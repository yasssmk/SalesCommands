# backend/tests/ai_pipelines/test_prep_call_idempotency.py
"""
Sprint 2 Game Plan — sub-step G12: Redis idempotency of the Game Plan's POST
(TD-50) — the test announced but missing in test_prep_call_view.py.

Before: POST /module-ai-pipelines/prep-call/run/ had no layer 1 (« Idempotence
layer 1 (Redis) intentionally omitted »): two concurrent POSTs with the same
Idempotency-Key both ran the pipeline — two LLM calls.

Now: the deal health's mechanics (core/idempotency start_op / complete_op /
fail_op), extracted to views/run_idempotency.py and shared by both views,
after the permission (403):
  * the same key while running -> 202 + poll_url, no second LLM call;
  * once answered -> the answer replayed, no new call: a success for
    IDEMPOTENCY_REDIS_TTL_SECONDS, an INFO or a failure for
    AI_RUN_SHORT_REPLAY_TTL_SECONDS (the rule is evaluated again after);
  * the same key with another payload -> 409;
  * without a key, the behaviour of today (no 400).

REAL local Redis (the settings' django_redis cache — required: the fixture
fails, never skips, without it). Unique keys per test; removed after.

Real path: the real view and pipeline, the fake LLM provider.

DB: Postgres.
"""

import json
import uuid

import pytest

from app_modules.activities.constants import ActivityStatus
from app_modules.activities.models import Activity
from app_modules.ai_pipelines.constants import (
    AI_RUN_SHORT_REPLAY_TTL_SECONDS,
    PREP_CALL_ACTIVITY_CLOSED_CODE,
    PREP_CALL_NOTHING_NEW_CODE,
)
from app_modules.ai_pipelines.models import AIPipelineRun, PrepCallSnapshot
from core.timeout_conventions import IDEMPOTENCY_REDIS_TTL_SECONDS

from tests.ai_pipelines.test_prep_call_not_an_analysis import _VALID_BRIEF, _preparable_activity


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/prep-call/run/'


@pytest.fixture
def real_redis():
    """The real local Redis behind core/idempotency — required."""
    from django.conf import settings
    from django.core.cache import cache
    from core.cache_utils import is_redis_healthy

    assert settings.CACHES['default']['BACKEND'] == 'django_redis.cache.RedisCache', (
        'G12 needs the local Redis (redis-server): the settings fell back to the file cache.')
    assert is_redis_healthy(), 'G12 needs the local Redis (redis-server).'
    client = cache.client.get_client()
    used = []
    yield {'client': client, 'keys': used}
    for redis_key in used:
        client.delete(redis_key)


@pytest.fixture
def activity(account, user_a):
    return _preparable_activity(account, user_a)


@pytest.fixture
def provider(patch_active_provider):
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)
    return patch_active_provider


def _key(real_redis, activity):
    from core.idempotency import _build_redis_key
    key = f'g12-{uuid.uuid4()}'
    real_redis['keys'].append(_build_redis_key(str(activity.client_id), key))
    return key


def _ttl(real_redis, activity, key):
    from core.idempotency import _build_redis_key
    return real_redis['client'].ttl(_build_redis_key(str(activity.client_id), key))


def _post(api, activity, key=None, **payload):
    headers = {'HTTP_IDEMPOTENCY_KEY': key} if key else {}
    return api.post(RUN_URL, {'activity_id': str(activity.id), **payload}, format='json', **headers)


def _llm_calls(provider):
    return len(provider.calls_for('prep_call'))


def _runs(activity):
    return AIPipelineRun.objects.filter(source_activity=activity).count()


# =============================================================================
# THE REPRO — two concurrent POSTs with the same key: ONE LLM call
# =============================================================================

def test_two_concurrent_posts_with_the_same_key_make_one_llm_call(
    authed_api_a, activity, provider, real_redis,
):
    key = _key(real_redis, activity)
    second = {}
    real_call = provider.call

    def call_while_a_second_post_arrives(**kwargs):
        if 'response' not in second:            # the 2nd POST lands DURING the 1st run
            second['response'] = _post(authed_api_a, activity, key)
        return real_call(**kwargs)

    provider.call = call_while_a_second_post_arrives

    first = _post(authed_api_a, activity, key)

    assert first.status_code == 201, first.content
    assert second['response'].status_code == 202, second['response'].content
    assert second['response'].json()['status'] == 'running'
    assert _llm_calls(provider) == 1
    assert _runs(activity) == 1


def test_a_replay_after_success_returns_the_same_result_without_a_new_call(
    authed_api_a, activity, provider, real_redis,
):
    key = _key(real_redis, activity)
    first = _post(authed_api_a, activity, key)
    assert first.status_code == 201, first.content

    replay = _post(authed_api_a, activity, key)

    assert replay.status_code == 201
    assert replay.json() == first.json()
    assert _llm_calls(provider) == 1 and _runs(activity) == 1
    assert _ttl(real_redis, activity, key) > AI_RUN_SHORT_REPLAY_TTL_SECONDS
    assert _ttl(real_redis, activity, key) <= IDEMPOTENCY_REDIS_TTL_SECONDS


