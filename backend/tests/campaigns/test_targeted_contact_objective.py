# backend/tests/campaigns/test_targeted_contact_objective.py
"""
S13 sub-step 2/6 — per-contact TARGETED objective + TD-145 closure.

A TARGETED contact carries its OWN per-run ``objective``, entered at enrollment
via the existing enroll-target endpoint. It populates the generated activity's
``call_to_action``. The CTA STOPS reading ``campaign_account.notes`` (the
double-purpose status-journal field), so the parasitic "Stopped: …" text can no
longer leak into an active activity's CTA (TD-145).

The objective is jetable per run: reactivate() nulls it, and each enrollment call
re-enters it.

Real endpoint path: POST /campaigns/accounts/enroll-target/  →
generate_activities_for_contact → _create_activity. Postgres.

Mirrors tests/campaigns/test_reactivate_removed_and_rechase.py for the TARGETED
campaign / enroll-target / re-chase setup.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.activities.models import Activity
from app_modules.campaigns.constants import (
    CampaignContactStatus, CampaignStatus, CampaignType,
)
from app_modules.campaigns.models import Campaign, CampaignAccount, CampaignContact

ENROLL_URL = '/campaigns/accounts/enroll-target/'


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _active_targeted_campaign(account, user_a):
    """ACTIVE TARGETED campaign, no sequence_type -> one activity per contact."""
    today = timezone.now().date()
    c = Campaign(
        name='Warm Targets',
        campaign_type=CampaignType.TARGETED,
        status=CampaignStatus.ACTIVE,
        owner=user_a,
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
        actual_start_date=today,
    )
    c.save(user=user_a, client_id=account.client_id)
    ca = CampaignAccount(campaign=c, account=account)
    ca.save(user=user_a, client_id=account.client_id)
    return c, ca


def _reachable_contact(account, user_a, email='lead@example.io'):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name='Lead', last_name='X', email=email)
    c.save(user=user_a, client_id=account.client_id)
    return c


def _enroll(api, campaign, account, contact, *, objective=None):
    data = {
        'campaign_id': str(campaign.id),
        'account_id': str(account.id),
        'type': 'CONTACT',
        'contact_ids': [str(contact.id)],
    }
    if objective is not None:
        data['objective'] = objective
    return api.post(ENROLL_URL, data=data, format='json')


# ---------------------------------------------------------------------------
# RED repro A — feature: objective carried to the activity
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_targeted_objective_carried_to_activity(authed_api_a, account, user_a):
    """enroll-target with an objective → generated activity.call_to_action == it."""
    campaign, ca = _active_targeted_campaign(account, user_a)
    contact = _reachable_contact(account, user_a)

    resp = _enroll(authed_api_a, campaign, account, contact,
                   objective="Chase the signed quote")
    assert resp.status_code == 201, resp.data

    acts = list(Activity.objects.filter(campaign=campaign))
    assert acts, "enrollment should have generated an activity"
    assert all(a.call_to_action == "Chase the signed quote" for a in acts), \
        [a.call_to_action for a in acts]


# ---------------------------------------------------------------------------
# RED repro B — TD-145: status text must NOT leak into the re-chased CTA
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_rechase_objective_not_poisoned_by_account_notes(authed_api_a, account, user_a):
    """
    A previous cycle left "Stopped: …" in campaign_account.notes. Re-chasing the
    contact with a NEW objective must populate the fresh activity's CTA from the
    contact objective — never the account status journal.
    """
    campaign, ca = _active_targeted_campaign(account, user_a)
    contact = _reachable_contact(account, user_a)

    # Previous run finished; the account status journal holds a "Stopped: …" note.
    ca.mark_stopped(reason="previous deal lost", user=user_a)
    ca.refresh_from_db()
    assert ca.notes and ca.notes.startswith("Stopped")

    # A finished contact from the previous cycle (no live activities), carrying a
    # stale objective that must also not survive the re-chase.
    cc = CampaignContact(
        campaign_account=ca,
        contact=contact,
        status=CampaignContactStatus.STOPPED,
        activities_generated=True,
        objective="Old objective",
    )
    cc.save(user=user_a, client_id=account.client_id)

    resp = _enroll(authed_api_a, campaign, account, contact,
                   objective="Re-open conversation")
    assert resp.status_code == 201, resp.data

    cc.refresh_from_db()
    acts = list(Activity.objects.filter(campaign_contact=cc))
    assert acts, "re-chase should have generated a fresh activity"
    for a in acts:
        assert a.call_to_action == "Re-open conversation", a.call_to_action
        assert "Stopped" not in (a.call_to_action or ""), a.call_to_action


# ---------------------------------------------------------------------------
# objective absent → CTA None
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_targeted_objective_absent_leaves_cta_none(authed_api_a, account, user_a):
    """No objective at enrollment → generated activity keeps call_to_action None."""
    campaign, ca = _active_targeted_campaign(account, user_a)
    contact = _reachable_contact(account, user_a)

    resp = _enroll(authed_api_a, campaign, account, contact, objective=None)
    assert resp.status_code == 201, resp.data

    acts = list(Activity.objects.filter(campaign=campaign))
    assert acts
    assert all(a.call_to_action is None for a in acts), [a.call_to_action for a in acts]


# ---------------------------------------------------------------------------
# re-chase WITHOUT a new objective → CTA None (jetable per run)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_rechase_without_objective_resets_to_none(authed_api_a, account, user_a):
    """
    reactivate() nulls the objective. Re-chasing WITHOUT a new objective yields
    a fresh activity whose CTA is None — never the previous run's value nor the
    account status text.
    """
    campaign, ca = _active_targeted_campaign(account, user_a)
    contact = _reachable_contact(account, user_a)
    ca.mark_stopped(reason="lost", user=user_a)

    cc = CampaignContact(
        campaign_account=ca,
        contact=contact,
        status=CampaignContactStatus.STOPPED,
        activities_generated=True,
        objective="Old objective",
    )
    cc.save(user=user_a, client_id=account.client_id)

    resp = _enroll(authed_api_a, campaign, account, contact, objective=None)
    assert resp.status_code == 201, resp.data

    cc.refresh_from_db()
    assert cc.objective is None
    acts = list(Activity.objects.filter(campaign_contact=cc))
    assert acts
    assert all(a.call_to_action is None for a in acts), [a.call_to_action for a in acts]


# ---------------------------------------------------------------------------
# non-regression — campaign_account.notes still works as the status journal
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_account_notes_still_status_journal(account, user_a):
    """mark_stopped still writes the status journal into campaign_account.notes."""
    campaign, ca = _active_targeted_campaign(account, user_a)

    ca.mark_stopped(reason="deal lost", user=user_a)

    ca.refresh_from_db()
    assert ca.notes == "Stopped: deal lost"
    assert ca.status == 'STOPPED'


# ---------------------------------------------------------------------------
# reactivate() model contract — objective is reset alongside notes
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_reactivate_nulls_objective(make_campaign_contact, user_a):
    """The kept model method resets objective to None (jetable per run)."""
    cc = make_campaign_contact(
        status=CampaignContactStatus.COMPLETED,
        activities_generated=True,
        objective="Should not survive",
    )

    cc.reactivate(user=user_a)

    cc.refresh_from_db()
    assert cc.objective is None
