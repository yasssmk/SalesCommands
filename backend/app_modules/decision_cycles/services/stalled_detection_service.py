# app_modules/decision_cycles/services/stalled_detection_service.py
"""
Stalled Detection Service for Decision Steps.

Detects stalled DecisionSteps and provides actionable diagnostics.
Single source of truth for stalled state, replacing model @property methods.

Stalled reasons (priority order):
1. EXPECTED_END_PASSED — deadline missed
2. NO_ACTIVITY — no activities at all (skip activity-optional steps)
3. NO_NEXT_STEP — last activity explicitly marked no next step
4. NO_FUTURE_ACTIVITY — no planned activities
5. WAITING_TOO_LONG — no activity in 7+ days

Usage:
    service = StalledDetectionService()

    # Single step (detail view)
    result = service.detect(step)
    # Returns: {is_stalled, reason, reason_display, details}

    # Bulk (list/timeline view — zero DB queries, uses prefetched data)
    results = service.detect_bulk(steps)
    # Returns: dict keyed by step.id
"""

from django.utils import timezone

from core.logging import get_logger

logger = get_logger(__name__)


class StalledDetectionService:
    """
    Detects stalled DecisionSteps and provides diagnostics.

    Design:
    - Stateless: no stored state between calls.
    - Single-instance methods: trigger DB queries, suitable for detail views.
    - Bulk methods: operate on prefetched data only, zero additional queries.
    - Returns plain dicts (serializable), not model instances.
    """

    STALLED_THRESHOLD_DAYS = 7

    # Statuses that can never be stalled
    NON_STALLABLE_STATUSES = frozenset([
        'NOT_STARTED',
        'VALIDATED',
        'REJECTED',
        'ON_HOLD',
        'CANCELLED',
    ])

    # ------------------------------------------------------------------
    # SINGLE-INSTANCE METHODS (detail view — DB queries acceptable)
    # ------------------------------------------------------------------

    def detect(self, step):
        """
        Full stalled analysis for a single step.

        Returns dict:
        {
            'is_stalled': bool,
            'reason': str (StalledReason value),
            'reason_display': str | None,
            'details': {
                'last_activity_date': date | None,
                'days_since_last_activity': int | None,
                'has_future_activity': bool,
                'expected_end': date | None,
            }
        }

        Triggers DB queries — use detect_bulk() for list views.
        """
        from .step_aggregation_service import StepAggregationService
        from ..constants import StalledReason

        reason = self._compute_reason(step)
        is_stalled = reason != StalledReason.NONE

        # Build details dict (only if stalled, to avoid unnecessary queries)
        details = None
        if is_stalled:
            details = {
                'last_activity_date': self._get_last_activity_date(step),
                'days_since_last_activity': self._get_days_since_last_activity(step),
                'has_future_activity': self._has_future_activity(step),
                'expected_end': step.expected_end,
            }

        return {
            'is_stalled': is_stalled,
            'reason': reason,
            'reason_display': (
                StalledReason(reason).label if is_stalled else None
            ),
            'details': details,
        }

    def get_stalled_details(self, step):
        """
        Detailed breakdown for UI display.
        Returns dict or None (if not stalled).

        Convenience wrapper around detect() for serializer use.
        """
        result = self.detect(step)
        if not result['is_stalled']:
            return None

        return {
            'reason': result['reason'],
            'reason_display': result['reason_display'],
            'last_activity_date': result['details']['last_activity_date'],
            'days_since_last_activity': result['details']['days_since_last_activity'],
            'has_future_activity': result['details']['has_future_activity'],
            'expected_end': result['details']['expected_end'],
        }

    def needs_next_step_attention(self, step):
        """
        Check if last completed activity needs next step resolution.

        Returns True when:
        - Step has at least one COMPLETED activity
        - Most recent completed activity has next_step_agreed=None or
          next_step_agreed=False with no reason
        - No PLANNED activities exist in the step

        Triggers DB queries — for bulk, use detect_bulk().
        """
        from app_modules.activities.constants import ActivityStatus

        last_completed = step.activities.filter(
            status=ActivityStatus.COMPLETED
        ).order_by('-completed_at').first()

        if not last_completed:
            return False

        # If planned activities exist, no attention needed
        has_planned = step.activities.filter(
            status=ActivityStatus.PLANNED
        ).exists()
        if has_planned:
            return False

        # Next step resolution missing
        if last_completed.next_step_agreed is None:
            return True

        if (last_completed.next_step_agreed is False
                and not last_completed.no_next_step_reason):
            return True

        return False

    # ------------------------------------------------------------------
    # BULK METHOD (list/timeline view — zero DB queries)
    # ------------------------------------------------------------------

    def detect_bulk(self, steps):
        """
        Bulk stalled detection for list/timeline views.

        Operates entirely on prefetched data:
        - step.status, step.stage, step.expected_end (model fields)
        - step activities from prefetch cache

        Requires same prefetch setup as StepAggregationService.get_bulk_aggregation().

        Returns dict keyed by step.id:
        {
            step_id: {
                'is_stalled': bool,
                'reason': str,
                'reason_display': str | None,
                'needs_next_step_attention': bool,
            }
        }
        """
        from ..constants import StalledReason, ACTIVITY_OPTIONAL_STEPS

        today = timezone.now().date()
        results = {}

        for step in steps:
            activities = self._get_prefetched_activities(step)
            reason = self._compute_reason_from_prefetched(
                step, activities, today
            )
            is_stalled = reason != StalledReason.NONE

            results[step.id] = {
                'is_stalled': is_stalled,
                'reason': reason,
                'reason_display': (
                    StalledReason(reason).label if is_stalled else None
                ),
                'needs_next_step_attention': (
                    self._bulk_needs_next_step_attention(activities)
                ),
            }

        return results

    # ------------------------------------------------------------------
    # PRIVATE — Single-instance helpers (DB queries)
    # ------------------------------------------------------------------

    def _compute_reason(self, step):
        """
        Compute stalled reason for a single step.
        Priority order matches product spec.
        """
        from ..constants import StalledReason, ACTIVITY_OPTIONAL_STEPS
        from app_modules.activities.constants import ActivityStatus

        if step.status in self.NON_STALLABLE_STATUSES:
            return StalledReason.NONE

        today = timezone.now().date()

        # 1. Expected end date has passed
        if step.expected_end and step.expected_end < today:
            return StalledReason.EXPECTED_END_PASSED

        # 2. No activities at all (skip activity-optional steps)
        if not step.activities.exists():
            if step.stage in ACTIVITY_OPTIONAL_STEPS:
                return StalledReason.NONE
            return StalledReason.NO_ACTIVITY

        # 3. Last completed activity marked no next step
        last_completed = step.activities.filter(
            status=ActivityStatus.COMPLETED
        ).order_by('-completed_at').first()

        if last_completed and last_completed.next_step_agreed is False:
            return StalledReason.NO_NEXT_STEP

        # 4. No future activities planned
        has_future = self._has_future_activity(step)
        if not has_future:
            # 5. Check waiting too long
            days = self._get_days_since_last_activity(step)
            if days is not None and days >= self.STALLED_THRESHOLD_DAYS:
                return StalledReason.WAITING_TOO_LONG
            return StalledReason.NO_FUTURE_ACTIVITY

        return StalledReason.NONE

    def _get_last_activity_date(self, step):
        """Date of the most recent activity. Triggers 1 query."""
        last_activity = step.activities.order_by('-updated_at').first()
        if not last_activity:
            return None

        if last_activity.completed_at:
            return last_activity.completed_at.date()
        if last_activity.scheduled_date:
            return last_activity.scheduled_date
        return last_activity.updated_at.date()

    def _get_days_since_last_activity(self, step):
        """Days since last activity. Returns int or None."""
        last_date = self._get_last_activity_date(step)
        if not last_date:
            return None
        today = timezone.now().date()
        return (today - last_date).days

    @staticmethod
    def _has_future_activity(step):
        """Check if step has any PLANNED activities."""
        from app_modules.activities.constants import ActivityStatus

        return step.activities.filter(
            status=ActivityStatus.PLANNED
        ).exists()

    # ------------------------------------------------------------------
    # PRIVATE — Bulk helpers (prefetched data only, zero queries)
    # ------------------------------------------------------------------

    @staticmethod
    def _get_prefetched_activities(step):
        """Get activities from Django prefetch cache."""
        cache = getattr(step, '_prefetched_objects_cache', {})
        return cache.get('activities', [])

    def _compute_reason_from_prefetched(self, step, activities, today):
        """
        Compute stalled reason from prefetched data only.
        Same priority order as _compute_reason but no DB queries.
        """
        from ..constants import StalledReason, ACTIVITY_OPTIONAL_STEPS

        if step.status in self.NON_STALLABLE_STATUSES:
            return StalledReason.NONE

        # 1. Expected end date has passed
        if step.expected_end and step.expected_end < today:
            return StalledReason.EXPECTED_END_PASSED

        # 2. No activities at all
        if not activities:
            if step.stage in ACTIVITY_OPTIONAL_STEPS:
                return StalledReason.NONE
            return StalledReason.NO_ACTIVITY

        # 3. Last completed activity marked no next step
        completed = [
            a for a in activities
            if a.status == 'COMPLETED' and a.completed_at
        ]
        if completed:
            last_completed = max(completed, key=lambda a: a.completed_at)
            if last_completed.next_step_agreed is False:
                return StalledReason.NO_NEXT_STEP

        # 4. No future activities planned
        has_planned = any(a.status == 'PLANNED' for a in activities)
        if not has_planned:
            # 5. Waiting too long
            last_date = self._bulk_last_activity_date(activities)
            if last_date:
                days = (today - last_date).days
                if days >= self.STALLED_THRESHOLD_DAYS:
                    return StalledReason.WAITING_TOO_LONG
            return StalledReason.NO_FUTURE_ACTIVITY

        return StalledReason.NONE

    @staticmethod
    def _bulk_last_activity_date(activities):
        """Compute last activity date from prefetched list."""
        if not activities:
            return None

        dates = []
        for a in activities:
            if a.completed_at:
                dates.append(a.completed_at.date())
            elif a.scheduled_date:
                dates.append(a.scheduled_date)

        return max(dates) if dates else None

    @staticmethod
    def _bulk_needs_next_step_attention(activities):
        """
        Check next step attention from prefetched activities.
        Same logic as single-instance but on in-memory list.
        """
        if not activities:
            return False

        # Check if any planned activities exist
        has_planned = any(a.status == 'PLANNED' for a in activities)
        if has_planned:
            return False

        # Find last completed
        completed = [
            a for a in activities
            if a.status == 'COMPLETED' and a.completed_at
        ]
        if not completed:
            return False

        last_completed = max(completed, key=lambda a: a.completed_at)

        if last_completed.next_step_agreed is None:
            return True

        if (last_completed.next_step_agreed is False
                and not last_completed.no_next_step_reason):
            return True

        return False