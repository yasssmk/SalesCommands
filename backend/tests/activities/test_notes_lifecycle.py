# backend/tests/activities/test_notes_lifecycle.py
"""
Sprint « Source / Notes » — ONE note per activity: `Activity.outcome_notes`
is the activity's notes, filled throughout its lifecycle.

1.1 — the lock (PO, Q2): the notes and the transcript of the Source band are
editable on a PLANNED / ON_HOLD / COMPLETED activity and LOCKED on a
CANCELLED one — server side, through the real PATCH /module-activities/{id}/,
with the ONE predicate of the signal bands (activities/services/
signals_lock.py, mirror of frontend utils/activitySignalsLock.js).
"""

import pytest
from rest_framework import status

from app_modules.activities.constants import ActivityStatus, ActivityType
from core.error_messages import ActivityErrorMessages


pytestmark = pytest.mark.django_db
URL = '/module-activities/'
TODAY = '2026-11-09'


def _activity(account, user, activity_status=ActivityStatus.PLANNED, notes=None, transcript=None):
    from app_modules.activities.models import Activity
    a = Activity(title='Discovery', activity_type=ActivityType.MEETING,
                 status=ActivityStatus.PLANNED, account=account, owner=user,
                 scheduled_date=TODAY)
    a.save(user=user, client_id=account.client_id)
    # The status / note are set in DB directly: the test reads what a PATCH
    # does on an activity already in that state, whatever flow put it there.
    Activity.objects.filter(id=a.id).update(
        status=activity_status, outcome_notes=notes, transcript=transcript,
    )
    a.refresh_from_db()
    return a


def _patch(api, activity, **fields):
    return api.patch(f'{URL}{activity.id}/', fields, format='json')


# =============================================================================
# 1.1 — the notes / transcript lock (CANCELLED only)
# =============================================================================

@pytest.mark.parametrize('activity_status', [
    ActivityStatus.PLANNED, ActivityStatus.ON_HOLD, ActivityStatus.COMPLETED,
])
def test_the_notes_are_editable_outside_cancelled(authed_api_a, account, user_a, activity_status):
    activity = _activity(account, user_a, activity_status, notes='N')
    r = _patch(authed_api_a, activity, outcome_notes='N — later')
    assert r.status_code == status.HTTP_200_OK, r.content
    activity.refresh_from_db()
    assert activity.outcome_notes == 'N — later'


def test_the_notes_of_a_cancelled_activity_are_locked(authed_api_a, account, user_a):
    activity = _activity(account, user_a, ActivityStatus.CANCELLED, notes='N')
    r = _patch(authed_api_a, activity, outcome_notes='Changed')
    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.content
    assert str(ActivityErrorMessages.SOURCE_LOCKED) in r.content.decode()
    activity.refresh_from_db()
    assert activity.outcome_notes == 'N'


def test_the_transcript_of_a_cancelled_activity_is_locked(authed_api_a, account, user_a):
    activity = _activity(account, user_a, ActivityStatus.CANCELLED, transcript='T')
    r = _patch(authed_api_a, activity, transcript='Changed')
    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.content
    assert str(ActivityErrorMessages.SOURCE_LOCKED) in r.content.decode()
    activity.refresh_from_db()
    assert activity.transcript == 'T'


def test_resending_the_same_notes_on_a_cancelled_activity_is_no_change(authed_api_a, account, user_a):
    # The rule refuses a CHANGE (the transcript-lock model, 8g-7): a form
    # that re-sends the unchanged value is not refused.
    activity = _activity(account, user_a, ActivityStatus.CANCELLED, notes='N', transcript='T')
    r = _patch(authed_api_a, activity, outcome_notes='N', transcript='T')
    assert r.status_code == status.HTTP_200_OK, r.content


@pytest.mark.parametrize('activity_status, locked', [
    (ActivityStatus.PLANNED, False), (ActivityStatus.ON_HOLD, False),
    (ActivityStatus.COMPLETED, False), (ActivityStatus.CANCELLED, True),
])
def test_one_predicate_for_the_lock(account, user_a, activity_status, locked):
    from app_modules.activities.services.signals_lock import is_activity_signals_locked
    assert is_activity_signals_locked(_activity(account, user_a, activity_status)) is locked
    assert is_activity_signals_locked(None) is False


def test_the_field_is_the_activity_notes():
    from app_modules.activities.models import Activity
    field = Activity._meta.get_field('outcome_notes')
    assert str(field.verbose_name) == 'Notes'
    assert str(field.help_text) == 'Notes of the activity, filled throughout its lifecycle'


# =============================================================================
# 1.2 — no note at closure (PO, Q-i): complete / cancel / process_result /
# log-response / record-no-answer no longer take a note. A key still sent
# (`outcome_notes` / `notes`) is ignored like any unknown key: the note
# written during the activity stays INTACT. Through the real endpoints.
# =============================================================================

from tests.activities.test_next_planned_step import _days, chain  # noqa: E402,F401


NOTE = 'N — call takeaways'


def _with_note(activity):
    from app_modules.activities.models import Activity
    Activity.objects.filter(id=activity.id).update(outcome_notes=NOTE)
    activity.refresh_from_db()
    return activity


