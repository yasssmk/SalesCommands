# backend/tests/campaigns/test_account_status_targeted_revive.py
"""
BUG 1A — a TARGETED CampaignAccount driven to a final state (STOPPED/COMPLETED) by
its contacts' cascade must be re-derived UPWARD to IN_PROGRESS when a contact becomes
active again (re-chase / resume). The revive is TARGETED-only and never resurrects a
genuinely finished account (every contact final) nor any OUTBOUND account.

All journeys are real (stop action / process_result / enroll-target) — status is never
hand-set. Postgres 5432.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.campaigns.constants import (
    CampaignContactStatus, CampaignStatus, CampaignType, CampaignAccountStatus,
)
from app_modules.activities.constants import ActivityStatus
from app_modules.campaigns.services.campaign_execution_service import (
    CampaignExecutionService,
)

ENROLL_URL = "/campaigns/accounts/enroll-target/"
STOP_CONTACT_URL = lambda pk: f"/campaigns/contacts/{pk}/mark-stopped/"
PAUSE_CONTACT_URL = lambda pk: f"/campaigns/contacts/{pk}/pause/"
RESUME_CONTACT_URL = lambda pk: f"/campaigns/contacts/{pk}/resume/"
RESUME_CB_URL = lambda pk: f"/campaigns/contacts/{pk}/resume-callback/"


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
    c = Contact(account=account, first_name=f"Piccolo{n}", last_name="Namek", email=f"p{n}@namek.io")
    c.save(user=user_a, client_id=account.client_id)
    return c


def _enroll(api, campaign, account, contact):
    return api.post(ENROLL_URL, data={"campaign_id": str(campaign.id), "account_id": str(account.id),
                    "type": "CONTACT", "contact_ids": [str(contact.id)], "strict": True}, format="json")


def _svc(user_a, account):
    return CampaignExecutionService(user=user_a, client_id=account.client_id)


@pytest.mark.django_db
class TestAccountRevive:

    # ---- (1) RED→GREEN: re-chase revives the account ---------------------------
    def test_rechase_revives_stopped_account(self, authed_api_a, account, user_a):
        from app_modules.campaigns.models import CampaignContact
        campaign, ca = _campaign(account, user_a, name="T-revive")
        contact = _contact(account, user_a)
        _enroll(authed_api_a, campaign, account, contact)
        cc = CampaignContact.objects.get(campaign_account=ca, contact=contact)

        authed_api_a.post(STOP_CONTACT_URL(cc.id), data={}, format="json")
        ca.refresh_from_db()
        assert ca.status == CampaignAccountStatus.STOPPED  # cascade drove it final

        _enroll(authed_api_a, campaign, account, contact)  # re-chase (Add Target)
        cc.refresh_from_db(); ca.refresh_from_db()
        assert cc.status == CampaignContactStatus.IN_PROGRESS
        assert ca.status == CampaignAccountStatus.IN_PROGRESS  # <-- 1A fix

    # ---- (4) anti-over-correction: all-final account is NOT revived ------------
    def test_all_final_account_not_revived(self, authed_api_a, account, user_a):
        from app_modules.campaigns.models import CampaignContact
        from app_modules.contacts.models import Contact
        campaign, ca = _campaign(account, user_a, name="T-final")
        c1 = _contact(account, user_a, 1)
        c2 = _contact(account, user_a, 2)
        _enroll(authed_api_a, campaign, account, c1)
        _enroll(authed_api_a, campaign, account, c2)

        cc1 = CampaignContact.objects.get(campaign_account=ca, contact=c1)
        cc2 = CampaignContact.objects.get(campaign_account=ca, contact=c2)
        # c1 SUCCESSFUL → COMPLETED ; c2 terminal → STOPPED (real journeys)
        a1 = cc1.activities.filter(status=ActivityStatus.PLANNED).first()
        _svc(user_a, account).process_result(a1, {"outcome": "SUCCESSFUL"})
        cc2.refresh_from_db()
        a2 = cc2.activities.filter(status=ActivityStatus.PLANNED).first()
        if a2:
            _svc(user_a, account).process_result(a2, {"outcome": "NOT_INTERESTED"})
        ca.refresh_from_db()
        assert ca.status in (CampaignAccountStatus.COMPLETED, CampaignAccountStatus.STOPPED)

        # Directly invoke the helper: must NOT revive (no non-final contact).
        result = ca.revive_if_active(user=user_a)
        ca.refresh_from_db()
        assert result is None
        assert ca.status in (CampaignAccountStatus.COMPLETED, CampaignAccountStatus.STOPPED)

    # ---- (5) multi-path invariant: resume paths keep the account active --------
    def test_resume_callback_keeps_account_active(self, authed_api_a, account, user_a):
        from app_modules.campaigns.models import CampaignContact
        campaign, ca = _campaign(account, user_a, name="T-cb")
        contact = _contact(account, user_a)
        _enroll(authed_api_a, campaign, account, contact)
        cc = CampaignContact.objects.get(campaign_account=ca, contact=contact)
        a = cc.activities.filter(status=ActivityStatus.PLANNED).first()
        future = (timezone.now().date() + timedelta(days=3)).isoformat()
        _svc(user_a, account).process_result(a, {"outcome": "CALLBACK_REQUESTED", "callback_date": future})
        cc.refresh_from_db()
        assert cc.status == CampaignContactStatus.CALLBACK_PENDING

        authed_api_a.post(RESUME_CB_URL(cc.id), data={}, format="json")
        cc.refresh_from_db(); ca.refresh_from_db()
        assert cc.status == CampaignContactStatus.IN_PROGRESS
        assert ca.status == CampaignAccountStatus.IN_PROGRESS

    def test_resume_pause_keeps_account_active(self, authed_api_a, account, user_a):
        from app_modules.campaigns.models import CampaignContact
        campaign, ca = _campaign(account, user_a, name="T-pause")
        contact = _contact(account, user_a)
        _enroll(authed_api_a, campaign, account, contact)
        cc = CampaignContact.objects.get(campaign_account=ca, contact=contact)

        authed_api_a.post(PAUSE_CONTACT_URL(cc.id), data={}, format="json")
        cc.refresh_from_db()
        assert cc.status == CampaignContactStatus.ON_HOLD
        authed_api_a.post(RESUME_CONTACT_URL(cc.id), data={}, format="json")
        cc.refresh_from_db(); ca.refresh_from_db()
        assert cc.status == CampaignContactStatus.IN_PROGRESS
        assert ca.status == CampaignAccountStatus.IN_PROGRESS

    # ---- (6) OUTBOUND guard: helper is a strict no-op on OUTBOUND --------------
    def test_outbound_account_never_revived(self, authed_api_a, account, user_a):
        from app_modules.campaigns.models import CampaignContact
        campaign, ca = _campaign(account, user_a, ctype=CampaignType.OUTBOUND, name="O-guard")
        contact = _contact(account, user_a)
        _enroll(authed_api_a, campaign, account, contact)
        cc = CampaignContact.objects.get(campaign_account=ca, contact=contact)
        authed_api_a.post(STOP_CONTACT_URL(cc.id), data={}, format="json")
        ca.refresh_from_db()
        assert ca.status == CampaignAccountStatus.STOPPED

        # Even with an active contact present, an OUTBOUND account must not revive.
        cc.status = CampaignContactStatus.IN_PROGRESS  # force an active contact (guard input only)
        cc.save(user=user_a)
        result = ca.revive_if_active(user=user_a)
        ca.refresh_from_db()
        assert result is None
        assert ca.status == CampaignAccountStatus.STOPPED  # OUTBOUND unchanged
