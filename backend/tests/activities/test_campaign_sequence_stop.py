# backend/tests/activities/test_campaign_sequence_stop.py
"""
Sprint Next steps 5.14a -- the campaign sequence stops on EVERY path (PO
rule: a SUCCESSFUL or terminal outcome ends the prospect's chasing sequence).

Before 5.14a only process_result (POST /complete/ on a PLANNED step, the
playlist's log-response, record-no-answer) applied it. Two paths wrote a
final outcome and left the sequence running:
  * POST /module-activities/{id}/complete/ on an ALREADY COMPLETED step
    (views.py, "If already completed, just update outcome fields") -- the
    campaign "Log Response" (CampaignOutcomeModal, mode A: the prospect
    answers an email already sent);
  * PATCH /module-activities/{id}/ (ActivityUpdateSerializer: status /
    outcome).
The ONE place now: a post_save on Activity (the pre_save snapshot pattern of
decision_cycles/signals/readiness_recompute.py), calling
CampaignExecutionService.apply_final_outcome -- extracted from
_handle_outcome; process_result no longer does that part itself (no double
run). Idempotent. Respects are_signals_disabled().
PO: an outcome changed after a final one is accepted on the activity, with
no transition of the prospect, no 500 -- logged.
"""

import logging
from unittest import mock

import pytest

from app_modules.activities.constants import ActivityStatus
from app_modules.activities.models import Activity
from tests.activities.test_next_planned_step import _activity, _days, _get, chain  # noqa: F401


pytestmark = pytest.mark.django_db


def _in_progress(a):
    from app_modules.campaigns.models import CampaignAccount, CampaignContact
    CampaignContact.objects.filter(id=a.campaign_contact_id).update(status='IN_PROGRESS')
    CampaignAccount.objects.filter(id=a.campaign_account_id).update(status='IN_PROGRESS')


def _contact_status(a):
    from app_modules.campaigns.models import CampaignContact
    return CampaignContact.objects.get(id=a.campaign_contact_id).status


def _open_steps(a):
    return Activity.objects.filter(
        campaign_contact_id=a.campaign_contact_id,
        status__in=[ActivityStatus.PLANNED, ActivityStatus.ON_HOLD],
    ).count()


def _complete(api, a, outcome):
    r = api.post(f'/module-activities/{a.id}/complete/', {'outcome': outcome}, format='json')
    assert r.status_code == 200, r.content
    return r


def _patch(api, a, data):
    r = api.patch(f'/module-activities/{a.id}/', data, format='json')
    assert r.status_code == 200, r.content
    return r


@pytest.fixture
def emailed(chain):
    """Step 1 (the email) already COMPLETED, no answer yet; steps 2-3 open."""
    s1 = chain(1, ActivityStatus.COMPLETED, _days(-2))
    chain(2, date=_days(1))
    chain(3, date=_days(4))
    _in_progress(s1)
    return s1


# --- the paths that used to leave the sequence running ----------------------

def test_log_response_on_a_completed_step_stops_the_sequence(authed_api_a, emailed):
    """CampaignOutcomeModal mode A -> /complete/ on an already COMPLETED step."""
    _complete(authed_api_a, emailed, 'SUCCESSFUL')
    assert _open_steps(emailed) == 0
    assert _contact_status(emailed) == 'COMPLETED'
    assert _get(authed_api_a, emailed)['next_planned_step'] is None


def test_log_response_terminal_outcome_stops_the_prospect(authed_api_a, emailed):
    _complete(authed_api_a, emailed, 'NOT_INTERESTED')
    assert _open_steps(emailed) == 0
    assert _contact_status(emailed) == 'STOPPED'


def test_patch_status_and_outcome_stops_the_sequence(authed_api_a, chain):
    s1 = chain(1, date=_days(0)); chain(2, date=_days(3))
    _in_progress(s1)
    _patch(authed_api_a, s1, {'status': 'COMPLETED', 'outcome': 'MEETING_SCHEDULED'})
    assert _open_steps(s1) == 0
    assert _contact_status(s1) == 'COMPLETED'


def test_patch_outcome_on_a_completed_step_stops_the_sequence(authed_api_a, emailed):
    _patch(authed_api_a, emailed, {'outcome': 'SUCCESSFUL'})
    assert _open_steps(emailed) == 0
    assert _contact_status(emailed) == 'COMPLETED'


# --- the path that already worked: unchanged, run ONCE ------------------------

def test_the_planned_path_still_stops_and_runs_the_final_outcome_once(authed_api_a, chain):
    from app_modules.campaigns.services.campaign_execution_service import CampaignExecutionService
    s1 = chain(1, date=_days(0)); chain(2, date=_days(3))
    _in_progress(s1)
    real = CampaignExecutionService.apply_final_outcome
    with mock.patch.object(CampaignExecutionService, 'apply_final_outcome', autospec=True,
                           side_effect=real) as spy:
        _complete(authed_api_a, s1, 'SUCCESSFUL')
    assert spy.call_count == 1
    assert _open_steps(s1) == 0
    assert _contact_status(s1) == 'COMPLETED'