def _note_of(activity):
    activity.refresh_from_db()
    return activity.outcome_notes


def _in_progress(activity):
    from app_modules.campaigns.models import CampaignAccount, CampaignContact
    CampaignContact.objects.filter(id=activity.campaign_contact_id).update(status='IN_PROGRESS')
    CampaignAccount.objects.filter(id=activity.campaign_account_id).update(status='IN_PROGRESS')


@pytest.mark.parametrize('payload', [
    {'outcome': 'SUCCESSFUL'},
    {'outcome': 'SUCCESSFUL', 'outcome_notes': 'X'},
    {'outcome': 'SUCCESSFUL', 'notes': 'X'},
], ids=['no-key', 'outcome_notes-key', 'notes-alias'])
def test_complete_keeps_the_note(authed_api_a, account, user_a, payload):
    activity = _with_note(_activity(account, user_a))
    r = authed_api_a.post(f'{URL}{activity.id}/complete/', payload, format='json')
    assert r.status_code == status.HTTP_200_OK, r.content
    assert activity.__class__.objects.get(id=activity.id).status == ActivityStatus.COMPLETED
    assert _note_of(activity) == NOTE


def test_completing_an_already_completed_activity_keeps_the_note(authed_api_a, account, user_a):
    activity = _with_note(_activity(account, user_a, ActivityStatus.COMPLETED))
    r = authed_api_a.post(f'{URL}{activity.id}/complete/',
                          {'outcome': 'FOLLOW_UP_NEEDED', 'outcome_notes': 'X'}, format='json')
    assert r.status_code == status.HTTP_200_OK, r.content
    activity.refresh_from_db()
    assert activity.outcome == 'FOLLOW_UP_NEEDED'
    assert activity.outcome_notes == NOTE


@pytest.mark.parametrize('payload', [{}, {'notes': 'Reason'}, {'outcome_notes': 'Reason'}],
                         ids=['no-key', 'notes-key', 'outcome_notes-key'])
def test_cancel_keeps_the_note(authed_api_a, account, user_a, payload):
    activity = _with_note(_activity(account, user_a))
    r = authed_api_a.post(f'{URL}{activity.id}/cancel/', payload, format='json')
    assert r.status_code == status.HTTP_200_OK, r.content
    activity.refresh_from_db()
    assert activity.status == ActivityStatus.CANCELLED
    assert activity.outcome_notes == NOTE


def test_completing_a_campaign_step_keeps_the_note(authed_api_a, chain):
    # /complete/ on a PLANNED campaign activity → CampaignExecutionService.process_result
    step = _with_note(chain(1, date=_days(0)))
    chain(2, date=_days(3))
    _in_progress(step)
    r = authed_api_a.post(f'{URL}{step.id}/complete/',
                          {'outcome': 'NOT_INTERESTED', 'outcome_notes': 'X'}, format='json')
    assert r.status_code == status.HTTP_200_OK, r.content
    step.refresh_from_db()
    assert step.status == ActivityStatus.COMPLETED
    assert step.outcome_notes == NOTE


def test_the_exhausted_no_answer_keeps_the_note(authed_api_a, chain):
    # The last allowed no-answer → process_result(NO_ANSWER).
    from app_modules.activities.models import Activity
    from app_modules.campaigns.config.settings import CONFIG
    step = _with_note(chain(1, date=_days(0)))
    _in_progress(step)
    Activity.objects.filter(id=step.id).update(no_answer_count=CONFIG.limits.max_retry_attempts - 1)
    r = authed_api_a.post(f'{URL}{step.id}/record-no-answer/', {'outcome_notes': 'X'}, format='json')
    assert r.status_code == status.HTTP_200_OK, r.content
    step.refresh_from_db()
    assert step.status == ActivityStatus.COMPLETED
    assert step.outcome == 'NO_ANSWER'
    assert step.outcome_notes == NOTE


def test_a_logged_response_keeps_the_note(authed_api_a, chain):
    step = _with_note(chain(1, ActivityStatus.COMPLETED, _days(-2)))
    chain(2, date=_days(1))
    _in_progress(step)
    r = authed_api_a.post(f'/campaigns/{step.campaign_id}/log-response/',
                          {'activity_id': str(step.id), 'response': 'NEGATIVE', 'notes': 'X'},
                          format='json')
    assert r.status_code == status.HTTP_200_OK, r.content
    step.refresh_from_db()
    assert step.outcome == 'NOT_INTERESTED'
    assert step.outcome_notes == NOTE


def test_the_closure_methods_take_no_note():
    # No phantom field: the note parameter is REMOVED, not ignored.
    import inspect
    from app_modules.activities.models import Activity
    assert 'notes' not in inspect.signature(Activity.complete).parameters
    assert 'notes' not in inspect.signature(Activity.cancel).parameters


# =============================================================================
# 1.3 — reopening keeps the note (PO): POST /reopen/ and a PATCH of status
# COMPLETED → other no longer clear the activity's notes; the outcome and
# completed_at are still cleared (a reopened activity has no result).
# =============================================================================

