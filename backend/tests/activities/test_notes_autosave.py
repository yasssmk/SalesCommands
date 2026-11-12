# backend/tests/activities/test_notes_autosave.py
"""
Sprint « Source / Notes » — notes panel, N1: the note-only AUTOSAVE endpoint.

    POST /module-activities/{id}/notes/   { "outcome_notes": "<text>" }

A light write for the notes panel's autosave (every pause in typing): ONE
`.update()` of outcome_notes + updated_at / updated_by — no post_save cascade
(cache invalidation, readiness recompute…), no audit_log. Same rules as the
PATCH everywhere else:
  * the CANCELLED lock (is_activity_signals_locked → SOURCE_LOCKED, 400);
  * tenant scoping (another tenant's activity → 404);
  * the update permission and scope of the PATCH (same answer as the PATCH);
  * its OWN throttle scope `notes_autosave` — the global per-user throttle
    does not apply to it.
Through the real endpoint.
"""

from unittest import mock

import pytest
from django.core.cache import cache
from django.db import connection
from django.db.models.signals import post_save
from django.test.utils import CaptureQueriesContext
from rest_framework import status

from app_modules.activities.constants import ActivityStatus, ActivityType
from core.error_messages import ActivityErrorMessages


pytestmark = pytest.mark.django_db
URL = '/module-activities/{}/notes/'
TODAY = '2026-11-11'


@pytest.fixture(autouse=True)
def _fresh_throttle_counters():
    cache.clear()
    yield
    cache.clear()


def _activity(account, owner, activity_status=ActivityStatus.PLANNED, notes='N', title='Discovery'):
    from app_modules.activities.models import Activity
    a = Activity(title=title, activity_type=ActivityType.MEETING, status=ActivityStatus.PLANNED,
                 account=account, owner=owner, scheduled_date=TODAY)
    a.save(user=owner, client_id=account.client_id)
    Activity.objects.filter(id=a.id).update(status=activity_status, outcome_notes=notes)
    a.refresh_from_db()
    return a


def _post(api, activity, notes='N — later', **extra):
    return api.post(URL.format(activity.id), {'outcome_notes': notes, **extra}, format='json')


# =============================================================================
# The write
# =============================================================================

def test_the_note_is_written_with_updated_at_and_updated_by(authed_api_a, account, user_a):
    activity = _activity(account, user_a)
    before = activity.updated_at
    r = _post(authed_api_a, activity, 'Takeaways, typed during the call')
    assert r.status_code == status.HTTP_200_OK, r.content
    activity.refresh_from_db()
    assert activity.outcome_notes == 'Takeaways, typed during the call'
    assert activity.updated_at > before
    assert activity.updated_by_id == user_a.id
    body = r.json()['data']
    assert body['outcome_notes'] == 'Takeaways, typed during the call'
    assert body['updated_at']


def test_only_the_note_is_written(authed_api_a, account, user_a):
    activity = _activity(account, user_a)
    r = _post(authed_api_a, activity, 'x', title='Hijacked', status=ActivityStatus.CANCELLED)
    assert r.status_code == status.HTTP_200_OK, r.content
    activity.refresh_from_db()
    assert activity.title == 'Discovery'
    assert activity.status == ActivityStatus.PLANNED


def test_an_empty_note_is_written_empty(authed_api_a, account, user_a):
    activity = _activity(account, user_a)
    assert _post(authed_api_a, activity, '').status_code == status.HTTP_200_OK
    activity.refresh_from_db()
    assert (activity.outcome_notes or '') == ''


def test_the_note_key_is_required(authed_api_a, account, user_a):
    activity = _activity(account, user_a)
    r = authed_api_a.post(URL.format(activity.id), {}, format='json')
    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.content
    activity.refresh_from_db()
    assert activity.outcome_notes == 'N'


@pytest.mark.parametrize('activity_status', [
    ActivityStatus.PLANNED, ActivityStatus.ON_HOLD, ActivityStatus.COMPLETED,
])
def test_writable_outside_cancelled(authed_api_a, account, user_a, activity_status):
    activity = _activity(account, user_a, activity_status)
    assert _post(authed_api_a, activity).status_code == status.HTTP_200_OK


def test_a_cancelled_activity_refuses_with_source_locked(authed_api_a, account, user_a):
    activity = _activity(account, user_a, ActivityStatus.CANCELLED)
    r = _post(authed_api_a, activity)
    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.content
    assert str(ActivityErrorMessages.SOURCE_LOCKED) in r.content.decode()
    activity.refresh_from_db()
    assert activity.outcome_notes == 'N'


