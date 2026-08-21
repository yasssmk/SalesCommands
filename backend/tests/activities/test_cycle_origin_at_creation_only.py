# backend/tests/activities/test_cycle_origin_at_creation_only.py
"""
A DecisionCycle's ORIGIN is set when it is created, never by an activity later.

``DecisionCycle.source_campaign`` answers "which campaign created this deal", and
it is the sole basis of the DECISION_CYCLES campaign objective. It used to be
written by a BACKFILL in ``ActivityCreationService.create_with_entities``, which
ran whenever an activity born from a campaign pointed at a cycle — including a
cycle that already existed and had nothing to do with that campaign. Two
consequences the PO reported:

  * a PRE-EXISTING deal silently became "created by" a campaign that merely
    touched it, inflating that campaign's DECISION_CYCLES count;
  * it happened at activity CREATION, before anyone had completed anything.

The origin now comes from the creation path only: when the modal creates a NEW
inline cycle while working a campaign activity, that cycle is genuinely born from
the campaign and is stamped at construction. A cycle that already exists is never
re-parented.

This is the ONLY behaviour that changes here. Campaign VALUE does not depend on
``source_campaign`` at all any more (campaign_dc_attribution: money requires a
COMPLETED + SUCCESSFUL activity of the campaign), so a touched pre-existing deal
still contributes to that campaign's pipeline — through work, not through a
re-written origin.

Harness mirrors tests/activities/test_create_with_entities_inline_cycle.py (same
endpoint, same authed client, same modal-shaped payload).
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status

from app_modules.activities.constants import (
    ActivityOutcome, ActivityStatus, ActivityType,
)
from app_modules.activities.models import Activity
from app_modules.campaigns.constants import CampaignType
from app_modules.campaigns.models import Campaign
from app_modules.decision_cycles.constants import PipelineStep
from app_modules.decision_cycles.models import DecisionCycle, DecisionStep


_URL = '/module-activities/create-with-entities/'
TODAY = timezone.now().date()


def _campaign(owner, ca, name='Camp'):
    c = Campaign(name=name, campaign_type=CampaignType.OUTBOUND, owner=owner,
                 executor=owner, planned_start_date=TODAY,
                 planned_end_date=TODAY + timedelta(days=30))
    c.save(user=owner, client_id=ca.id)
    return c


def _campaign_activity(owner, account, ca, campaign):
    """The sequence activity a follow-up is created FROM."""
    a = Activity(title='seed', activity_type=ActivityType.CALL,
                 status=ActivityStatus.COMPLETED,
                 outcome=ActivityOutcome.SUCCESSFUL,
                 account=account, owner=owner, campaign=campaign,
                 scheduled_date=TODAY)
    a.save(user=owner, client_id=ca.id)
    return a


def _cycle(owner, account, ca, *, name='existing', source_campaign=None):
    """A pre-existing cycle WITH its qualification step — the endpoint refuses
    to link an activity to a cycle without naming a step."""
    dc = DecisionCycle(account=account, owner=owner, name=name,
                       source_campaign=source_campaign)
    dc.save(user=owner, client_id=ca.id)
    step = DecisionStep(cycle=dc, name='Qualification',
                        stage=PipelineStep.QUALIFICATION, order=1)
    step.save(user=owner, client_id=ca.id)
    return dc


def _base_activity(account, **extra):
    payload = {
        'title': 'Follow-up',
        'activity_type': ActivityType.CALL,
        'status': ActivityStatus.PLANNED,
        'account_id': str(account.id),
        'contact_ids': [],
    }
    payload.update(extra)
    return payload


@pytest.mark.django_db
class TestAnActivityNeverRewritesAnExistingCycleOrigin:

    def test_a_campaign_follow_up_does_not_adopt_an_untagged_cycle(
        self, authed_api_a, account, user_a, client_account_a,
    ):
        """THE regression: an existing deal with no origin stays without one."""
        campaign = _campaign(user_a, client_account_a, name='B')
        seed = _campaign_activity(user_a, account, client_account_a, campaign)
        cycle = _cycle(user_a, account, client_account_a, source_campaign=None)
        step = cycle.steps.get(stage=PipelineStep.QUALIFICATION)

        resp = authed_api_a.post(_URL, {
            'activity': _base_activity(
                account,
                decision_cycle_id=str(cycle.id),
                decision_step_id=str(step.id),
                source_activity_id=str(seed.id),
            ),
        }, format='json')

        assert resp.status_code == status.HTTP_201_CREATED, resp.content

        cycle.refresh_from_db()
        assert cycle.source_campaign_id is None

    def test_a_campaign_follow_up_does_not_steal_a_cycle_from_another_campaign(
        self, authed_api_a, account, user_a, client_account_a,
    ):
        camp_a = _campaign(user_a, client_account_a, name='A')
        camp_b = _campaign(user_a, client_account_a, name='B')
        seed = _campaign_activity(user_a, account, client_account_a, camp_b)
        cycle = _cycle(user_a, account, client_account_a, source_campaign=camp_a)
        step = cycle.steps.get(stage=PipelineStep.QUALIFICATION)

        resp = authed_api_a.post(_URL, {
            'activity': _base_activity(
                account,
                decision_cycle_id=str(cycle.id),
                decision_step_id=str(step.id),
                source_activity_id=str(seed.id),
            ),
        }, format='json')

        assert resp.status_code == status.HTTP_201_CREATED, resp.content

        cycle.refresh_from_db()
        assert cycle.source_campaign_id == camp_a.id


@pytest.mark.django_db
class TestACycleCreatedFromACampaignIsBornFromIt:

    def test_an_inline_cycle_created_from_a_campaign_activity_carries_the_origin(
        self, authed_api_a, account, user_a, client_account_a,
    ):
        """The legitimate half of the old backfill, kept: a cycle that did not
        exist before this campaign activity IS the campaign's creation."""
        campaign = _campaign(user_a, client_account_a, name='B')
        seed = _campaign_activity(user_a, account, client_account_a, campaign)

        resp = authed_api_a.post(_URL, {
            'activity': _base_activity(account, source_activity_id=str(seed.id)),
            'inline_cycle': {'name': 'Born from B', 'description': None},
            'inline_step_stage': 'QUALIFICATION',
        }, format='json')

        assert resp.status_code == status.HTTP_201_CREATED, resp.content

        cycle = DecisionCycle.objects.get(account=account, name='Born from B')
        assert cycle.source_campaign_id == campaign.id

    def test_an_inline_cycle_created_outside_any_campaign_has_no_origin(
        self, authed_api_a, account,
    ):
        resp = authed_api_a.post(_URL, {
            'activity': _base_activity(account),
            'inline_cycle': {'name': 'Born alone', 'description': None},
            'inline_step_stage': 'QUALIFICATION',
        }, format='json')

        assert resp.status_code == status.HTTP_201_CREATED, resp.content

        cycle = DecisionCycle.objects.get(account=account, name='Born alone')
        assert cycle.source_campaign_id is None

    def test_an_inline_cycle_from_an_activity_with_no_campaign_has_no_origin(
        self, authed_api_a, account, user_a, client_account_a,
    ):
        """The source activity exists but carries no campaign — nothing to
        inherit."""
        seed = Activity(title='plain', activity_type=ActivityType.CALL,
                        status=ActivityStatus.COMPLETED, account=account,
                        owner=user_a, scheduled_date=TODAY)
        seed.save(user=user_a, client_id=client_account_a.id)

        resp = authed_api_a.post(_URL, {
            'activity': _base_activity(account, source_activity_id=str(seed.id)),
            'inline_cycle': {'name': 'No campaign', 'description': None},
            'inline_step_stage': 'QUALIFICATION',
        }, format='json')

        assert resp.status_code == status.HTTP_201_CREATED, resp.content

        cycle = DecisionCycle.objects.get(account=account, name='No campaign')
        assert cycle.source_campaign_id is None
