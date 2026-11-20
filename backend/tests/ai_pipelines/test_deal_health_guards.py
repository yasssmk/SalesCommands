# backend/tests/ai_pipelines/test_deal_health_guards.py
"""
Sprint « Deal health v2 », step 6 — the guards of a deal health run.

Layer 1, Redis (TD-50): the core/idempotency.py pattern (start_op /
complete_op / fail_op, as activity_extraction_view.py) — a double click or a
second tab with the same Idempotency-Key never runs the LLM twice.
Layer 2, A10 — business rules, answered 200 + an INFO code, no LLM call, no
snapshot:
  * nothing new since the last snapshot (the step 3b sources cursor) →
    DEAL_HEALTH_NO_NEW_SOURCES;
  * a closed decision cycle (outcome set) → DEAL_HEALTH_CYCLE_CLOSED; the
    last diagnostic stays readable.

Real path: POST /module-ai-pipelines/deal-health/run/ through the real view,
the real DealHealthPipeline and the real core/idempotency.py; only the LLM
(the fake provider) and the Redis server (an in-memory client exposing the
commands core/idempotency.py sends) are stood in for.

  (a) the same Idempotency-Key twice → ONE LLM call, the 2nd replays;
  (b) the same key with another payload → 409 (the pattern's conflict);
  (c) nothing new → 200 + DEAL_HEALTH_NO_NEW_SOURCES, no call, no snapshot;
      a new source afterwards → the run happens again;
  (d) a closed cycle → 200 + DEAL_HEALTH_CYCLE_CLOSED, no call, no
      snapshot, the last diagnostic still served.
"""

import copy
import fnmatch
import json
import time

import pytest

from app_modules.ai_pipelines.constants import (
    DEAL_HEALTH_CYCLE_CLOSED_CODE,
    DEAL_HEALTH_NO_NEW_SOURCES_CODE,
)
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DealHealthSnapshot, DecisionCycle

from tests.ai_pipelines.conftest import fake_provider, patch_active_provider  # noqa: F401
from tests.ai_pipelines.deal_health_fixtures import V2_DIAGNOSTIC
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

RUN_URL = '/module-ai-pipelines/deal-health/run/'


# =============================================================================
# An in-memory Redis client — the commands core/idempotency.py sends
# =============================================================================

class _InMemoryRedis:
    def __init__(self):
        self.hashes, self.strings, self.expiry = {}, {}, {}

    def _alive(self, key):
        at = self.expiry.get(key)
        if at is not None and at <= time.monotonic():
            self.hashes.pop(key, None)
            self.strings.pop(key, None)
            self.expiry.pop(key, None)
        return key in self.hashes or key in self.strings

    def hgetall(self, key):
        if not self._alive(key):
            return {}
        return {k.encode(): str(v).encode() for k, v in self.hashes[key].items()}

    def hset(self, key, mapping):
        self._alive(key)
        self.hashes.setdefault(key, {}).update(mapping)
        return len(mapping)

    def expire(self, key, ttl):
        if self._alive(key):
            self.expiry[key] = time.monotonic() + ttl
        return True

    def set(self, key, value, nx=False, ex=None):
        if nx and self._alive(key):
            return None
        self.strings[key] = value
        if ex:
            self.expiry[key] = time.monotonic() + ex
        return True

    def delete(self, *keys):
        for key in keys:
            self.hashes.pop(key, None)
            self.strings.pop(key, None)
            self.expiry.pop(key, None)

    def keys(self, pattern='*'):
        return [k for k in list(self.hashes) + list(self.strings)
                if self._alive(k) and fnmatch.fnmatch(k, pattern)]


@pytest.fixture
def redis_store(monkeypatch):
    from core import idempotency

    store = _InMemoryRedis()

    class _Client:
        @staticmethod
        def get_client():
            return store

    class _Cache:
        client = _Client()

    monkeypatch.setattr(idempotency, 'is_redis_healthy', lambda *a, **k: True)
    monkeypatch.setattr(idempotency, 'cache', _Cache())
    return store


# =============================================================================
# Helpers
# =============================================================================

def _reply(provider):
    provider.replies['deal_health'] = json.dumps(copy.deepcopy(V2_DIAGNOSTIC))
    return provider


def _post(api, cycle, key=None, **extra):
    headers = {'HTTP_IDEMPOTENCY_KEY': key} if key else {}
    return api.post(RUN_URL, {'decision_cycle_id': str(cycle.id), **extra},
                    format='json', **headers)


def _snapshots(cycle):
    return DealHealthSnapshot.objects.filter(decision_cycle=cycle).count()


def _feed(cycle, activity, user, text):
    """A source of the deal changed: an activity of the cycle with content."""
    activity.decision_cycle = cycle
    activity.transcript = text
    activity.save(user=user, client_id=cycle.client_id)


# =============================================================================
# (a) / (b) — layer 1, Redis
# =============================================================================

