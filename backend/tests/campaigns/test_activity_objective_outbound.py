# backend/tests/campaigns/test_activity_objective_outbound.py
"""
S13 sub-step 1/6 — Campaign-level activity objective + OUTBOUND propagation.

An OUTBOUND campaign carries an optional free-text ``activity_objective``. When
its activities are generated (at start()), each generated Activity's
``call_to_action`` is populated from that campaign objective — this is the
OUTBOUND source of the unified "Activity Objective".

The primary test drives the REAL lifecycle path:
    CampaignLifecycleService.start()
      -> CampaignExecutionService.generate_activities()
        -> _generate_for_account -> _extract_contacts
          -> generate_activities_for_contact -> _create_activity

Precedence (in _create_activity): existing per-step
``step_config['call_to_action']`` wins if present; else
``campaign.activity_objective``; else None.

Real generation path, Postgres.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.activities.constants import ActivityType
from app_modules.activities.models import Activity
from app_modules.campaigns.constants import (
    CampaignType, CampaignStatus, CampaignAccountStatus, CampaignContactStatus,
    ObjectiveType,
)
from app_modules.campaigns.models import Campaign, CampaignAccount, CampaignContact
from app_modules.campaigns.services.campaign_execution_service import CampaignExecutionService
from app_modules.campaigns.services.campaign_lifecycle_service import CampaignLifecycleService
from app_modules.contacts.models import Contact

CREATE_URL = '/campaigns/'


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _reachable_contact(account, user_a, email="lead@example.io"):
    """A contact with a real channel so _extract_contacts keeps it."""
    c = Contact(account=account, first_name="Lead", last_name="X", email=email)
    c.save(user=user_a, client_id=account.client_id)
    return c


def _outbound_draft(user_a, client_id, *, activity_objective=None):
    """OUTBOUND DRAFT campaign, no sequence_type (1 CALL activity per contact)."""
    today = timezone.now().date()
    c = Campaign(
        name='Q3 Outbound',
        campaign_type=CampaignType.OUTBOUND,
        status=CampaignStatus.DRAFT,
        owner=user_a,
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
        activity_objective=activity_objective,
    )
    c.save(user=user_a, client_id=client_id)
    return c


def _preenroll(campaign, account, contact, user_a):
    """
    Mirror the post-territory-enrollment state OUTBOUND produces: a PENDING
    CampaignAccount + PENDING CampaignContact. start() then cascades both to
    IN_PROGRESS and generates activities.
    """
    ca = CampaignAccount(
        campaign=campaign, account=account,
        status=CampaignAccountStatus.PENDING,
    )
    ca.save(user=user_a, client_id=account.client_id)
    cc = CampaignContact(
        campaign_account=ca, contact=contact,
        status=CampaignContactStatus.PENDING,
    )
    cc.save(user=user_a, client_id=account.client_id)
    return ca, cc


# ---------------------------------------------------------------------------
# RED repro — real start() path
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_outbound_objective_carried_to_generated_activities(account, user_a, client_account_a):
    """
    OUTBOUND campaign.activity_objective propagates onto every generated
    Activity.call_to_action, through the real start() lifecycle path.
    """
    campaign = _outbound_draft(
        user_a, client_account_a.id, activity_objective="Book a discovery call",
    )
    contact = _reachable_contact(account, user_a)
    _preenroll(campaign, account, contact, user_a)

    CampaignLifecycleService(user=user_a, client_id=client_account_a.id).start(campaign)

    acts = list(Activity.objects.filter(campaign=campaign))
    assert acts, "start() should have generated at least one activity"
    assert all(a.call_to_action == "Book a discovery call" for a in acts), \
        [a.call_to_action for a in acts]


@pytest.mark.django_db
def test_outbound_objective_absent_leaves_cta_none(account, user_a, client_account_a):
    """No activity_objective → generated activities keep call_to_action = None."""
    campaign = _outbound_draft(user_a, client_account_a.id, activity_objective=None)
    contact = _reachable_contact(account, user_a)
    _preenroll(campaign, account, contact, user_a)

    CampaignLifecycleService(user=user_a, client_id=client_account_a.id).start(campaign)

    acts = list(Activity.objects.filter(campaign=campaign))
    assert acts, "start() should have generated at least one activity"
    assert all(a.call_to_action is None for a in acts), \
        [a.call_to_action for a in acts]


# ---------------------------------------------------------------------------
# precedence — step_config['call_to_action'] wins over campaign objective
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_step_config_call_to_action_wins_over_campaign_objective(account, user_a, client_account_a):
    """
    When a sequence step_config carries its own call_to_action, it takes
    precedence over the campaign-level activity_objective.
    """
    campaign = _outbound_draft(
        user_a, client_account_a.id, activity_objective="Campaign objective",
    )
    ca = CampaignAccount(
        campaign=campaign, account=account,
        status=CampaignAccountStatus.IN_PROGRESS,
    )
    ca.save(user=user_a, client_id=account.client_id)
    contact = _reachable_contact(account, user_a)
    cc = CampaignContact(
        campaign_account=ca, contact=contact,
        status=CampaignContactStatus.IN_PROGRESS,
    )
    cc.save(user=user_a, client_id=account.client_id)

    svc = CampaignExecutionService(user=user_a, client_id=client_account_a.id)
    activity = svc._create_activity(
        campaign=campaign,
        campaign_account=ca,
        campaign_contact=cc,
        account=account,
        contact=contact,
        activity_type=ActivityType.CALL,
        position=1,
        step_config={'type': ActivityType.CALL, 'call_to_action': 'Step-level CTA'},
    )

    assert activity.call_to_action == 'Step-level CTA'


# ---------------------------------------------------------------------------
# non-regression — the KPI `objective` DictField path is untouched
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_kpi_objective_dict_still_creates_objective_row(authed_api_a, user_a, client_account_a):
    """
    The existing CampaignObjective KPI input (`objective` dict) still creates a
    CampaignObjective row, and `activity_objective` is a separate free-text field.
    """
    from app_modules.campaigns.models import CampaignObjective
    from app_modules.territories.models import Territory

    # OUTBOUND campaigns require a territory — create a permissive one.
    territory = Territory(name='All Tenant', owner=user_a, filter_definition={})
    territory.save(user=user_a, client_id=client_account_a.id)

    today = timezone.now().date()
    resp = authed_api_a.post(
        CREATE_URL,
        data={
            'name': 'Outbound With Objective',
            'campaign_type': CampaignType.OUTBOUND,
            'territory_ids': [str(territory.id)],
            'start_date': str(today),
            'end_date': str(today + timedelta(days=30)),
            'activity_objective': 'Book a discovery call',
            'objective': {
                'objective_type': ObjectiveType.MEETINGS,
                'target_value': 10,
                'is_primary': True,
            },
        },
        format='json',
    )
    assert resp.status_code in (200, 201), resp.data

    campaign = Campaign.objects.get(name='Outbound With Objective')
    assert campaign.activity_objective == 'Book a discovery call'
    assert CampaignObjective.objects.filter(
        campaign=campaign, objective_type=ObjectiveType.MEETINGS,
    ).exists()
