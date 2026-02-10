# app_modules/decision_cycles/services/step_status_derivation_service.py
"""
Step Status Derivation Service.

Derives DecisionStep status automatically from activity data.
Single source of truth for step status — replaces manual status changes.

Derivation priority (highest first):
1. WON         — activity completed with no_next_step_reason=CLOSE_WON
2. REJECTED    — activity completed with reason ∈ {CLOSE_LOST, NOT_QUALIFIED}
3. OVERDUE     — expected_end < today OR any PLANNED activity past scheduled/due date
4. VALIDATED   — ALL activities completed (0 PLANNED) + later step has activities
5. IN_PROGRESS — at least 1 PLANNED AND (some PLANNED are current/past/undated OR completed exist)
6. ON_HOLD     — completed activities exist, no PLANNED, no activity in later steps
7. NOT_STARTED — no activities, all cancelled, OR only future-dated PLANNED with no completed

IN_CHASING: Reserved for future Campaign/Sequence feature (not auto-derived).

Usage:
    service = StepStatusDerivationService()

    # Single step (detail view — triggers DB queries)
    result = service.derive(step)
    # Returns: {status, status_display, color}

    # Bulk (timeline view — zero DB queries, uses prefetched data)
    results = service.derive_bulk(steps)
    # Returns: dict keyed by step.id
"""

from django.utils import timezone

from core.logging import get_logger

logger = get_logger(__name__)


