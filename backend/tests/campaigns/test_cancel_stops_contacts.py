# backend/tests/campaigns/test_cancel_stops_contacts.py
"""
Cancelling a campaign must stop every still-active contact (product-locked rule):

  - Non-terminal contact (PENDING / IN_PROGRESS / ON_HOLD / CALLBACK_PENDING)
    -> STOPPED.
  - Terminal contact (COMPLETED / STOPPED) -> left untouched.

This exercises the SHARED cancel path (CampaignLifecycleService.cancel), which
backs both the manual cancel endpoint and cancellation via user deactivation.
Postgres 5432.
"""
import pytest

from app_modules.campaigns.constants import CampaignContactStatus
from app_modules.campaigns.models import CampaignContact
from app_modules.campaigns.services.campaign_lifecycle_service import (
    CampaignLifecycleService,
)


NON_TERMINAL = [
    CampaignContactStatus.PENDING,
    CampaignContactStatus.IN_PROGRESS,
    CampaignContactStatus.ON_HOLD,
    CampaignContactStatus.CALLBACK_PENDING,
]


@pytest.mark.django_db
def test_cancel_stops_all_non_terminal_contacts(
    client_account_a, user_a, campaign, make_campaign_contact
):
    contacts = [make_campaign_contact(status=s) for s in NON_TERMINAL]

    CampaignLifecycleService(user=user_a, client_id=client_account_a.id).cancel(campaign)

    for cc in contacts:
        cc.refresh_from_db()
        assert cc.status == CampaignContactStatus.STOPPED, (
            f"{cc.status} contact not stopped on cancel"
        )


@pytest.mark.django_db
def test_cancel_leaves_terminal_contacts_untouched(
    client_account_a, user_a, campaign, make_campaign_contact
):
    completed = make_campaign_contact(status=CampaignContactStatus.COMPLETED)
    stopped = make_campaign_contact(status=CampaignContactStatus.STOPPED)
    stopped_notes = stopped.notes

    CampaignLifecycleService(user=user_a, client_id=client_account_a.id).cancel(campaign)

    completed.refresh_from_db()
    stopped.refresh_from_db()
    assert completed.status == CampaignContactStatus.COMPLETED  # not flipped
    assert stopped.status == CampaignContactStatus.STOPPED
    assert stopped.notes == stopped_notes  # terminal notes not clobbered


@pytest.mark.django_db
def test_cancelled_campaign_has_no_active_contact(
    client_account_a, user_a, campaign, make_campaign_contact
):
    for s in NON_TERMINAL:
        make_campaign_contact(status=s)
    make_campaign_contact(status=CampaignContactStatus.COMPLETED)

    CampaignLifecycleService(user=user_a, client_id=client_account_a.id).cancel(campaign)

    from app_modules.campaigns.constants import FINAL_CONTACT_STATES
    remaining_active = CampaignContact.objects.filter(
        campaign_account__campaign=campaign,
    ).exclude(status__in=FINAL_CONTACT_STATES)
    assert remaining_active.count() == 0


@pytest.mark.django_db
def test_cancel_does_not_touch_another_campaigns_contacts(
    client_account_a, user_a, account, campaign, make_campaign_contact
):
    # Cancelling one campaign must leave a different campaign's contacts alone
    # (the stop is scoped to campaign_account__campaign).
    from datetime import timedelta
    from django.utils import timezone
    from app_modules.campaigns.models import Campaign, CampaignAccount, CampaignContact
    from app_modules.campaigns.constants import CampaignType
    from app_modules.contacts.models import Contact

    mine = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)

    today = timezone.now().date()
    other_camp = Campaign(
        name='Other Outbound', campaign_type=CampaignType.OUTBOUND, owner=user_a,
        planned_start_date=today, planned_end_date=today + timedelta(days=30),
    )
    other_camp.save(user=user_a, client_id=client_account_a.id)
    other_ca = CampaignAccount(campaign=other_camp, account=account)
    other_ca.save(user=user_a, client_id=client_account_a.id)
    other_contact = Contact(account=account, first_name='Other', last_name='Test')
    other_contact.save(user=user_a, client_id=client_account_a.id)
    other_cc = CampaignContact(
        campaign_account=other_ca, contact=other_contact,
        status=CampaignContactStatus.IN_PROGRESS,
    )
    other_cc.save(user=user_a, client_id=client_account_a.id)

    CampaignLifecycleService(user=user_a, client_id=client_account_a.id).cancel(campaign)

    mine.refresh_from_db()
    other_cc.refresh_from_db()
    assert mine.status == CampaignContactStatus.STOPPED          # cancelled campaign
    assert other_cc.status == CampaignContactStatus.IN_PROGRESS  # untouched
