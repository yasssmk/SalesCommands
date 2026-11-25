# backend/tests/ai_pipelines/test_deal_health_hard_crash.py
"""
Sprint 2 Game Plan — sub-step S4b (defect, same as S4 on the prep call): a
deal-health crash BEFORE the run row exists no longer hides the original
error.

Before: DealHealthPipeline.run opens its run inside the `try`
(pipelines/deal_health.py:205-207); when `_create_run` itself raised, the
`except Exception` (:303-309) called `self._finalize_run(run, …)` on a name
never bound — an UnboundLocalError replaced the original error, and the
view's `deal_health_run.pipeline_hard_crash` log carried the
UnboundLocalError, the real cause only as its context.

Now: DealHealthPipeline goes through BasePipeline._finalize_hard_crash
(pipelines/base.py, S4), which finalises the run only when it exists. The
ORIGINAL error propagates to the view and is logged as the hard crash; the
client gets the standard answer — 502 and the generic message — nothing
technical; no LLM call.

Real path: POST /module-ai-pipelines/deal-health/run/ through the real view
and the real DealHealthPipeline; the LLM is the fake provider and Redis the
in-memory client of test_deal_health_guards.py; `_create_run` patched to
raise.

DB: Postgres.
"""

import logging

import pytest

from app_modules.ai_pipelines.pipelines.deal_health import DealHealthPipeline

from tests.ai_pipelines.conftest import fake_provider, patch_active_provider  # noqa: F401
from tests.ai_pipelines.test_deal_health_guards import _post, _reply, redis_store  # noqa: F401
from tests.decision_cycles.conftest import (  # noqa: F401
    pytest_configure,
    _jwt_only_no_csrf,
    tenant_a_id,
    tenant_b_id,
    client_account_a,
    client_account_b,
    role_individual_a,
    role_individual_b,
    user_a,
    user_b,
    account,
    other_tenant_account,
    activity,
    contact,
    api,
    authenticate,
    authed_api_a,
    authed_api_b,
    cache_invalidation_calls,
    cycle,
)


pytestmark = pytest.mark.django_db

GENERIC_ERROR = 'An unexpected error occurred during the pipeline run.'
SECRET = 'connection refused on db-internal-7:5432'


class _RunTableDown(Exception):
    """The original error: the run row cannot be written."""


@pytest.fixture
def run_creation_fails(monkeypatch):
    def _boom(self, **kwargs):
        raise _RunTableDown(SECRET)
    monkeypatch.setattr(DealHealthPipeline, '_create_run', _boom)


def _hard_crash_records(caplog):
    return [r for r in caplog.records if r.getMessage() == 'deal_health_run.pipeline_hard_crash']


def test_the_original_error_is_logged_and_the_client_gets_the_standard_answer(
    authed_api_a, cycle, patch_active_provider, redis_store, run_creation_fails, caplog,
):
    provider = _reply(patch_active_provider)

    with caplog.at_level(logging.ERROR):
        resp = _post(authed_api_a, cycle, key='dh-crash-1')

    # The standard answer (the view's hard-crash path).
    assert resp.status_code == 502, resp.content
    assert resp.json() == {'success': False, 'error': GENERIC_ERROR}
    # Nothing technical reaches the client.
    body = resp.content.decode()
    assert SECRET not in body
    assert 'UnboundLocalError' not in body

    # The ORIGINAL error is the one logged as the hard crash.
    records = _hard_crash_records(caplog)
    assert len(records) == 1, [r.getMessage() for r in caplog.records]
    logged = records[0].exc_info[1]
    assert isinstance(logged, _RunTableDown), repr(logged)
    assert str(logged) == SECRET

    # No LLM call: the crash happened before the run existed.
    assert provider.calls == []


def test_a_crash_after_the_run_exists_still_finalises_it_with_the_cut_error(
    authed_api_a, cycle, activity, user_a, patch_active_provider, redis_store,
    monkeypatch,
):
    """Non-regression of the hard-crash path WITH a run: it is finalised
    LLM_ERROR, « hard crash: » + the exception text cut to
    HARD_CRASH_ERROR_MAX_CHARS (ai_pipelines/constants.py)."""
    from app_modules.ai_pipelines.constants import (
        AIPipelineStatus,
        AIPipelineType,
        HARD_CRASH_ERROR_MAX_CHARS,
    )
    from app_modules.ai_pipelines.models import AIPipelineRun
    from app_modules.ai_pipelines.services.deal_health_writer import DealHealthWriter

    _reply(patch_active_provider)
    long_text = 'x' * (HARD_CRASH_ERROR_MAX_CHARS + 500)

    def _boom(self, **kwargs):
        raise RuntimeError(long_text)
    monkeypatch.setattr(DealHealthWriter, 'write', _boom)

    resp = _post(authed_api_a, cycle, key='dh-crash-2')

    assert resp.status_code == 502, resp.content
    assert resp.json() == {'success': False, 'error': GENERIC_ERROR}
    run = AIPipelineRun.objects.get(
        source_decision_cycle=cycle, pipeline_type=AIPipelineType.DEAL_HEALTH,
    )
    assert run.status == AIPipelineStatus.LLM_ERROR
    assert run.error_message == f'hard crash: {long_text[:HARD_CRASH_ERROR_MAX_CHARS]}'
