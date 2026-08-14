# backend/tests/campaigns/test_objectives_grouped_equivalence.py
"""
BUSINESS EQUIVALENCE — the grouped objective-value calculation returns the exact
same numbers as the per-objective source of truth.

``CampaignAnalyticsService.calculate_objective_values`` groups the objective
current-values by data source (one query per source, not one per objective). It
must never change a single business value: for every ObjectiveType, its result
must equal ``_calculate_objective_value(campaign, objective)`` — the untouched
per-objective method the detail/list/model callers still use.

This locks the two paths together so the N+1 fix stays a pure performance change.

DB: Postgres.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.accounts.models import CompanyAccount
from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.campaigns.constants import (
    CampaignAccountStatus,
    CampaignType,
    ObjectiveType,
)
from app_modules.campaigns.models import Campaign, CampaignAccount, CampaignObjective
from app_modules.campaigns.services.campaign_analytics_service import (
    CampaignAnalyticsService,
)
from app_modules.contacts.models import Contact
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle

TODAY = timezone.now().date()


def _seed_all_types(user, ca):
    """A campaign carrying ALL six objective types, with data that makes each
    current value NON-ZERO and distinct, so equivalence is not a trivial 0 == 0.
    """
    camp = Campaign(
        name="Equiv",
        campaign_type=CampaignType.OUTBOUND,
        owner=user,
        executor=user,
        planned_start_date=TODAY,
        planned_end_date=TODAY + timedelta(days=30),
    )
    camp.save(user=user, client_id=ca.id)

    # A CLIENT account with a COMPLETED CampaignAccount -> NEW_LOGOS = 1.
    client_acc = CompanyAccount(
        company_name="ClientCo", has_buying_decision=True, account_owner=user, type="CLIENT"
    )
    client_acc.save(user=user, client_id=ca.id)
    other_acc = CompanyAccount(
        company_name="ProspectCo", has_buying_decision=True, account_owner=user
    )
    other_acc.save(user=user, client_id=ca.id)
    CampaignAccount(
        campaign=camp, account=client_acc, status=CampaignAccountStatus.COMPLETED
    ).save(user=user, client_id=ca.id)

    # A completed campaign MEETING -> MEETINGS = 1.
    Activity(
        title="meeting",
        activity_type=ActivityType.MEETING,
        status=ActivityStatus.COMPLETED,
        outcome="SUCCESSFUL",
        account=client_acc,
        owner=user,
        campaign=camp,
        scheduled_date=TODAY,
    ).save(user=user, client_id=ca.id)

    # A completed campaign activity carrying a contact -> CONTACTS_REACHED >= 1.
    contact = Contact(account=client_acc, first_name="Reached", last_name="Contact")
    contact.save(user=user, client_id=ca.id)
    reached = Activity(
        title="call",
        activity_type=ActivityType.CALL,
        status=ActivityStatus.COMPLETED,
        account=client_acc,
        owner=user,
        campaign=camp,
        scheduled_date=TODAY,
    )
    reached.save(user=user, client_id=ca.id)
    reached.contacts.add(contact)

    # Decision cycles of origin: 2 open (PIPELINE_VALUE = 1500 + 500 = 2000),
    # 1 won (REVENUE_WON = 900); DECISION_CYCLES = 3 (all cycles of the campaign).
    DecisionCycle(
        account=other_acc, owner=user, name="open-a",
        source_campaign=camp, estimated_value=1500,
    ).save(user=user, client_id=ca.id)
    DecisionCycle(
        account=other_acc, owner=user, name="open-b",
        source_campaign=camp, estimated_value=500,
    ).save(user=user, client_id=ca.id)
    DecisionCycle(
        account=other_acc, owner=user, name="won",
        source_campaign=camp, estimated_value=900,
        outcome=CycleOutcome.WON, outcome_date=TODAY,
    ).save(user=user, client_id=ca.id)

    for idx, otype in enumerate(ObjectiveType.values):
        CampaignObjective(
            campaign=camp, name=str(otype), objective_type=otype,
            target_value=10, is_primary=(idx == 0),
        ).save(user=user, client_id=ca.id)

    return camp


@pytest.mark.django_db
class TestGroupedObjectiveValuesEquivalence:

    def test_grouped_equals_per_objective_for_all_six_types(
        self, user_a, client_account_a
    ):
        camp = _seed_all_types(user_a, client_account_a)
        svc = CampaignAnalyticsService(client_id=client_account_a.id)
        objectives = list(CampaignObjective.objects.filter(campaign=camp))
        assert len(objectives) == 6  # one per ObjectiveType

        grouped = svc.calculate_objective_values(camp, objectives)

        # Every objective's grouped value must equal the per-objective source of
        # truth (the untouched _calculate_objective_value the other callers use).
        for obj in objectives:
            reference = svc._calculate_objective_value(camp, obj)
            assert grouped[obj.id] == reference, (
                f"{obj.objective_type}: grouped {grouped[obj.id]} != "
                f"reference {reference}"
            )

        # And the reference values are genuinely non-zero / distinct (so the
        # equivalence above is meaningful, not 0 == 0 everywhere).
        by_type = {
            obj.objective_type: grouped[obj.id] for obj in objectives
        }
        assert by_type[ObjectiveType.DECISION_CYCLES] == 3
        assert by_type[ObjectiveType.PIPELINE_VALUE] == 2000.0
        assert by_type[ObjectiveType.REVENUE_WON] == 900.0
        assert by_type[ObjectiveType.MEETINGS] == 1
        assert by_type[ObjectiveType.NEW_LOGOS] == 1
        assert by_type[ObjectiveType.CONTACTS_REACHED] >= 1

    def test_get_objectives_progress_matches_reference(
        self, user_a, client_account_a
    ):
        """End-to-end (path a/b): the values surfaced by get_objectives_progress
        equal the per-objective reference calculation."""
        camp = _seed_all_types(user_a, client_account_a)
        svc = CampaignAnalyticsService(client_id=client_account_a.id)
        # get_objectives_progress serializes ids as str, so key by str too.
        objectives = {
            str(o.id): o for o in CampaignObjective.objects.filter(campaign=camp)
        }

        for row in svc.get_objectives_progress(camp):
            obj = objectives[row["id"]]
            reference = float(svc._calculate_objective_value(camp, obj) or 0)
            assert float(row["current_value"]) == reference
