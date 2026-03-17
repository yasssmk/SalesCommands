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

from django.db.models import Count, Q, Sum, F, Value, CharField
from django.db.models.functions import Coalesce
from django.utils import timezone
from decimal import Decimal

from core.logging import get_logger
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignModuleErrorMessages

from app_modules.activities.models import Activity
from app_modules.activities.constants import ActivityType, ActivityStatus, ActivityOutcome

from ..models import (
    Campaign,
    CampaignAccount,
    CampaignAccountStatus,
    CampaignObjective,
    ObjectiveType,
)
from ..config.settings import CONFIG

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

        return {
            'summary': self.get_summary(campaign),
            'objectives': self.get_objectives_progress(campaign),
            'activities': self.get_activities_breakdown(campaign),
            'accounts': self.get_accounts_breakdown(campaign),
            'timeline': self.get_timeline_progress(campaign),
            'executors': self.get_executor_performance(campaign),
        }

    # ======================================================================
    # PUBLIC — SUMMARY
    # ======================================================================

    def get_summary(self, campaign):
        """Get high-level campaign summary."""
        total_accounts = CampaignAccount.objects.filter(campaign=campaign).count()
        total_activities = Activity.objects.filter(campaign=campaign).count()

        completed_accounts = CampaignAccount.objects.filter(
            campaign=campaign,
            status=CampaignAccountStatus.COMPLETED,
        ).count()
        completion_rate = 0.0
        if total_accounts > 0:
            completion_rate = round((completed_accounts / total_accounts) * 100, 1)

        today = timezone.now().date()
        days_elapsed = max(0, (today - campaign.planned_start_date).days) if campaign.planned_start_date else 0
        days_remaining = max(0, (campaign.planned_end_date - today).days) if campaign.planned_end_date else 0
        total_days = max(1, (campaign.planned_end_date - campaign.planned_start_date).days) if campaign.planned_start_date and campaign.planned_end_date else 1

        owner = campaign.owner
        executor = campaign.executor

        return {
            'campaign_id': str(campaign.id),
            'name': campaign.name,
            'status': campaign.status,
            'status_display': campaign.get_status_display(),
            'campaign_type': campaign.campaign_type,
            'campaign_type_display': campaign.get_campaign_type_display(),
            'total_accounts': total_accounts,
            'total_activities': total_activities,
            'total_members': 2 if executor else 1,
            'completed_accounts': completed_accounts,
            'completion_rate': completion_rate,
            'days_elapsed': days_elapsed,
            'days_remaining': days_remaining,
            'total_days': total_days,
            'time_progress': round((days_elapsed / total_days) * 100, 1),
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
        objectives = CampaignObjective.objects.filter(campaign=campaign)
        results = []

        for obj in objectives:
            current_value = self._calculate_objective_value(campaign, obj)
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

    # ======================================================================
    # PUBLIC — ACTIVITIES BREAKDOWN
    # ======================================================================

    def get_activities_breakdown(self, campaign):
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

        # By status
        status_agg = dict(
            base_qs.values_list('status')
            .annotate(count=Count('id'))
            .values_list('status', 'count')
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

        total = base_qs.count()
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

    def get_accounts_breakdown(self, campaign):
        """
        Account stats grouped by status.

        Returns:
            dict: {
                'by_status': {PENDING: n, IN_PROGRESS: n, ...},
                'totals': {total, active, completed, stopped},
                'conversion_rate': float,
            }
        """
        base_qs = CampaignAccount.objects.filter(campaign=campaign)

        status_agg = dict(
            base_qs.values_list('status')
            .annotate(count=Count('id'))
            .values_list('status', 'count')
        )

        total = base_qs.count()
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

    def get_timeline_progress(self, campaign):
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

        # Work progress: completed accounts / total accounts
        total_accounts = CampaignAccount.objects.filter(campaign=campaign).count()
        completed_accounts = CampaignAccount.objects.filter(
            campaign=campaign,
            status__in=[CampaignAccountStatus.COMPLETED, CampaignAccountStatus.STOPPED],
        ).count()
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
        """Per-executor activity stats — owner and executor only."""
        results = []
        users = [
            (campaign.owner, 'OWNER'),
            (campaign.executor, 'EXECUTOR'),
        ]
        for user, role in users:
            if not user:
                continue
            user_activities = Activity.objects.filter(campaign=campaign, owner=user)
            total = user_activities.count()
            completed = user_activities.filter(status=ActivityStatus.COMPLETED).count()
            planned = user_activities.filter(status=ActivityStatus.PLANNED).count()
            on_hold = user_activities.filter(status=ActivityStatus.ON_HOLD).count()
            accounts_count = user_activities.values('account').distinct().count()

            results.append({
                'user_id': str(user.id),
                'user_name': f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
                'user_email': user.email,
                'role': role,
                'total_activities': total,
                'completed': completed,
                'planned': planned,
                'on_hold': on_hold,
                'completion_rate': round((completed / total) * 100, 1) if total > 0 else 0.0,
                'accounts_count': accounts_count,
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
        """MEETINGS: count completed MEETING activities."""
        return Activity.objects.filter(
            campaign=campaign,
            activity_type=ActivityType.MEETING,
            status=ActivityStatus.COMPLETED,
        ).count()

    def _count_contacts_reached(self, campaign):
        """CONTACTS_REACHED: distinct contacts with at least one completed activity."""
        return Activity.objects.filter(
            campaign=campaign,
            status=ActivityStatus.COMPLETED,
        ).values('contacts').distinct().count()

    def _count_decision_cycles(self, campaign):
        """DECISION_CYCLES: distinct decision cycles linked to campaign activities."""
        return Activity.objects.filter(
            campaign=campaign,
            decision_cycle__isnull=False,
        ).values('decision_cycle').distinct().count()

    def _sum_pipeline_value(self, campaign):
        """PIPELINE_VALUE: sum of estimated_value from open decision cycles."""
        result = Activity.objects.filter(
            campaign=campaign,
            decision_cycle__isnull=False,
            decision_cycle__outcome__isnull=True,  # open cycles only
        ).values('decision_cycle').distinct().aggregate(
            total=Sum('decision_cycle__estimated_value')
        )
        return float(result['total'] or 0)

    def _sum_revenue_won(self, campaign):
        """REVENUE_WON: sum of estimated_value from WON decision cycles."""
        result = Activity.objects.filter(
            campaign=campaign,
            decision_cycle__isnull=False,
            decision_cycle__outcome='WON',
        ).values('decision_cycle').distinct().aggregate(
            total=Sum('decision_cycle__estimated_value')
        )
        return float(result['total'] or 0)

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