class StepStatusDerivationService:
    """
    Derives step status from activity data.

    Design:
    - Stateless: no stored state between calls.
    - Single-instance methods: trigger DB queries, suitable for detail views.
    - Bulk methods: operate on prefetched data only, zero additional queries.
    - Returns plain dicts (serializable), not model instances.
    """

    # Terminal no_next_step_reasons that determine WON/REJECTED
    WON_REASONS = frozenset(['CLOSE_WON'])
    REJECTED_REASONS = frozenset(['CLOSE_LOST', 'NOT_QUALIFIED'])

    # Status → MUI color token mapping
    STATUS_COLORS = {
        'WON': 'primary.dark',
        'REJECTED': 'error.main',
        'OVERDUE': 'error.light',
        'VALIDATED': 'primary.light',
        'IN_PROGRESS': 'secondary.main',
        'ON_HOLD': 'warning.light',
        'IN_CHASING': 'warning.dark',
        'NOT_STARTED': 'secondary.light',
    }

    # ------------------------------------------------------------------
    # SINGLE-INSTANCE METHOD (detail view — DB queries acceptable)
    # ------------------------------------------------------------------

    def derive(self, step):
        """
        Derive status for a single step from its activities.

        Returns dict:
        {
            'status': str (DecisionStepStatus value),
            'status_display': str,
            'color': str (MUI color token),
        }

        Triggers DB queries — use derive_bulk() for list views.
        """
        from ..constants import DecisionStepStatus
        from app_modules.activities.constants import ActivityStatus

        # Get non-cancelled activities for this step
        activities = list(
            step.activities.exclude(status=ActivityStatus.CANCELLED)
        )

        # Check if a later step in the same cycle has activities
        has_activity_in_later_step = self._has_activity_in_later_step_db(step)

        status = self._compute_status(
            step, activities, timezone.now().date(), has_activity_in_later_step
        )

        return {
            'status': status,
            'status_display': DecisionStepStatus(status).label,
            'color': self.STATUS_COLORS.get(status, 'secondary.light'),
        }

    # ------------------------------------------------------------------
    # BULK METHOD (timeline view — zero DB queries)
    # ------------------------------------------------------------------

    def derive_bulk(self, steps):
        """
        Bulk status derivation for list/timeline views.

        Operates entirely on prefetched data:
        - step.expected_end, step.order, step.cycle_id (model fields)
        - step activities from prefetch cache

        Requires activities prefetched on each step.
        All steps from the same cycle must be passed together
        so we can check cross-step activity existence.

        Returns dict keyed by step.id:
        {
            step_id: {
                'status': str,
                'status_display': str,
                'color': str,
            }
        }
        """
        from ..constants import DecisionStepStatus

        today = timezone.now().date()

        # Group steps by cycle for cross-step lookups
        cycle_steps_map = self._group_steps_by_cycle(steps)

        results = {}

        for step in steps:
            activities = self._get_non_cancelled_activities(step)
            has_activity_in_later_step = self._has_activity_in_later_step_bulk(
                step, cycle_steps_map
            )

            status = self._compute_status(
                step, activities, today, has_activity_in_later_step
            )

            results[step.id] = {
                'status': status,
                'status_display': DecisionStepStatus(status).label,
                'color': self.STATUS_COLORS.get(status, 'secondary.light'),
            }

        return results

    # ------------------------------------------------------------------
    # CORE DERIVATION LOGIC (shared by single + bulk)
    # ------------------------------------------------------------------

    def _compute_status(self, step, activities, today, has_activity_in_later_step):
        """
        Core derivation logic.

        Works on in-memory activity list.

        Args:
            step: DecisionStep instance (reads expected_end only)
            activities: list of Activity instances (non-cancelled)
            today: date for overdue comparison
            has_activity_in_later_step: bool — a step with higher order
                in the same cycle has at least 1 non-cancelled activity

        Returns: status string
        """
        from ..constants import DecisionStepStatus

        # Rule 7 — NOT_STARTED: no activities
        if not activities:
            return DecisionStepStatus.NOT_STARTED

        # Classify activities
        completed = [a for a in activities if a.status == 'COMPLETED']
        planned = [a for a in activities if a.status == 'PLANNED']

        # Rule 1 — WON: any completed activity has CLOSE_WON
        for a in completed:
            if a.no_next_step_reason in self.WON_REASONS:
                return DecisionStepStatus.WON

        # Rule 2 — REJECTED: any completed activity has CLOSE_LOST/NOT_QUALIFIED
        for a in completed:
            if a.no_next_step_reason in self.REJECTED_REASONS:
                return DecisionStepStatus.REJECTED

        # Rule 3 — OVERDUE: step deadline passed OR any PLANNED activity overdue
        if self._is_step_overdue(step, planned, today):
            return DecisionStepStatus.OVERDUE

        # Rule 4 — VALIDATED: ALL completed (0 PLANNED) + later step has activity
        if completed and not planned and has_activity_in_later_step:
            return DecisionStepStatus.VALIDATED

        # Rule 5 — IN_PROGRESS: at least 1 PLANNED that is actionable
        # Actionable = PLANNED with current/past/no date, OR completed work exists
        if planned:
            if completed:
                # Work already started + more planned = in progress
                return DecisionStepStatus.IN_PROGRESS

            # No completed yet — check if any planned is current or past
            has_actionable = any(
                self._is_activity_current_or_past(a, today)
                for a in planned
            )
            if has_actionable:
                return DecisionStepStatus.IN_PROGRESS

            # All planned are future-dated, no completed → not started yet
            return DecisionStepStatus.NOT_STARTED

        # Rule 6 — ON_HOLD: completed exist, no planned, no later activity
        if completed:
            return DecisionStepStatus.ON_HOLD

        # Fallback (should never reach here)
        return DecisionStepStatus.NOT_STARTED

    # ------------------------------------------------------------------
    # PRIVATE — Activity-level overdue helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_activity_overdue(activity, today):
        """
        Check if a PLANNED activity is past its scheduled or due date.

        An activity is overdue when:
        - scheduled_date < today, OR
        - due_date < today
        Only applies to PLANNED activities (completed/cancelled are excluded).
        """
        if activity.scheduled_date and activity.scheduled_date < today:
            return True
        if activity.due_date and activity.due_date < today:
            return True
        return False

    @staticmethod
    def _is_activity_current_or_past(activity, today):
        """
        Check if a PLANNED activity is current, past, or has no date.

        Returns True when:
        - No scheduled_date and no due_date (undated = actionable now)
        - scheduled_date <= today
        - due_date <= today
        """
        if not activity.scheduled_date and not activity.due_date:
            return True
        if activity.scheduled_date and activity.scheduled_date <= today:
            return True
        if activity.due_date and activity.due_date <= today:
            return True
        return False

    @classmethod
    def _is_step_overdue(cls, step, planned_activities, today):
        """
        Check if step is overdue at step level OR activity level.

        Returns True when:
        - step.expected_end < today (step deadline passed), OR
        - Any PLANNED activity has scheduled_date or due_date in the past
        """
        # Step-level deadline
        if step.expected_end and step.expected_end < today:
            return True

        # Activity-level overdue
        for a in planned_activities:
            if cls._is_activity_overdue(a, today):
                return True

        return False

    # ------------------------------------------------------------------
    # PRIVATE — Single-instance helpers (DB queries)
    # ------------------------------------------------------------------

    @staticmethod
    def _has_activity_in_later_step_db(step):
        """
        Check if any step with higher order in the same cycle
        has at least 1 non-cancelled activity.

        Queries from Activity table to avoid Django's multi-valued
        .exclude() gotcha (which would exclude entire steps if ANY
        activity is cancelled, even if other activities are not).

        Triggers 1 DB query.
        """
        from app_modules.activities.constants import ActivityStatus
        from app_modules.activities.models import Activity

        if not step.cycle_id:
            return False

        return Activity.objects.filter(
            decision_step__cycle_id=step.cycle_id,
            decision_step__order__gt=step.order,
        ).exclude(
            status=ActivityStatus.CANCELLED,
        ).exists()

    # ------------------------------------------------------------------
    # PRIVATE — Bulk helpers (prefetched data only, zero queries)
    # ------------------------------------------------------------------

    @staticmethod
    def _get_non_cancelled_activities(step):
        """
        Get non-cancelled activities from Django prefetch cache.
        Filters CANCELLED from prefetched list (no DB query).
        """
        cache = getattr(step, '_prefetched_objects_cache', {})
        all_activities = cache.get('activities', [])
        return [a for a in all_activities if a.status != 'CANCELLED']

    @staticmethod
    def _group_steps_by_cycle(steps):
        """
        Group steps by cycle_id for cross-step lookups.

        Returns dict: {cycle_id: [step, step, ...]} sorted by order.
        """
        cycle_map = {}
        for step in steps:
            cycle_id = step.cycle_id
            if cycle_id not in cycle_map:
                cycle_map[cycle_id] = []
            cycle_map[cycle_id].append(step)

        # Sort each cycle's steps by order
        for cycle_id in cycle_map:
            cycle_map[cycle_id].sort(key=lambda s: s.order)

        return cycle_map

    @classmethod
    def _has_activity_in_later_step_bulk(cls, step, cycle_steps_map):
        """
        Check if any later step (higher order) in the same cycle
        has at least 1 non-cancelled activity.

        Uses prefetched data only — zero DB queries.
        """
        cycle_id = step.cycle_id
        if not cycle_id or cycle_id not in cycle_steps_map:
            return False

        for sibling in cycle_steps_map[cycle_id]:
            if sibling.order <= step.order:
                continue
            # Check if this later step has non-cancelled activities
            sibling_activities = cls._get_non_cancelled_activities(sibling)
            if sibling_activities:
                return True

        return False