def _closed(account, user, activity_status, outcome=None):
    from django.utils import timezone
    from app_modules.activities.models import Activity
    activity = _with_note(_activity(account, user, activity_status))
    Activity.objects.filter(id=activity.id).update(outcome=outcome, completed_at=timezone.now())
    activity.refresh_from_db()
    return activity


@pytest.mark.parametrize('activity_status, outcome', [
    (ActivityStatus.COMPLETED, 'SUCCESSFUL'),
    (ActivityStatus.CANCELLED, None),
])
def test_reopen_keeps_the_note(authed_api_a, account, user_a, activity_status, outcome):
    activity = _closed(account, user_a, activity_status, outcome)
    r = authed_api_a.post(f'{URL}{activity.id}/reopen/', {}, format='json')
    assert r.status_code == status.HTTP_200_OK, r.content
    activity.refresh_from_db()
    assert activity.status == ActivityStatus.PLANNED
    assert activity.outcome is None
    assert activity.completed_at is None
    assert activity.outcome_notes == NOTE


def test_a_status_patch_out_of_completed_keeps_the_note(authed_api_a, account, user_a):
    activity = _closed(account, user_a, ActivityStatus.COMPLETED, 'SUCCESSFUL')
    r = _patch(authed_api_a, activity, status=ActivityStatus.PLANNED)
    assert r.status_code == status.HTTP_200_OK, r.content
    activity.refresh_from_db()
    assert activity.status == ActivityStatus.PLANNED
    assert activity.outcome is None
    assert activity.completed_at is None
    assert activity.outcome_notes == NOTE


# =============================================================================
# 1.4 — a system cancellation APPENDS a line at the END of the note, never
# erasing what is there (PO): empty note → the line alone; written note →
# « <note>\n\n<line> ». One UPDATE per call. Through the real endpoints.
# =============================================================================

def _note_rows(*activities):
    from app_modules.activities.models import Activity
    return {a.id: Activity.objects.get(id=a.id) for a in activities}


def test_cancel_planned_appends_its_line_to_the_note(authed_api_a, account, chain):
    from app_modules.activities.models import Activity
    from app_modules.campaigns.constants import CANCEL_PLANNED_NOTE_LINE
    written = _with_note(chain(1, date=_days(1)))
    empty = chain(2, date=_days(3))
    Activity.objects.filter(id=empty.id).update(outcome_notes='')
    unset = chain(3, date=_days(5))
    before = _note_rows(written)[written.id].updated_at
    r = authed_api_a.delete(f'/campaigns/{written.campaign_id}/cancel-planned/',
                            {'scope': 'account', 'account_id': str(account.id)}, format='json')
    assert r.status_code == status.HTTP_200_OK, r.content
    rows = _note_rows(written, empty, unset)
    assert all(a.status == ActivityStatus.CANCELLED for a in rows.values())
    assert rows[written.id].outcome_notes == f'{NOTE}\n\n{CANCEL_PLANNED_NOTE_LINE}'
    assert rows[empty.id].outcome_notes == CANCEL_PLANNED_NOTE_LINE
    assert rows[unset.id].outcome_notes == CANCEL_PLANNED_NOTE_LINE
    assert rows[written.id].updated_at > before


def test_removing_a_target_appends_its_line_to_the_note(authed_api_a, chain):
    from app_modules.activities.models import Activity
    from app_modules.campaigns.constants import TARGET_REMOVED_NOTE_LINE
    done = _with_note(chain(1, ActivityStatus.COMPLETED, _days(-2)))
    written = _with_note(chain(2, date=_days(1)))
    on_hold = chain(3, date=_days(4))
    Activity.objects.filter(id=on_hold.id).update(status=ActivityStatus.ON_HOLD)
    r = authed_api_a.delete(f'/campaigns/contacts/{written.campaign_contact_id}/')
    assert r.status_code in (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT), r.content
    rows = _note_rows(done, written, on_hold)
    assert rows[written.id].status == rows[on_hold.id].status == ActivityStatus.CANCELLED
    assert rows[written.id].outcome_notes == f'{NOTE}\n\n{TARGET_REMOVED_NOTE_LINE}'
    assert rows[on_hold.id].outcome_notes == TARGET_REMOVED_NOTE_LINE
    # A finished step is not touched.
    assert rows[done.id].status == ActivityStatus.COMPLETED
    assert rows[done.id].outcome_notes == NOTE


def test_the_system_line_is_one_update_and_a_blank_note_counts_as_empty(account, user_a):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    from app_modules.activities.models import Activity
    from app_modules.activities.services.activity_notes import notes_with_system_line
    written = _with_note(_activity(account, user_a))
    blank = _activity(account, user_a, notes='   ')
    unset = _activity(account, user_a)
    ids = [written.id, blank.id, unset.id]
    with CaptureQueriesContext(connection) as ctx:
        Activity.objects.filter(id__in=ids).update(outcome_notes=notes_with_system_line('L'))
    assert len(ctx.captured_queries) == 1
    notes = dict(Activity.objects.filter(id__in=ids).values_list('id', 'outcome_notes'))
    assert notes == {written.id: f'{NOTE}\n\nL', blank.id: 'L', unset.id: 'L'}