def test_a_non_final_outcome_keeps_the_sequence(authed_api_a, emailed):
    _complete(authed_api_a, emailed, 'FOLLOW_UP_NEEDED')
    assert _open_steps(emailed) == 2
    assert _contact_status(emailed) == 'IN_PROGRESS'


# --- idempotence ---------------------------------------------------------------

def test_idempotent_a_second_call_breaks_nothing(authed_api_a, emailed, user_a):
    from app_modules.campaigns.services.campaign_execution_service import CampaignExecutionService
    _complete(authed_api_a, emailed, 'SUCCESSFUL')
    emailed.refresh_from_db()
    service = CampaignExecutionService(user=user_a, client_id=emailed.client_id)
    service.apply_final_outcome(emailed)
    service.apply_final_outcome(emailed)
    assert _open_steps(emailed) == 0
    assert _contact_status(emailed) == 'COMPLETED'


def test_resaving_the_activity_does_not_rerun_it(authed_api_a, emailed):
    from app_modules.campaigns.services.campaign_execution_service import CampaignExecutionService
    _complete(authed_api_a, emailed, 'SUCCESSFUL')
    with mock.patch.object(CampaignExecutionService, 'apply_final_outcome') as spy:
        _patch(authed_api_a, emailed, {'title': 'Cold email — renamed'})
    assert spy.call_count == 0


# --- PO: an outcome changed after a final one ---------------------------------

def test_outcome_changed_after_a_final_one_no_transition_no_500_logged(authed_api_a, emailed, caplog):
    _complete(authed_api_a, emailed, 'SUCCESSFUL')
    with caplog.at_level(logging.WARNING):
        _complete(authed_api_a, emailed, 'NOT_INTERESTED')
    emailed.refresh_from_db()
    assert emailed.outcome == 'NOT_INTERESTED'
    assert _contact_status(emailed) == 'COMPLETED'
    assert any(r.getMessage() == 'campaign_final_outcome_changed_no_transition'
               for r in caplog.records)


# --- scope ---------------------------------------------------------------------

def test_respects_are_signals_disabled(emailed, user_a):
    from core.cache_utils import disable_signals
    with disable_signals():
        emailed.outcome = 'SUCCESSFUL'
        emailed.save(user=user_a)
    assert _open_steps(emailed) == 2
    assert _contact_status(emailed) == 'IN_PROGRESS'


def test_an_activity_outside_a_campaign_is_untouched(authed_api_a, account, user_a):
    a = _activity(account, user_a, 'Standalone call', date=_days(0))
    _complete(authed_api_a, a, 'SUCCESSFUL')
    a.refresh_from_db()
    assert a.status == ActivityStatus.COMPLETED and a.outcome == 'SUCCESSFUL'


# --- the data command (existing orphan sequences) ----------------------------

def _orphan(step, user, outcome='SUCCESSFUL'):
    """The pre-5.14a state: a final outcome written, the sequence left open
    (written with the signals off, as the old outcome-only update did)."""
    from core.cache_utils import disable_signals
    with disable_signals():
        step.outcome = outcome
        step.save(user=user)


def _run(*args):
    from io import StringIO
    from django.core.management import call_command
    out = StringIO()
    call_command('stop_orphan_campaign_sequences', *args, stdout=out)
    return out.getvalue()


def test_command_dry_run_lists_per_tenant_and_writes_nothing(emailed, user_a):
    _orphan(emailed, user_a)
    out = _run('--dry-run')
    assert 'DRY RUN' in out
    assert f'Tenant {emailed.client_id}' in out
    assert f'prospect {emailed.campaign_contact_id} (IN_PROGRESS)' in out
    assert out.count('would delete: ') == 2
    assert '1 prospect(s) found' in out
    assert _open_steps(emailed) == 2
    assert _contact_status(emailed) == 'IN_PROGRESS'


def test_command_stops_the_orphan_sequences_then_finds_nothing(emailed, user_a):
    _orphan(emailed, user_a, 'NOT_INTERESTED')
    out = _run()
    assert '1 stopped, 0 not applied' in out
    assert _open_steps(emailed) == 0
    assert _contact_status(emailed) == 'STOPPED'
    assert 'No campaign sequence to stop.' in _run()


def test_command_leaves_a_running_sequence_alone(emailed):
    """No final outcome: nothing found."""
    assert 'No campaign sequence to stop.' in _run('--dry-run')
    assert _open_steps(emailed) == 2


def test_command_client_id_filter(emailed, user_a, client_account_b):
    _orphan(emailed, user_a)
    assert 'No campaign sequence to stop.' in _run('--dry-run', '--client-id', str(client_account_b.id))
    assert '1 prospect(s) found' in _run('--dry-run', '--client-id', str(emailed.client_id))
