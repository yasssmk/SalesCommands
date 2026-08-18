# app_modules/campaigns/services/campaign_analytics_service.py
"""
CampaignAnalyticsService — dashboard KPIs, objective progress, conversion rates.

Responsibilities:
    - Campaign summary (accounts, activities, members stats)
    - Objective progress calculation (wires CampaignObjective.get_current_value)
    - Activity breakdown by status, type, outcome
    - Conversion rates and timeline progress
    - Per-executor performance stats

Follows legacy campaign_analytics_service.py patterns,
simplified for new CampaignAccount pivot architecture.
"""

from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.utils import timezone

from core.logging import get_logger

from app_modules.activities.models import Activity
from app_modules.activities.constants import ActivityType, ActivityStatus
from app_modules.bi import metrics
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle
from app_modules.decision_cycles.services.deal_value_sql import (
    DEAL_VALUE_ALIAS,
    annotate_deal_value,
)

from ..constants import DECISION_CYCLE_OBJECTIVE_TYPES
from ..models import (
    CampaignAccount,
    CampaignAccountStatus,
    CampaignObjective,
    CampaignStatus,
    CampaignType,
    ObjectiveType,
)

logger = get_logger(__name__)


class CampaignAnalyticsService:
    """
    Service for campaign analytics and dashboard data.

    Usage:
        service = CampaignAnalyticsService(client_id=client_id)
        dashboard = service.get_dashboard(campaign)
        summary = service.get_summary(campaign)
    """

    def __init__(self, client_id):
        self.client_id = str(client_id)

    # ======================================================================
    # PUBLIC — FULL DASHBOARD
    # ======================================================================

    def get_dashboard(self, campaign):
        """
        Get complete dashboard data for a campaign.

        Returns:
            dict: {
                'summary': {...},
                'objectives': [...],
                'activities': {...},
                'accounts': {...},
                'timeline': {...},
                'executors': [...],
            }
        """
        logger.info("campaign_dashboard_requested", extra={
            'campaign_id': str(campaign.id),
        })

        # Compute the per-status buckets ONCE and share them across the sub-metrics
        # that each used to recount the same populations (total accounts was counted
        # 3x, total activities 2x). Deriving the totals and the per-status figures
        # from these buckets is value-identical: a GROUP BY partitions every row, so
        # sum(buckets) == count(), and status is a non-null field.
        account_status_counts = self._account_status_counts(campaign)
        activity_status_counts = self._activity_status_counts(campaign)

        return {
            'summary': self.get_summary(campaign, account_status_counts, activity_status_counts),
            'objectives': self.get_objectives_progress(campaign),
            'activities': self.get_activities_breakdown(campaign, activity_status_counts),
            'accounts': self.get_accounts_breakdown(campaign, account_status_counts),
            'timeline': self.get_timeline_progress(campaign, account_status_counts),
            'executors': self.get_executor_performance(campaign),
        }

    # ======================================================================
    # PRIVATE — SHARED PER-STATUS BUCKETS (computed once, reused by the dashboard)
    # ======================================================================

    def _account_status_counts(self, campaign):
        """{status: count} for a campaign's CampaignAccounts in ONE GROUP BY.

        sum(values) == total accounts (status is non-null), so callers derive the
        total and the completed/stopped/... figures from this dict instead of
        recounting the same population.
        """
        return dict(
            CampaignAccount.objects.filter(campaign=campaign)
            .values_list('status')
            .annotate(count=Count('id'))
            .values_list('status', 'count')
        )

    def _activity_status_counts(self, campaign):
        """{status: count} for a campaign's Activities in ONE GROUP BY (same
        contract as _account_status_counts)."""
        return dict(
            Activity.objects.filter(campaign=campaign)
            .values_list('status')
            .annotate(count=Count('id'))
            .values_list('status', 'count')
        )

    # ======================================================================
    # PUBLIC — SUMMARY
    # ======================================================================

    def get_summary(self, campaign, account_status_counts=None, activity_status_counts=None):
        """Get high-level campaign summary.

        account_status_counts / activity_status_counts are the shared per-status
        buckets (_account_status_counts / _activity_status_counts). Standalone
        callers omit them and they are computed here; the dashboard passes them so
        the same populations are not recounted. Deriving the totals/statuses from
        the buckets is value-identical to the former separate counts.
        """
        if account_status_counts is None:
            account_status_counts = self._account_status_counts(campaign)
        if activity_status_counts is None:
            activity_status_counts = self._activity_status_counts(campaign)

        total_accounts = sum(account_status_counts.values())
        total_activities = sum(activity_status_counts.values())
        completed_accounts = account_status_counts.get(CampaignAccountStatus.COMPLETED, 0)
        # stopped reused to derive non_terminal without an extra query.
        stopped_accounts = account_status_counts.get(CampaignAccountStatus.STOPPED, 0)
        completion_rate = 0.0
        if total_accounts > 0:
            completion_rate = round((completed_accounts / total_accounts) * 100, 1)

        today = timezone.now().date()
        days_elapsed = max(0, (today - campaign.planned_start_date).days) if campaign.planned_start_date else 0
        days_remaining = max(0, (campaign.planned_end_date - today).days) if campaign.planned_end_date else 0
        total_days = max(1, (campaign.planned_end_date - campaign.planned_start_date).days) if campaign.planned_start_date and campaign.planned_end_date else 1

        owner = campaign.owner
        executor = campaign.executor

        # Count distinct users: owner + executor (CampaignMember table removed in 0013)
        member_ids = set()
        if owner:
            member_ids.add(owner.id)
        if executor:
            member_ids.add(executor.id)

        # accounts_all_terminal derived from already-fetched counts — no extra query.
        accounts_all_terminal = (
            total_accounts > 0
            and (completed_accounts + stopped_accounts) == total_accounts
        )

        # has_planned_activities: single .exists() — fast index scan.
        has_planned_activities = (
            Activity.objects.filter(
                campaign=campaign,
                status=ActivityStatus.PLANNED,
            ).exists()
            if accounts_all_terminal  # skip if accounts aren't all done anyway
            else True
        )

        completion_eligible = (
            not has_planned_activities
            and accounts_all_terminal
            and campaign.status in (CampaignStatus.ACTIVE, CampaignStatus.PAUSED)
            and campaign.campaign_type != CampaignType.TARGETED
        )

        return {
            'campaign_id': str(campaign.id),
            'name': campaign.name,
            'status': campaign.status,
            'status_display': campaign.get_status_display(),
            'campaign_type': campaign.campaign_type,
            'campaign_type_display': campaign.get_campaign_type_display(),
            'total_accounts': total_accounts,
            'total_activities': total_activities,
            'total_members': len(member_ids),
            'completed_accounts': completed_accounts,
            'stopped_accounts': stopped_accounts,
            'completion_rate': completion_rate,
            'days_elapsed': days_elapsed,
            'days_remaining': days_remaining,
            'total_days': total_days,
            'time_progress': round((days_elapsed / total_days) * 100, 1),
            'completion_eligible': completion_eligible,
            'owner': {
                'id': str(owner.id),
                'full_name': f"{owner.first_name or ''} {owner.last_name or ''}".strip() or owner.email,
            } if owner else None,
            'executor': {
                'id': str(executor.id),
                'full_name': f"{executor.first_name or ''} {executor.last_name or ''}".strip() or executor.email,
            } if executor else None,
        }

    

    # ======================================================================
    # PUBLIC — OBJECTIVES PROGRESS
    # ======================================================================

    def get_objectives_progress(self, campaign):
        """
        Calculate real-time progress for all campaign objectives.

        Wires each ObjectiveType to actual data queries.

        Returns:
            list[dict]: [{
                'id', 'name', 'objective_type', 'target_value',
                'current_value', 'progress_percentage', 'is_primary',
            }]
        """
        objectives = list(CampaignObjective.objects.filter(campaign=campaign))
        # Grouped by data source: one query per distinct source present, never
        # one per objective (was a 1+N loop over _calculate_objective_value).
        values = self.calculate_objective_values(campaign, objectives)
        results = []

        for obj in objectives:
            current_value = values.get(obj.id, 0)
            progress = 0.0
            if obj.target_value and obj.target_value > 0:
                progress = round((current_value / float(obj.target_value)) * 100, 1)

            results.append({
                'id': str(obj.id),
                'name': obj.name,
                'objective_type': obj.objective_type,
                'objective_type_display': obj.get_objective_type_display(),
                'target_value': float(obj.target_value),
                'current_value': current_value,
                'progress_percentage': min(progress, 100.0),
                'is_primary': obj.is_primary,
            })

        return results

    def calculate_objective_values(self, campaign, objectives):
        """Current value for EACH objective of a campaign, grouped by data source.

        Returns the SAME numbers as calling ``_calculate_objective_value(campaign,
        obj)`` per objective, but bounded to ONE query per distinct data SOURCE
        present — never one query per objective:

        - The DecisionCycle family (DECISION_CYCLES / PIPELINE_VALUE /
          REVENUE_WON) collapses into a single conditional aggregate. Campaign
          objectives are computed with ``period=None``, so pipeline_value's date
          anchor is inert; the three metrics reduce to a count plus two filtered
          sums over the campaign's cycles, identical to the per-metric formulas
          (``metrics.decision_cycles`` / ``pipeline_value`` / ``revenue_won``).
        - MEETINGS / CONTACTS_REACHED / NEW_LOGOS each keep their own single
          query (distinct populations that cannot be merged), reusing the same
          per-campaign helpers ``_calculate_objective_value`` dispatches to.

        Only the sources actually present among ``objectives`` are queried, so
        the query count is bounded by the number of distinct sources (<= 4),
        independent of the number of objectives. Unmapped types resolve to 0,
        mirroring ``_calculate_objective_value``'s default.

        Args:
            campaign: the campaign whose objectives are valued.
            objectives: an iterable of its CampaignObjective rows (already loaded).

        Returns:
            dict: {objective_id: current_value}.
        """
        present_types = {obj.objective_type for obj in objectives}
        value_by_type = {}

        # DecisionCycle family — one conditional aggregate for the up-to-three
        # cycle-based metrics present (count + two filtered sums).
        if present_types & DECISION_CYCLE_OBJECTIVE_TYPES:
            # Amounts are the DERIVED product roll-up (TD-75), summed off the
            # per-cycle annotation rather than a deal_products JOIN: a join
            # would multiply each cycle row by its line count and inflate
            # dc_count. The annotation is one scalar subquery per cycle, so the
            # count stays exact.
            agg = (
                annotate_deal_value(
                    DecisionCycle.objects
                    .filter(client_id=self.client_id, source_campaign=campaign)
                )
                .aggregate(
                    dc_count=Count('id'),
                    pipeline=Sum(DEAL_VALUE_ALIAS, filter=Q(outcome__isnull=True)),
                    revenue=Sum(DEAL_VALUE_ALIAS, filter=Q(outcome=CycleOutcome.WON)),
                )
            )
            value_by_type[ObjectiveType.DECISION_CYCLES] = agg['dc_count'] or 0
            value_by_type[ObjectiveType.PIPELINE_VALUE] = float(agg['pipeline'] or 0)
            value_by_type[ObjectiveType.REVENUE_WON] = float(agg['revenue'] or 0)

        # Activity / CampaignAccount sources — distinct populations, one query
        # each, reusing the existing per-campaign helpers.
        if ObjectiveType.MEETINGS in present_types:
            value_by_type[ObjectiveType.MEETINGS] = self._count_meetings(campaign)
        if ObjectiveType.CONTACTS_REACHED in present_types:
            value_by_type[ObjectiveType.CONTACTS_REACHED] = self._count_contacts_reached(campaign)
        if ObjectiveType.NEW_LOGOS in present_types:
            value_by_type[ObjectiveType.NEW_LOGOS] = self._count_new_logos(campaign)

        return {obj.id: value_by_type.get(obj.objective_type, 0) for obj in objectives}

    # ======================================================================
    # PUBLIC — ACTIVITIES BREAKDOWN
    # ======================================================================

    def get_activities_breakdown(self, campaign, activity_status_counts=None):
        """
        Activity stats grouped by status, type, and outcome.

        Returns:
            dict: {
                'by_status': {PLANNED: n, COMPLETED: n, CANCELLED: n},
                'by_type': {CALL: n, EMAIL: n, MEETING: n, ...},
                'by_outcome': {SUCCESSFUL: n, NO_ANSWER: n, ...},
                'totals': {total, completed, planned, cancelled, completion_rate},
            }
        """
        base_qs = Activity.objects.filter(campaign=campaign)

        # By status — reuse the shared buckets when the dashboard provides them.
        status_agg = (
            activity_status_counts if activity_status_counts is not None
            else dict(
                base_qs.values_list('status')
                .annotate(count=Count('id'))
                .values_list('status', 'count')
            )
        )

        # By type
        type_agg = dict(
            base_qs.values_list('activity_type')
            .annotate(count=Count('id'))
            .values_list('activity_type', 'count')
        )

        # By outcome (completed only)
        outcome_agg = dict(
            base_qs.filter(status=ActivityStatus.COMPLETED)
            .exclude(outcome__isnull=True)
            .values_list('outcome')
            .annotate(count=Count('id'))
            .values_list('outcome', 'count')
        )

        total = sum(status_agg.values())
        completed = status_agg.get(ActivityStatus.COMPLETED, 0)
        planned = status_agg.get(ActivityStatus.PLANNED, 0)
        on_hold = status_agg.get(ActivityStatus.ON_HOLD, 0)
        cancelled = status_agg.get(ActivityStatus.CANCELLED, 0)

        return {
            'by_status': status_agg,
            'by_type': type_agg,
            'by_outcome': outcome_agg,
            'totals': {
                'total': total,
                'completed': completed,
                'planned': planned,
                'on_hold': on_hold,
                'cancelled': cancelled,
                'completion_rate': round((completed / total) * 100, 1) if total > 0 else 0.0,
            },
        }


    # ======================================================================
    # PUBLIC — ACCOUNTS BREAKDOWN
    # ======================================================================

    def get_accounts_breakdown(self, campaign, account_status_counts=None):
        """
        Account stats grouped by status.

        Returns:
            dict: {
                'by_status': {PENDING: n, IN_PROGRESS: n, ...},
                'totals': {total, active, completed, stopped},
                'conversion_rate': float,
            }
        """
        # Reuse the shared buckets when the dashboard provides them.
        status_agg = (
            account_status_counts if account_status_counts is not None
            else self._account_status_counts(campaign)
        )

        total = sum(status_agg.values())
        completed = status_agg.get(CampaignAccountStatus.COMPLETED, 0)
        stopped = status_agg.get(CampaignAccountStatus.STOPPED, 0)
        in_progress = status_agg.get(CampaignAccountStatus.IN_PROGRESS, 0)
        pending = status_agg.get(CampaignAccountStatus.PENDING, 0)

        # Conversion: completed / (completed + stopped) — accounts that went through
        touched = completed + stopped
        conversion_rate = round((completed / touched) * 100, 1) if touched > 0 else 0.0

        return {
            'by_status': status_agg,
            'totals': {
                'total': total,
                'pending': pending,
                'active': in_progress,
                'completed': completed,
                'stopped': stopped,
            },
            'conversion_rate': conversion_rate,
        }

    # ======================================================================
    # PUBLIC — TIMELINE PROGRESS
    # ======================================================================

    def get_timeline_progress(self, campaign, account_status_counts=None):
        """
        Timeline progress: time elapsed vs work completed.

        Returns:
            dict: {
                'start_date', 'end_date',
                'days_elapsed', 'days_remaining', 'total_days',
                'time_progress': float (0-100),
                'work_progress': float (0-100),
                'on_track': bool,
            }
        """
        today = timezone.now().date()

        start = campaign.planned_start_date
        end = campaign.planned_end_date
        total_days = max(1, (end - start).days) if start and end else 1
        days_elapsed = max(0, (today - start).days) if start else 0
        days_remaining = max(0, (end - today).days) if end else 0

        time_progress = round((days_elapsed / total_days) * 100, 1)

        # Work progress: (completed + stopped) accounts / total accounts, derived
        # from the shared per-status buckets (value-identical to the former counts).
        if account_status_counts is None:
            account_status_counts = self._account_status_counts(campaign)
        total_accounts = sum(account_status_counts.values())
        completed_accounts = (
            account_status_counts.get(CampaignAccountStatus.COMPLETED, 0)
            + account_status_counts.get(CampaignAccountStatus.STOPPED, 0)
        )
        work_progress = round((completed_accounts / total_accounts) * 100, 1) if total_accounts > 0 else 0.0

        # On track: work progress >= time progress (with 10% tolerance)
        on_track = work_progress >= (time_progress - 10)

        return {
            'planned_start_date': start.isoformat() if start else None,
            'planned_end_date': end.isoformat() if end else None,
            'actual_start_date': campaign.actual_start_date.isoformat() if campaign.actual_start_date else None,
            'actual_end_date': campaign.actual_end_date.isoformat() if campaign.actual_end_date else None,
            'days_elapsed': days_elapsed,
            'days_remaining': days_remaining,
            'total_days': total_days,
            'time_progress': min(time_progress, 100.0),
            'work_progress': min(work_progress, 100.0),
            'on_track': on_track,
        }

    # ======================================================================
    # PUBLIC — EXECUTOR PERFORMANCE
    # ======================================================================

    def get_executor_performance(self, campaign):
        """Per-executor activity stats — owner and executor only.

        Was a 5-.count()-per-user loop (an N+1 in the number of executors). Now
        ONE conditional aggregate grouped by owner yields the same five figures for
        both users at once; the two User rows (names/emails) load in one in_bulk
        query. Account is a non-null FK, so Count('account', distinct=True) equals
        the former values('account').distinct().count(). Values are unchanged; the
        [owner, executor] order and the "always a row per non-null user (zeros when
        no activity)" behaviour are preserved.
        """
        # owner_id / executor_id are FK columns — read without loading the users.
        pairs = [(campaign.owner_id, 'OWNER'), (campaign.executor_id, 'EXECUTOR')]
        user_ids = [uid for uid, _ in pairs if uid]
        if not user_ids:
            return []

        rows = (
            Activity.objects.filter(campaign=campaign, owner_id__in=user_ids)
            .values('owner')
            .annotate(
                total=Count('id'),
                completed=Count('id', filter=Q(status=ActivityStatus.COMPLETED)),
                planned=Count('id', filter=Q(status=ActivityStatus.PLANNED)),
                on_hold=Count('id', filter=Q(status=ActivityStatus.ON_HOLD)),
                accounts_count=Count('account', distinct=True),
            )
        )
        by_owner = {r['owner']: r for r in rows}

        from end_users.models import User
        users = User.objects.in_bulk(user_ids)

        results = []
        for uid, role in pairs:
            user = users.get(uid) if uid else None
            if user is None:
                continue
            stats = by_owner.get(uid, {})
            total = stats.get('total', 0)
            completed = stats.get('completed', 0)
            results.append({
                'user_id': str(user.id),
                'user_name': f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
                'user_email': user.email,
                'role': role,
                'total_activities': total,
                'completed': completed,
                'planned': stats.get('planned', 0),
                'on_hold': stats.get('on_hold', 0),
                'completion_rate': round((completed / total) * 100, 1) if total > 0 else 0.0,
                'accounts_count': stats.get('accounts_count', 0),
            })

        return results

    # ======================================================================
    # PRIVATE — OBJECTIVE VALUE CALCULATION
    # ======================================================================

    def _calculate_objective_value(self, campaign, objective):
        """
        Calculate current value for a specific objective type.

        Maps each ObjectiveType to a concrete query on campaign data.
        """
        obj_type = objective.objective_type

        if obj_type == ObjectiveType.MEETINGS:
            return self._count_meetings(campaign)

        elif obj_type == ObjectiveType.CONTACTS_REACHED:
            return self._count_contacts_reached(campaign)

        elif obj_type == ObjectiveType.DECISION_CYCLES:
            return self._count_decision_cycles(campaign)

        elif obj_type == ObjectiveType.PIPELINE_VALUE:
            return self._sum_pipeline_value(campaign)

        elif obj_type == ObjectiveType.REVENUE_WON:
            return self._sum_revenue_won(campaign)

        elif obj_type == ObjectiveType.NEW_LOGOS:
            return self._count_new_logos(campaign)

        return 0

    def _count_meetings(self, campaign):
        """MEETINGS: completed MEETING activities attributed to the campaign.

        A completed MEETING is "from the campaign" through any of THREE origins
        (``Activity.decision_cycle`` and ``source_activity`` are both nullable,
        so no single field is enough):
        - its decision cycle of origin (``decision_cycle.source_campaign`` — the
          modal sets the cycle but leaves ``Activity.campaign`` None), OR
        - directly via ``Activity.campaign`` (a campaign meeting with no cycle),
          OR
        - the campaign activity it was born from
          (``source_activity.campaign`` — a meeting logged on a PRE-EXISTING
          cycle that never got ``source_campaign``, but whose triggering sequence
          activity carries the campaign).

        Each side is an ISOLATED correlated EXISTS (correlated by
        ``decision_cycle_id`` / ``source_activity_id``); both traversals are
        to-one, so counting activities never fans out. A meeting matching several
        origins is a single Activity row, counted once. A null cycle / source
        activity simply makes that EXISTS false — no error.

        NOTE: this widens ACTIVITY attribution only. The cycle metrics
        (DECISION_CYCLES / PIPELINE_VALUE / REVENUE_WON) still attribute by the
        cycle's OWN ``source_campaign`` and are unaffected.
        """
        cycle_in_campaign = DecisionCycle.objects.filter(
            pk=OuterRef('decision_cycle_id'),
            source_campaign=campaign,
        )
        source_in_campaign = Activity.objects.filter(
            pk=OuterRef('source_activity_id'),
            campaign=campaign,
        )
        return (
            Activity.objects
            .filter(
                activity_type=ActivityType.MEETING,
                status=ActivityStatus.COMPLETED,
            )
            .annotate(
                _cycle_in_campaign=Exists(cycle_in_campaign),
                _source_in_campaign=Exists(source_in_campaign),
            )
            .filter(
                Q(campaign=campaign)
                | Q(_cycle_in_campaign=True)
                | Q(_source_in_campaign=True)
            )
            .count()
        )

    def _count_contacts_reached(self, campaign):
        """CONTACTS_REACHED: distinct contacts with at least one completed activity."""
        return Activity.objects.filter(
            campaign=campaign,
            status=ActivityStatus.COMPLETED,
        ).values('contacts').distinct().count()

    def _dc_base_queryset(self):
        """Tenant-bounded DecisionCycle queryset for the canonical metric formulas.

        The pure ``bi/metrics`` functions expect a base queryset the caller has
        already bounded to the tenant; they only narrow it further (here by
        ``source_campaign``). Bounding on ``client_id`` keeps that contract.
        """
        return DecisionCycle.objects.filter(client_id=self.client_id)

    def _count_decision_cycles(self, campaign):
        """DECISION_CYCLES: decision cycles whose ``source_campaign`` is this campaign.

        Attribution is the DC's OWN ``source_campaign`` (the campaign that
        generated the cycle), not whether a campaign activity happens to point at
        it — same definition as the personal objective, via the canonical
        formula. ``period=None`` keeps the campaign's all-time count.
        """
        return metrics.decision_cycles(
            self._dc_base_queryset(), source_campaign=campaign, period=None
        )

    def _sum_pipeline_value(self, campaign):
        """PIPELINE_VALUE: Σ total_deal_value of OPEN cycles attributed to the
        campaign via ``DecisionCycle.source_campaign`` (canonical formula)."""
        return metrics.pipeline_value(
            self._dc_base_queryset(), source_campaign=campaign, period=None
        )

    def _sum_revenue_won(self, campaign):
        """REVENUE_WON: Σ total_deal_value of WON cycles attributed to the campaign
        via ``DecisionCycle.source_campaign`` (canonical formula)."""
        return metrics.revenue_won(
            self._dc_base_queryset(), source_campaign=campaign, period=None
        )

    def _count_new_logos(self, campaign):
        """
        NEW_LOGOS: accounts that transitioned from PROSPECT to CLIENT.

        MVP: count completed CampaignAccounts where account.type changed.
        Simplified — full tracking requires event sourcing in future.
        """
        return CampaignAccount.objects.filter(
            campaign=campaign,
            status=CampaignAccountStatus.COMPLETED,
            account__type='CLIENT',
        ).count()