# backend/tests/campaigns/test_reactivate_removed_and_rechase.py
"""
Removal of the standalone Reactivate contact endpoint, and the guard-rail that
protects the CampaignContact.reactivate() MODEL METHOD we deliberately kept.

Two concerns:

(a) The per-contact Reactivate action/route is gone. A POST to the old URL
    (/campaigns/contacts/<pk>/reactivate/) must resolve to 404 — there is no
    such route anymore.

(b) enroll-target still RE-CHASES a contact already present in a final state.
    This is the reason the model method survives: for a TARGETED campaign,
    re-enrolling a COMPLETED/STOPPED contact must flip it back to IN_PROGRESS
    and generate a fresh sequence. Without reactivate(), activities_generated
    stays True and generation becomes a silent no-op (status unchanged, zero
    activities created). If someone deletes the model method later, this test
    turns red.

    Note on activities_generated: reactivate() sets it False, which is what
    ENABLES regeneration — but generate_activities_for_contact re-marks it True
    once the new chain is created. So the False state is transient inside a
    single enroll-target call; the endpoint end-state is IN_PROGRESS with fresh
    activities. The False reset itself is pinned directly on the model method in
    test (c), where it is the observable contract.

Mirrors tests/campaigns/test_campaign_list_attribution.py for the tenant / user
/ account fixtures and tests/campaigns/test_activity_title.py for building a
campaign that drives the real generator. Postgres 5432; planned dates supplied
NOT NULL like the conftest `campaign` fixture.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.campaigns.constants import (
    CampaignContactStatus,
    CampaignStatus,
    CampaignType,
)

ENROLL_URL = '/campaigns/accounts/enroll-target/'


def _reactivate_url(pk):
    return f'/campaigns/contacts/{pk}/reactivate/'


def _active_targeted_campaign(account, user_a):
    """An ACTIVE TARGETED campaign (no sequence_type -> one activity per contact)."""
    from app_modules.campaigns.models import Campaign, CampaignAccount

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


def _reachable_contact(account, user_a):
    from app_modules.contacts.models import Contact

    c = Contact(
        account=account,
        first_name='Bulma',
        last_name='Brief',
        email='bulma@capsule.corp',
    )
    c.save(user=user_a, client_id=account.client_id)
    return c


# =============================================================================
# (a) REMOVED ROUTE — the standalone Reactivate endpoint is gone
# =============================================================================

@pytest.mark.django_db
def test_reactivate_route_removed_returns_404(
    authed_api_a, make_campaign_contact
):
    """POST to the old reactivate URL resolves to 404 — the route no longer exists."""
    cc = make_campaign_contact(status=CampaignContactStatus.COMPLETED)

    resp = authed_api_a.post(_reactivate_url(cc.id), data={}, format='json')

    assert resp.status_code == 404


# =============================================================================
# (b) GUARD-RAIL — enroll-target still re-chases a final-state contact
# =============================================================================

@pytest.mark.django_db
def test_enroll_target_rechases_finished_contact(
    authed_api_a, account, user_a
):
    """
    Re-enrolling a COMPLETED contact on an ACTIVE TARGETED campaign re-chases it:
    status → IN_PROGRESS and a fresh activity is generated. Removing the model
    method (or the re-chase call) makes generation a silent no-op, flipping both
    assertions red.
    """
    from app_modules.campaigns.models import CampaignContact
    from app_modules.activities.models import Activity

    campaign, ca = _active_targeted_campaign(account, user_a)
    contact = _reachable_contact(account, user_a)

    # A contact already finished a previous cycle: COMPLETED, chain already
    # generated (no live Activity rows remain — they were completed/cleared).
    cc = CampaignContact(
        campaign_account=ca,
        contact=contact,
        status=CampaignContactStatus.COMPLETED,
        activities_generated=True,
    )
    cc.save(user=user_a, client_id=account.client_id)

    assert Activity.objects.filter(campaign_contact=cc).count() == 0

    resp = authed_api_a.post(
        ENROLL_URL,
        data={
            'campaign_id': str(campaign.id),
            'account_id': str(account.id),
            'type': 'CONTACT',
            'contact_ids': [str(contact.id)],
        },
        format='json',
    )

    assert resp.status_code == 201, resp.data
    body = resp.data['data']
    # Not a no-op: one contact re-chased, one activity generated.
    assert body['contacts_enrolled'] == 1
    assert body['activities_created'] == 1

    cc.refresh_from_db()
    assert cc.status == CampaignContactStatus.IN_PROGRESS
    # A fresh sequence now exists for the re-chased contact.
    assert Activity.objects.filter(campaign_contact=cc).count() == 1


# =============================================================================
# (c) MODEL METHOD CONTRACT — reactivate() resets the contact for a new cycle
# =============================================================================

@pytest.mark.django_db
def test_model_reactivate_resets_for_new_cycle(
    make_campaign_contact, user_a
):
    """
    The kept model method flips a final-state contact back to IN_PROGRESS and
    clears activities_generated (which is what unblocks regeneration). This is
    the transient reset that enroll-target relies on; pinning it here means
    deleting the method turns this test red immediately.
    """
    cc = make_campaign_contact(
        status=CampaignContactStatus.COMPLETED,
        activities_generated=True,
    )

    result = cc.reactivate(user=user_a)

    cc.refresh_from_db()
    assert cc.status == CampaignContactStatus.IN_PROGRESS
    assert cc.activities_generated is False
    assert result['previous_status'] == CampaignContactStatus.COMPLETED
    assert result['new_status'] == CampaignContactStatus.IN_PROGRESS
