# backend/tests/campaigns/test_sequence_run.py
"""
BUG 1 — chasing "run" stamping so the completed accordion shows only the current run.

CampaignContact.sequence_run is a per-contact counter (starts at 1, +1 on reactivate);
each generated Activity is stamped with the contact's run at creation and never changed.
The completed endpoint filters ?current_run=true to keep only the current run (orphan-safe),
while previous runs stay in the DB.

Real journeys only (enroll-target / process_result). Postgres 5432.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.campaigns.constants import (
    CampaignStatus, CampaignType, CampaignAccountStatus, CampaignContactStatus,
)
from app_modules.activities.constants import ActivityStatus
from app_modules.campaigns.services.campaign_execution_service import (
    CampaignExecutionService,
)

ENROLL_URL = "/campaigns/accounts/enroll-target/"
ACTS_URL = "/module-activities/"


def _campaign(account, user_a, ctype=CampaignType.TARGETED, name="C"):
    from app_modules.campaigns.models import Campaign, CampaignAccount
    today = timezone.now().date()
    c = Campaign(name=name, campaign_type=ctype, status=CampaignStatus.ACTIVE, owner=user_a,
                 planned_start_date=today, planned_end_date=today + timedelta(days=30),
                 actual_start_date=today)
    c.save(user=user_a, client_id=account.client_id)
    ca = CampaignAccount(campaign=c, account=account, status=CampaignAccountStatus.IN_PROGRESS)
    ca.save(user=user_a, client_id=account.client_id)
    return c, ca


def _contact(account, user_a, n=1):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name=f"Trunks{n}", last_name="Brief", email=f"t{n}@ci.io")
    c.save(user=user_a, client_id=account.client_id)
    return c


def _enroll(api, campaign, account, contact):
    return api.post(ENROLL_URL, data={"campaign_id": str(campaign.id), "account_id": str(account.id),
                    "type": "CONTACT", "contact_ids": [str(contact.id)], "strict": True}, format="json")


def _svc(user_a, account):
    return CampaignExecutionService(user=user_a, client_id=account.client_id)


def _planned(cc):
    from app_modules.activities.models import Activity
    return Activity.objects.filter(campaign_contact=cc, status=ActivityStatus.PLANNED).first()


def _completed_ids(api, campaign_id, current_run=True, active_sequence=False):
    """Return the activity IDs the completed endpoint yields under the given filters."""
    url = f"{ACTS_URL}?campaign={campaign_id}&status=COMPLETED&page_size=50"
    if current_run:
        url += "&current_run=true"
    if active_sequence:
        url += "&active_sequence=true"
    resp = api.get(url)
    data = resp.data.get("data", resp.data)
    rows = data.get("results", data if isinstance(data, list) else [])
    return [r["id"] for r in rows]


def _runs_for(ids):
    """sequence_run values (from the DB, the source of truth) for the given activity IDs."""
    from app_modules.activities.models import Activity
    return sorted(
        Activity.objects.filter(id__in=ids).values_list("sequence_run", flat=True)
    )


def _run_two_targeted(authed_api_a, account, user_a):
    """Enroll, complete run 1 (NO_ANSWER exhausted → COMPLETED), re-chase, complete run 2."""
    from app_modules.campaigns.models import CampaignContact
    campaign, ca = _campaign(account, user_a, name="T-run")
    contact = _contact(account, user_a)
    _enroll(authed_api_a, campaign, account, contact)
    cc = CampaignContact.objects.get(campaign_account=ca, contact=contact)

    _svc(user_a, account).process_result(_planned(cc), {"outcome": "NO_ANSWER"})  # run 1 → COMPLETED
    cc.refresh_from_db()
    _enroll(authed_api_a, campaign, account, contact)  # re-chase → run 2
    cc.refresh_from_db()
    _svc(user_a, account).process_result(_planned(cc), {"outcome": "NO_ANSWER"})  # run 2 → COMPLETED
    cc.refresh_from_db()
    return campaign, ca, contact, cc


@pytest.mark.django_db
class TestSequenceRun:

    def test_completed_shows_only_current_run(self, authed_api_a, account, user_a):
        """RED before fix (no current_run filter → 2 rows). GREEN: only run 2."""
        campaign, ca, contact, cc = _run_two_targeted(authed_api_a, account, user_a)
        assert cc.sequence_run == 2

        ids = _completed_ids(authed_api_a, campaign.id, current_run=True)
        assert _runs_for(ids) == [2], "completed endpoint must return only the current run"

    def test_previous_run_persists_in_db(self, authed_api_a, account, user_a):
        """Memory guarantee: run-1 activities are NOT deleted — only hidden."""
        from app_modules.activities.models import Activity
        campaign, ca, contact, cc = _run_two_targeted(authed_api_a, account, user_a)

        all_completed = Activity.objects.filter(
            campaign_contact=cc, status=ActivityStatus.COMPLETED
        )
        runs = sorted(all_completed.values_list("sequence_run", flat=True))
        assert runs == [1, 2], f"both runs must remain in DB, got {runs}"

    def test_new_activities_stamped_incremented_run(self, authed_api_a, account, user_a):
        """Order increment→stamp + immutability: run-1 rows keep run=1, run-2 rows get run=2."""
        from app_modules.activities.models import Activity
        campaign, ca, contact, cc = _run_two_targeted(authed_api_a, account, user_a)

        by_run = {}
        for a in Activity.objects.filter(campaign_contact=cc):
            by_run.setdefault(a.sequence_run, []).append(a)
        assert set(by_run) == {1, 2}
        # position 1 exists in BOTH runs (the coexisting "step 1" of BUG 1), each immutable.
        assert all(a.sequence_position == 1 for a in by_run[1])
        assert all(a.sequence_position == 1 for a in by_run[2])

    def test_followup_stamped_current_run(self, authed_api_a, account, user_a):
        """_create_followup stamps the contact's current run."""
        from app_modules.campaigns.models import CampaignContact
        from app_modules.activities.models import Activity
        campaign, ca = _campaign(account, user_a, name="T-cb")
        contact = _contact(account, user_a)
        _enroll(authed_api_a, campaign, account, contact)
        cc = CampaignContact.objects.get(campaign_account=ca, contact=contact)
        future = (timezone.now().date() + timedelta(days=3)).isoformat()
        _svc(user_a, account).process_result(
            _planned(cc), {"outcome": "CALLBACK_REQUESTED", "callback_date": future}
        )
        followup = Activity.objects.filter(
            campaign_contact=cc, is_callback_followup=True
        ).first()
        assert followup is not None
        assert followup.sequence_run == cc.sequence_run == 1

    def test_outbound_current_run_keeps_all(self, authed_api_a, account, user_a):
        """OUTBOUND never re-chases: run stays 1, current_run=true keeps every completed."""
        from app_modules.campaigns.models import CampaignContact
        campaign, ca = _campaign(account, user_a, ctype=CampaignType.OUTBOUND, name="O-run")
        contact = _contact(account, user_a)
        _enroll(authed_api_a, campaign, account, contact)
        cc = CampaignContact.objects.get(campaign_account=ca, contact=contact)
        _svc(user_a, account).process_result(_planned(cc), {"outcome": "NO_ANSWER"})
        cc.refresh_from_db()
        assert cc.sequence_run == 1

        ids = _completed_ids(authed_api_a, campaign.id, current_run=True)
        assert _runs_for(ids) == [1]  # kept — run 1, filter neutral on OUTBOUND

    def test_cohabitation_with_active_sequence(self, authed_api_a, account, user_a):
        """active_sequence + current_run combine without contradiction on TARGETED.
        After run 2 the contact is COMPLETED (final) → active_sequence=true drops it,
        current_run=true would keep only run 2. Combined → empty (final contact)."""
        campaign, ca, contact, cc = _run_two_targeted(authed_api_a, account, user_a)
        # Contact is final → active_sequence drops all its rows; combined with
        # current_run there is no contradiction/error, just an empty set.
        ids = _completed_ids(authed_api_a, campaign.id, current_run=True, active_sequence=True)
        assert ids == []