def test_a_the_same_key_twice_runs_the_llm_once_and_replays(
    authed_api_a, cycle, activity, user_a, patch_active_provider, redis_store,
):
    provider = _reply(patch_active_provider)
    _feed(cycle, activity, user_a, 'Finance wants faster closing.')

    first = _post(authed_api_a, cycle, key='dh-key-1')
    second = _post(authed_api_a, cycle, key='dh-key-1')

    assert first.status_code == 201, first.content
    assert len(provider.calls_for('deal_health')) == 1
    # The 2nd answer replays the state of the 1st: the same snapshot.
    assert second.status_code == 201, second.content
    assert second.data['data']['snapshot']['id'] == first.data['data']['snapshot']['id']
    assert _snapshots(cycle) == 1


def test_a2_a_double_click_during_the_llm_call_is_answered_202_without_a_2nd_call(
    authed_api_a, cycle, activity, user_a, patch_active_provider, redis_store,
):
    """The real double click: the 2nd POST arrives WHILE the 1st is calling
    the LLM (layer 2 cannot see it yet: no snapshot written)."""
    provider = _reply(patch_active_provider)
    _feed(cycle, activity, user_a, 'Finance wants faster closing.')
    during = {}
    real_call = provider.call

    def call_and_click_again(**kwargs):
        if 'second' not in during:
            during['second'] = None                  # click again only once
            during['second'] = _post(authed_api_a, cycle, key='dh-key-3')
        return real_call(**kwargs)

    provider.call = call_and_click_again
    first = _post(authed_api_a, cycle, key='dh-key-3')

    assert first.status_code == 201, first.content
    second = during['second']
    assert second.status_code == 202, second.content
    assert second.data['status'] == 'running'
    assert second.data['poll_url']
    assert len(provider.calls_for('deal_health')) == 1
    assert _snapshots(cycle) == 1


def test_b_the_same_key_with_another_payload_is_a_conflict(
    authed_api_a, cycle, account, user_a, patch_active_provider, redis_store,
):
    provider = _reply(patch_active_provider)
    other = DecisionCycle(account=account, owner=user_a, name='Other', is_active=True)
    other.save(user=user_a, client_id=account.client_id)

    assert _post(authed_api_a, cycle, key='dh-key-2').status_code == 201
    conflict = _post(authed_api_a, other, key='dh-key-2')

    assert conflict.status_code == 409, conflict.content
    assert conflict.data['code'] == 'IDEMPOTENCY_CONFLICT'
    assert len(provider.calls_for('deal_health')) == 1
    assert _snapshots(other) == 0


# =============================================================================
# (c) — nothing new since the last snapshot (A10)
# =============================================================================

def test_c_nothing_new_is_an_info_without_llm_call_nor_snapshot(
    authed_api_a, cycle, activity, user_a, patch_active_provider,
):
    provider = _reply(patch_active_provider)
    _feed(cycle, activity, user_a, 'Finance wants faster closing.')
    assert _post(authed_api_a, cycle).status_code == 201

    resp = _post(authed_api_a, cycle)

    assert resp.status_code == 200, resp.content
    assert resp.data['success'] is True
    assert resp.data['code'] == DEAL_HEALTH_NO_NEW_SOURCES_CODE
    assert resp.data['data']['snapshot'] is None
    assert resp.data['data']['last_analysis_at']          # the date the front shows
    assert len(provider.calls_for('deal_health')) == 1    # the first run only
    assert _snapshots(cycle) == 1


def test_c_a_new_source_afterwards_runs_again(
    authed_api_a, cycle, activity, user_a, patch_active_provider,
):
    provider = _reply(patch_active_provider)
    _feed(cycle, activity, user_a, 'Finance wants faster closing.')
    assert _post(authed_api_a, cycle).status_code == 201

    _feed(cycle, activity, user_a, 'Finance wants faster closing. Budget owner met.')
    resp = _post(authed_api_a, cycle)

    assert resp.status_code == 201, resp.content
    assert len(provider.calls_for('deal_health')) == 2
    assert _snapshots(cycle) == 2


# =============================================================================
# (d) — a closed decision cycle (A10)
# =============================================================================

def test_d_a_closed_cycle_is_an_info_and_its_last_diagnostic_stays_readable(
    authed_api_a, cycle, activity, user_a, patch_active_provider,
):
    provider = _reply(patch_active_provider)
    _feed(cycle, activity, user_a, 'Finance wants faster closing.')
    assert _post(authed_api_a, cycle).status_code == 201
    DecisionCycle.objects.filter(pk=cycle.pk).update(outcome=CycleOutcome.LOST)
    _feed(cycle, activity, user_a, 'A late note after the loss.')   # even with a new source

    resp = _post(authed_api_a, cycle)

    assert resp.status_code == 200, resp.content
    assert resp.data['success'] is True
    assert resp.data['code'] == DEAL_HEALTH_CYCLE_CLOSED_CODE
    assert resp.data['data']['snapshot'] is None
    assert len(provider.calls_for('deal_health')) == 1
    assert _snapshots(cycle) == 1
    latest = authed_api_a.get(f'/decision_cycles/{cycle.id}/health-snapshots/latest/')
    assert latest.status_code == 200
    assert latest.data['data'] is not None
