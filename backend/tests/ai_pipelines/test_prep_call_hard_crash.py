# backend/tests/ai_pipelines/test_prep_call_hard_crash.py
"""
Sprint 2 Game Plan — sub-step S4 (defect): a hard crash BEFORE the run row
exists no longer hides the original error.

Before: PrepCallPipeline.run opens its run inside the `try`
(pipelines/prep_call.py:113-121); when `_create_run` itself raised, the
`except Exception` called `self._finalize_run(run, …)` on a name never bound
— an UnboundLocalError replaced the original error. The view's
`prep_call_run.pipeline_hard_crash` log then carried the UnboundLocalError,
the real cause only as its context.

Now: the hard-crash path goes through BasePipeline._finalize_hard_crash
(pipelines/base.py), which finalises the run only when it exists; the
ORIGINAL error propagates to the view, is logged as the hard crash, and the
client gets the pipeline's standard error answer — 502 and the same generic
message as the deal health (views/deal_health_view.py) — with nothing
technical in it.

Real path: POST /module-ai-pipelines/prep-call/run/ with the real
PrepCallPipeline (fake LLM provider), `_create_run` patched to raise.

DB: Postgres.
"""

import json
import logging

import pytest

from app_modules.ai_pipelines.pipelines.prep_call import PrepCallPipeline

from tests.ai_pipelines.test_prep_call_not_an_analysis import _VALID_BRIEF
from tests.signals.test_signal_cycle_attachment import _plain_activity


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/prep-call/run/'
GENERIC_ERROR = 'An unexpected error occurred during the pipeline run.'
SECRET = 'connection refused on db-internal-7:5432'


class _RunTableDown(Exception):
    """The original error: the run row cannot be written."""


@pytest.fixture
def activity(account, user_a):
    return _plain_activity(account, user_a)


@pytest.fixture
def prep_call_provider(patch_active_provider):
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)
    return patch_active_provider


@pytest.fixture
def run_creation_fails(monkeypatch):
    def _boom(self, **kwargs):
        raise _RunTableDown(SECRET)
    monkeypatch.setattr(PrepCallPipeline, '_create_run', _boom)


def _hard_crash_records(caplog):
    return [r for r in caplog.records if r.getMessage() == 'prep_call_run.pipeline_hard_crash']


def test_the_original_error_is_logged_and_the_client_gets_the_standard_answer(
    authed_api_a, activity, prep_call_provider, run_creation_fails, caplog,
):
    with caplog.at_level(logging.ERROR):
        resp = authed_api_a.post(RUN_URL, {'activity_id': str(activity.id)}, format='json')

    # The standard answer of the pipeline (the deal health's, same case).
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

    # No LLM call was made: the crash happened before the run existed.
    assert prep_call_provider.calls == []