# =============================================================================
# Light: one UPDATE, no cascade, no audit
# =============================================================================

def test_one_update_no_post_save_no_audit(authed_api_a, account, user_a):
    from app_modules.activities.models import Activity
    activity = _activity(account, user_a)
    receiver = mock.Mock()
    post_save.connect(receiver, sender=Activity, weak=False)
    try:
        with mock.patch('app_modules.activities.views.views.audit_log') as audit, \
                CaptureQueriesContext(connection) as ctx:
            r = _post(authed_api_a, activity)
    finally:
        post_save.disconnect(receiver, sender=Activity)
    assert r.status_code == status.HTTP_200_OK, r.content
    receiver.assert_not_called()
    audit.assert_not_called()
    updates = [q['sql'] for q in ctx.captured_queries
               if q['sql'].lstrip().upper().startswith('UPDATE') and 'module_activities' in q['sql']]
    assert len(updates) == 1, updates


# =============================================================================
# Tenant + permissions: the PATCH's
# =============================================================================

def test_another_tenants_activity_is_not_found(authed_api_a, other_tenant_activity):
    r = _post(authed_api_a, other_tenant_activity)
    assert r.status_code == status.HTTP_404_NOT_FOUND, r.content


@pytest.fixture
def other_owner_a(db, client_account_a, role_individual_a):
    from end_users.models import User
    return User.objects.create(email='other-owner-a@tenant-a.test', client_account=client_account_a,
                               role=role_individual_a, is_active=True)


@pytest.fixture
def read_only_user_a(db, client_account_a):
    from end_users.models import User, UserRole
    role = UserRole.objects.create(client_account=client_account_a, name='Read only',
                                   is_admin=False, is_manager=False, is_individual=True,
                                   read=True, write=False, modify=False, can_delete=False)
    return User.objects.create(email='read-only-a@tenant-a.test', client_account=client_account_a,
                               role=role, is_active=True)


@pytest.mark.parametrize('who', ['owner', 'other_owner', 'read_only'])
def test_same_permission_answer_as_the_patch(
    api, authenticate, client_account_a, account, user_a, other_owner_a, read_only_user_a, who,
):
    actor = {'owner': user_a, 'other_owner': other_owner_a, 'read_only': read_only_user_a}[who]
    authenticate(api, actor, client_account_a.id)
    via_patch = api.patch(f'/module-activities/{_activity(account, user_a).id}/',
                          {'outcome_notes': 'p'}, format='json').status_code
    via_notes = _post(api, _activity(account, user_a, title='Second')).status_code
    assert via_notes == via_patch, (who, via_notes, via_patch)


# =============================================================================
# Throttle: its own scope, not the global per-user one
# =============================================================================

def _rates(**overrides):
    from django.conf import settings as dj
    return {**dj.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'], **overrides}


def test_the_notes_autosave_scope_is_configured():
    from django.conf import settings as dj
    assert dj.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['notes_autosave'] == '60/minute'


def test_its_own_throttle_scope_applies(settings, authed_api_a, account, user_a):
    activity = _activity(account, user_a)
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK,
                               'DEFAULT_THROTTLE_RATES': _rates(notes_autosave='2/minute')}
    codes = [_post(authed_api_a, activity, f'v{i}').status_code for i in range(3)]
    assert codes == [200, 200, 429], codes


def test_the_global_per_user_throttle_does_not_apply(monkeypatch, authed_api_a, account, user_a):
    from rest_framework.throttling import SimpleRateThrottle
    activity = _activity(account, user_a)
    monkeypatch.setattr(SimpleRateThrottle, 'THROTTLE_RATES',
                        _rates(user='1/hour', standard='1/minute'))
    # Control: an ordinary endpoint IS throttled by the global classes at that
    # rate (a GET: an activity WRITE clears the whole cache on a non-Redis
    # backend — core/cache_utils.invalidate_tag — counters included).
    get_codes = [authed_api_a.get(f'/module-activities/{activity.id}/').status_code for _ in range(2)]
    assert get_codes == [200, 429], get_codes
    notes_codes = [_post(authed_api_a, activity, f'v{i}').status_code for i in range(3)]
    assert notes_codes == [200, 200, 200], notes_codes