# =============================================================================
# INFO / FAILURE — replayed only for the short TTL, then evaluated again
# =============================================================================

def test_a_replay_after_an_info_respects_the_short_ttl(
    authed_api_a, activity, provider, real_redis,
):
    Activity.objects.filter(pk=activity.pk).update(status=ActivityStatus.COMPLETED)
    key = _key(real_redis, activity)

    info = _post(authed_api_a, activity, key)
    assert info.json()['code'] == PREP_CALL_ACTIVITY_CLOSED_CODE
    assert 0 < _ttl(real_redis, activity, key) <= AI_RUN_SHORT_REPLAY_TTL_SECONDS
    assert _post(authed_api_a, activity, key).json() == info.json()       # replayed

    # The short TTL over (simulated: the key expires), the rule is evaluated
    # again — the activity re-planned, the same key generates.
    real_redis['client'].delete(real_redis['keys'][-1])
    Activity.objects.filter(pk=activity.pk).update(status=ActivityStatus.PLANNED)

    assert _post(authed_api_a, activity, key).status_code == 201
    assert _llm_calls(provider) == 1


def test_the_nothing_new_info_is_also_short(authed_api_a, activity, provider, real_redis):
    assert _post(authed_api_a, activity, _key(real_redis, activity)).status_code == 201
    key = _key(real_redis, activity)

    resp = _post(authed_api_a, activity, key)

    assert resp.json()['code'] == PREP_CALL_NOTHING_NEW_CODE
    assert 0 < _ttl(real_redis, activity, key) <= AI_RUN_SHORT_REPLAY_TTL_SECONDS


def test_a_replay_after_a_failure_respects_the_short_ttl(
    authed_api_a, activity, provider, real_redis,
):
    provider.replies['prep_call'] = json.dumps({'not': 'a plan'})
    key = _key(real_redis, activity)

    failed = _post(authed_api_a, activity, key)
    assert failed.status_code == 502
    assert 0 < _ttl(real_redis, activity, key) <= AI_RUN_SHORT_REPLAY_TTL_SECONDS

    replay = _post(authed_api_a, activity, key)

    assert replay.status_code == 502 and replay.json() == failed.json()
    calls = _llm_calls(provider)                       # the parse retry included
    assert _runs(activity) == 1
    assert _llm_calls(provider) == calls


# =============================================================================
# THE CONTRACT — conflict, no key, a 400 never left running
# =============================================================================

def test_the_same_key_with_another_payload_is_a_409(authed_api_a, activity, provider, real_redis):
    key = _key(real_redis, activity)
    assert _post(authed_api_a, activity, key).status_code == 201

    resp = _post(authed_api_a, activity, key, language_overrides=[{'ref': 'Nina', 'language': 'fr'}])

    assert resp.status_code == 409
    assert resp.json()['code'] == 'IDEMPOTENCY_CONFLICT'


def test_without_a_key_the_behaviour_is_unchanged(authed_api_a, activity, provider, real_redis):
    assert _post(authed_api_a, activity).status_code == 201
    again = _post(authed_api_a, activity)

    assert again.status_code == 200                                  # no 400
    assert again.json()['code'] == PREP_CALL_NOTHING_NEW_CODE         # G9, as today
    assert _llm_calls(provider) == 1


def test_a_standard_400_is_replayed_not_left_running(
    authed_api_a, account, user_a, provider, real_redis,
):
    from app_modules.activities.constants import ActivityType
    email = _preparable_activity(account, user_a)
    Activity.objects.filter(pk=email.pk).update(activity_type=ActivityType.EMAIL)
    key = _key(real_redis, email)
    overrides = [{'ref': 'Zoe', 'language': 'fr'}]

    first = _post(authed_api_a, email, key, language_overrides=overrides)
    again = _post(authed_api_a, email, key, language_overrides=overrides)

    assert first.status_code == 400 and again.status_code == 400      # never a 202
    assert again.json() == first.json()
    assert 0 < _ttl(real_redis, email, key) <= AI_RUN_SHORT_REPLAY_TTL_SECONDS
    assert not PrepCallSnapshot.objects.filter(activity=email).exists()


def test_the_permission_comes_before_the_idempotency_record(
    activity, provider, real_redis, authenticate, client_account_a, user_a,
):
    from rest_framework.test import APIClient
    from end_users.models import User
    stranger = User.objects.create(email='g12-stranger@tenant-a.test', client_account=client_account_a,
                                   role=user_a.role, is_active=True)
    client = APIClient(enforce_csrf_checks=False)
    authenticate(client, stranger, client_account_a.id)
    key = _key(real_redis, activity)

    assert _post(client, activity, key).status_code == 403
    assert _ttl(real_redis, activity, key) == -2                      # no record written
