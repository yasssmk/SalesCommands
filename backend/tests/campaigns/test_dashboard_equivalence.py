# backend/tests/campaigns/test_dashboard_equivalence.py
"""
BUSINESS EQUIVALENCE for the dashboard query-reduction fix.

The fix only changed HOW the dashboard counts (one grouped executor aggregate +
shared per-status GROUP BYs), never WHAT it counts. These tests lock that:

- the shared-aggregate dashboard blocks equal the standalone self-computing calls
  (so the optional precomputed params never change a value);
- the derived totals/statuses equal the DIRECT counts the old code used
  (total-accounts / total-activities / completed / stopped), i.e. the value the
  removed separate .count() calls produced;
- the grouped executor stats equal a per-user 5-count reference (the former loop),
  same five numbers, same [owner, executor] order;
- sum(status buckets) == total count (the invariant the dedup relies on), for
  both accounts and activities;
- the standalone `summary` action path (get_summary without params) is unchanged.

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

TODAY = timezone.now().date()

_seq = 0


def _mk_user(email, ca, role):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role, is_active=True)


def _mk_account(owner, ca):
    global _seq
    _seq += 1
    acc = CompanyAccount(company_name=f"Acc{_seq}", has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


@pytest.fixture
def scenario(db, client_account_a, role_individual_a, user_a):
    """A campaign with an owner (user_a) AND a distinct executor, accounts across
    statuses, activities owned by BOTH users (so executor stats are non-zero and
    span >1 account), and 3 objectives."""
    ca = client_account_a
    owner = user_a
    executor = _mk_user("dash-exec@a.test", ca, role_individual_a)

    camp = Campaign(name="Equiv", campaign_type=CampaignType.OUTBOUND, owner=owner,
                    executor=executor, planned_start_date=TODAY,
                    planned_end_date=TODAY + timedelta(days=30))
    camp.save(user=owner, client_id=ca.id)

    statuses = [CampaignAccountStatus.COMPLETED, CampaignAccountStatus.COMPLETED,
                CampaignAccountStatus.IN_PROGRESS, CampaignAccountStatus.PENDING,
                CampaignAccountStatus.STOPPED]
    accts = []
    for st in statuses:
        acc = _mk_account(owner, ca)
        CampaignAccount(campaign=camp, account=acc, status=st).save(user=owner, client_id=ca.id)
        accts.append(acc)

    def _act(atype, status, acc, who, outcome=None):
        a = Activity(title="a", activity_type=atype, status=status, account=acc,
                     owner=who, campaign=camp, scheduled_date=TODAY, outcome=outcome)
        a.save(user=who, client_id=ca.id)

    # owner activities (mixed), incl. a completed MEETING for _count_meetings
    _act(ActivityType.MEETING, ActivityStatus.COMPLETED, accts[0], owner, outcome="SUCCESSFUL")
    _act(ActivityType.CALL, ActivityStatus.COMPLETED, accts[0], owner)
    _act(ActivityType.CALL, ActivityStatus.PLANNED, accts[1], owner)
    _act(ActivityType.CALL, ActivityStatus.ON_HOLD, accts[2], owner)
    # executor activities on TWO distinct accounts (accounts_count must be 2)
    _act(ActivityType.EMAIL, ActivityStatus.COMPLETED, accts[3], executor)
    _act(ActivityType.EMAIL, ActivityStatus.PLANNED, accts[4], executor)
    _act(ActivityType.CALL, ActivityStatus.COMPLETED, accts[3], executor)

    for idx, otype in enumerate([ObjectiveType.MEETINGS, ObjectiveType.DECISION_CYCLES,
                                 ObjectiveType.CONTACTS_REACHED]):
        CampaignObjective(campaign=camp, name=str(otype), objective_type=otype,
                          target_value=10, is_primary=(idx == 0)).save(user=owner, client_id=ca.id)

    return {'ca': ca, 'owner': owner, 'executor': executor, 'campaign': camp, 'accts': accts}


def _svc(scenario):
    return CampaignAnalyticsService(client_id=scenario['ca'].id)


# ---------------------------------------------------------------------------
# Shared-aggregate path == standalone path (optional params never change a value)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSharedEqualsStandalone:

    def test_dashboard_blocks_equal_standalone_calls(self, scenario):
        svc, camp = _svc(scenario), scenario['campaign']
        dash = svc.get_dashboard(camp)

        # Each block computed with the shared buckets must equal the block computed
        # standalone (no params -> the method self-computes the same buckets).
        assert dash['summary'] == svc.get_summary(camp)
        assert dash['accounts'] == svc.get_accounts_breakdown(camp)
        assert dash['activities'] == svc.get_activities_breakdown(camp)
        assert dash['timeline'] == svc.get_timeline_progress(camp)
        assert dash['executors'] == svc.get_executor_performance(camp)


# ---------------------------------------------------------------------------
# Derived totals/statuses == the DIRECT counts the old code used
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDerivedEqualsDirectCounts:

    def test_totals_and_statuses_match_direct_counts(self, scenario):
        svc, camp = _svc(scenario), scenario['campaign']
        acc_qs = CampaignAccount.objects.filter(campaign=camp)
        act_qs = Activity.objects.filter(campaign=camp)

        direct_total_accounts = acc_qs.count()
        direct_total_activities = act_qs.count()
        direct_completed = acc_qs.filter(status=CampaignAccountStatus.COMPLETED).count()
        direct_stopped = acc_qs.filter(status=CampaignAccountStatus.STOPPED).count()

        summary = svc.get_summary(camp)
        assert summary['total_accounts'] == direct_total_accounts
        assert summary['total_activities'] == direct_total_activities
        assert summary['completed_accounts'] == direct_completed
        assert summary['stopped_accounts'] == direct_stopped

        assert svc.get_accounts_breakdown(camp)['totals']['total'] == direct_total_accounts
        assert svc.get_activities_breakdown(camp)['totals']['total'] == direct_total_activities

        # timeline work_progress = (completed + stopped) / total (the old formula).
        expected_work = round(((direct_completed + direct_stopped) / direct_total_accounts) * 100, 1)
        assert svc.get_timeline_progress(camp)['work_progress'] == expected_work


# ---------------------------------------------------------------------------
# Executor grouping == per-user 5-count reference (the former loop)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExecutorGroupingEquivalence:

    def test_grouped_executor_stats_match_per_user_reference(self, scenario):
        svc, camp = _svc(scenario), scenario['campaign']
        owner, executor = scenario['owner'], scenario['executor']

        def _ref(user, role):
            qs = Activity.objects.filter(campaign=camp, owner=user)
            total = qs.count()
            completed = qs.filter(status=ActivityStatus.COMPLETED).count()
            return {
                'user_id': str(user.id),
                'user_name': f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
                'user_email': user.email,
                'role': role,
                'total_activities': total,
                'completed': completed,
                'planned': qs.filter(status=ActivityStatus.PLANNED).count(),
                'on_hold': qs.filter(status=ActivityStatus.ON_HOLD).count(),
                'completion_rate': round((completed / total) * 100, 1) if total > 0 else 0.0,
                'accounts_count': qs.values('account').distinct().count(),
            }

        expected = [_ref(owner, 'OWNER'), _ref(executor, 'EXECUTOR')]
        assert svc.get_executor_performance(camp) == expected
        # sanity: the executor really has non-trivial, multi-account stats.
        assert expected[1]['total_activities'] == 3
        assert expected[1]['accounts_count'] == 2


# ---------------------------------------------------------------------------
# sum(buckets) == total count (the invariant the dedup relies on)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSumBucketsInvariant:

    def test_account_and_activity_buckets_sum_to_total(self, scenario):
        svc, camp = _svc(scenario), scenario['campaign']
        acc_buckets = svc._account_status_counts(camp)
        act_buckets = svc._activity_status_counts(camp)
        assert sum(acc_buckets.values()) == CampaignAccount.objects.filter(campaign=camp).count()
        assert sum(act_buckets.values()) == Activity.objects.filter(campaign=camp).count()


# ---------------------------------------------------------------------------
# Standalone summary action path unchanged
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStandaloneSummaryUnchanged:

    def test_standalone_summary_matches_direct_and_dashboard(self, scenario):
        svc, camp = _svc(scenario), scenario['campaign']
        standalone = svc.get_summary(camp)                 # the /summary action path
        in_dashboard = svc.get_dashboard(camp)['summary']  # the shared-buckets path
        assert standalone == in_dashboard
