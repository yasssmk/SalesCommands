# backend/tests/campaigns/test_enroll_contact_only.py
"""
S13 sub-step 4/6 — enroll_target accepts ONLY type=CONTACT.

The ACCOUNT (whole-account) and DEPARTMENT (whole-department) enroll modes are
removed from the endpoint. TARGETED enrollment is strictly contact-by-contact, so
every enrollment goes through the sub-step-2 objective-capture path. A non-CONTACT
request is rejected with a clean business-rule 4xx and creates no rows.

Real endpoint: POST /campaigns/accounts/enroll-target/. Postgres.

Mirrors tests/campaigns/test_reactivate_removed_and_rechase.py for the TARGETED
campaign / enroll-target setup.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.activities.models import Activity
from app_modules.campaigns.constants import CampaignStatus, CampaignType
from app_modules.campaigns.models import Campaign, CampaignAccount, CampaignContact

ENROLL_URL = '/campaigns/accounts/enroll-target/'


def _campaign_only(account, user_a):
    """ACTIVE TARGETED campaign with NO CampaignAccount yet (enroll creates it)."""
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
    return c


def _active_targeted_campaign(account, user_a):
    c = _campaign_only(account, user_a)
    ca = CampaignAccount(campaign=c, account=account)
    ca.save(user=user_a, client_id=account.client_id)
    return c, ca


def _reachable_contact(account, user_a, first='Lead', email='lead@example.io', dept=None):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name=first, last_name='X',
                email=email, standard_department=dept)
    c.save(user=user_a, client_id=account.client_id)
    return c


def _cc_count(campaign):
    return CampaignContact.objects.filter(campaign_account__campaign=campaign).count()


# ---------------------------------------------------------------------------
# RED repro A — ACCOUNT mode rejected, no rows
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_account_mode_rejected(authed_api_a, account, user_a):
    campaign = _campaign_only(account, user_a)
    _reachable_contact(account, user_a)

    resp = authed_api_a.post(
        ENROLL_URL,
        data={'campaign_id': str(campaign.id), 'account_id': str(account.id),
              'type': 'ACCOUNT'},
        format='json',
    )

    assert resp.status_code == 400, resp.data
    assert _cc_count(campaign) == 0
    assert CampaignAccount.objects.filter(campaign=campaign).count() == 0


# ---------------------------------------------------------------------------
# RED repro B — DEPARTMENT mode rejected, no rows
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_department_mode_rejected(authed_api_a, account, user_a):
    from app_modules.core_modules.models.standar_dept import StandardDepartment
    it, _ = StandardDepartment.objects.get_or_create(name='IT')
    campaign = _campaign_only(account, user_a)
    _reachable_contact(account, user_a, dept=it)

    resp = authed_api_a.post(
        ENROLL_URL,
        data={'campaign_id': str(campaign.id), 'account_id': str(account.id),
              'type': 'DEPARTMENT', 'department_id': it.id},
        format='json',
    )

    assert resp.status_code == 400, resp.data
    assert _cc_count(campaign) == 0
    assert CampaignAccount.objects.filter(campaign=campaign).count() == 0


# ---------------------------------------------------------------------------
# CONTACT mode still enrolls contact-by-contact + captures objective (sub-step 2)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_contact_mode_still_enrolls_with_objective(authed_api_a, account, user_a):
    campaign, _ = _active_targeted_campaign(account, user_a)
    contact = _reachable_contact(account, user_a)

    resp = authed_api_a.post(
        ENROLL_URL,
        data={'campaign_id': str(campaign.id), 'account_id': str(account.id),
              'type': 'CONTACT', 'contact_ids': [str(contact.id)],
              'objective': 'Chase the signed quote'},
        format='json',
    )

    assert resp.status_code == 201, resp.data
    acts = list(Activity.objects.filter(campaign=campaign))
    assert acts
    assert all(a.call_to_action == 'Chase the signed quote' for a in acts), \
        [a.call_to_action for a in acts]


# ---------------------------------------------------------------------------
# type omitted → defaults to CONTACT (only the passed contact, not the account)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_missing_type_defaults_to_contact(authed_api_a, account, user_a):
    campaign, _ = _active_targeted_campaign(account, user_a)
    wanted = _reachable_contact(account, user_a, first='Wanted', email='w@example.io')
    _reachable_contact(account, user_a, first='Other', email='o@example.io')

    resp = authed_api_a.post(
        ENROLL_URL,
        data={'campaign_id': str(campaign.id), 'account_id': str(account.id),
              'contact_ids': [str(wanted.id)]},  # no `type`
        format='json',
    )

    assert resp.status_code == 201, resp.data
    enrolled = set(
        CampaignContact.objects.filter(campaign_account__campaign=campaign)
        .values_list('contact_id', flat=True)
    )
    assert enrolled == {wanted.id}, "default must be CONTACT, not whole-account"
