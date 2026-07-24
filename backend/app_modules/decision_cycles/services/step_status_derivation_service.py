# app_modules/decision_cycles/services/step_status_derivation_service.py
"""
Step Status Derivation Service.

Derives DecisionStep status automatically from activity data.
Single source of truth for step status — replaces manual status changes.

Derivation priority (highest first):
1. OVERDUE     — step deadline passed OR any PLANNED activity overdue
2. VALIDATED   — all completed + PLANNED exists elsewhere in cycle (deal moving)
   STALLED     — all completed + NO PLANNED in entire cycle + last completed step
   VALIDATED   — all completed + NO PLANNED in cycle + not last completed step
3. IN_PROGRESS — at least 1 PLANNED activity exists
4. NOT_STARTED — no activities

STALLED only applies to the last step (by pipeline order) with completed
activities when the entire cycle has zero PLANNED activities remaining.
This signals a dormant deal to the sales rep.

WON/LOST/ON_HOLD are cycle-level outcomes (CycleOutcome), not step statuses.
IN_CHASING: Reserved for future Campaign/Sequence feature.

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

    # Status → MUI color token mapping
    STATUS_COLORS = {
        'OVERDUE': 'error.light',
        'VALIDATED': 'primary.light',
        'IN_PROGRESS': 'secondary.main',
        'STALLED': 'warning.light',
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

        # Prefer the SQL annotation when the queryset carried it (single source
        # of truth — see services/derivation_sql.py). Falls back to the Python
        # computation, which stays the parity oracle.
        annotated = getattr(step, '_derived_status', None)
        if annotated is not None:
            status = annotated
        else:
            # Get non-cancelled activities for this step
            activities = list(
                step.activities.exclude(status=ActivityStatus.CANCELLED)
            )

            today = timezone.now().date()
            has_planned_in_cycle = self._has_planned_in_cycle_db(step)
            is_last_completed_step = self._is_last_completed_step_db(step)

            status = self._compute_status(
                step, activities, today, has_planned_in_cycle, is_last_completed_step
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
            # Prefer the SQL annotation when the queryset carried it (single
            # source of truth — see services/derivation_sql.py). Falls back to
            # the prefetch-based Python computation, the parity oracle.
            annotated = getattr(step, '_derived_status', None)
            if annotated is not None:
                status = annotated
            else:
                activities = self._get_non_cancelled_activities(step)
                has_planned_in_cycle = self._has_planned_in_cycle_bulk(
                    step, cycle_steps_map
                )
                is_last_completed_step = self._is_last_completed_step_bulk(
                    step, cycle_steps_map
                )

                status = self._compute_status(
                    step, activities, today, has_planned_in_cycle, is_last_completed_step
                )

            results[step.id] = {
                'status': status,
                'status_display': DecisionStepStatus(status).label,
                'color': self.STATUS_COLORS.get(status, 'secondary.light'),
            }

        return results

    @staticmethod
    def _has_planned_in_cycle_bulk(step, cycle_steps_map):
        """Check if any PLANNED activity exists in any step of the same cycle (prefetched)."""
        cycle_steps = cycle_steps_map.get(step.cycle_id, [])
        for s in cycle_steps:
            activities = getattr(s, '_prefetched_objects_cache', {}).get('activities', [])
            if any(a.status == 'PLANNED' for a in activities):
                return True
        return False

    @staticmethod
    def _is_last_completed_step_bulk(step, cycle_steps_map):
        """
        Check if this step has the highest pipeline order among steps
        with at least one COMPLETED activity (prefetched).
        """
        cycle_steps = cycle_steps_map.get(step.cycle_id, [])
        max_order = None
        for s in cycle_steps:
            activities = getattr(s, '_prefetched_objects_cache', {}).get('activities', [])
            has_completed = any(a.status == 'COMPLETED' for a in activities)
            if has_completed:
                if max_order is None or s.order > max_order:
                    max_order = s.order
        if max_order is None:
            return False
        return step.order == max_order

    # ------------------------------------------------------------------
    # CORE DERIVATION LOGIC (shared by single + bulk)
    # ------------------------------------------------------------------

    def _compute_status(self, step, activities, today, has_planned_in_cycle, is_last_completed_step):
        """
        Core status derivation logic.

        Priority:
        1. DONE (VALIDATED / STALLED) — all activities completed, none planned in
           this step. Checked BEFORE overdue so a completed step never flips to
           OVERDUE (a past expected_end on a done step is irrelevant — BUG 4):
           a. PLANNED exists elsewhere in cycle → VALIDATED (cycle still moving)
           b. No PLANNED in cycle + last completed step → STALLED (deal dormant)
           c. No PLANNED in cycle + not last completed step → VALIDATED
        2. OVERDUE — step deadline passed OR any PLANNED activity overdue
           (only reachable when the step still has outstanding/planned work)
        3. IN_PROGRESS — at least 1 PLANNED activity exists
        4. NOT_STARTED — no activities at all
        """
        from ..constants import DecisionStepStatus

        non_cancelled = [a for a in activities if a.status != 'CANCELLED']

        if not non_cancelled:
            return DecisionStepStatus.NOT_STARTED

        planned = [a for a in non_cancelled if a.status == 'PLANNED']
        completed = [a for a in non_cancelled if a.status == 'COMPLETED']

        # Rule 1 — DONE: all completed, no planned in THIS step (VALIDATED/STALLED).
        # BUG 4 fix: evaluated BEFORE overdue so a completed step is never OVERDUE.
        # STALLED semantics unchanged (intentional motivation lever — kept).
        if completed and not planned:
            if has_planned_in_cycle:
                return DecisionStepStatus.VALIDATED
            # No PLANNED anywhere in cycle
            if is_last_completed_step:
                return DecisionStepStatus.STALLED
            return DecisionStepStatus.VALIDATED

        # Rule 2 — OVERDUE (only when outstanding/planned work is past due)
        if self._is_step_overdue(step, planned, today):
            return DecisionStepStatus.OVERDUE

        # Rule 3 — Has planned activities
        if planned:
            return DecisionStepStatus.IN_PROGRESS

        # Rule 4 — Fallback
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
    def _has_planned_in_cycle_db(step):
        """Check if any PLANNED activity exists in the same cycle. Triggers 1 query."""
        if not step.cycle_id:
            return False
        from app_modules.activities.models import Activity
        return Activity.objects.filter(
            decision_cycle_id=step.cycle_id,
            status='PLANNED',
        ).exists()

    @staticmethod
    def _is_last_completed_step_db(step):
        """
        Check if this step has the highest pipeline order among steps
        with at least one COMPLETED activity in the same cycle.
        Triggers 1 query.
        """
        if not step.cycle_id:
            return True
        from app_modules.activities.models import Activity
        from django.db.models import Max

        max_order_with_completed = Activity.objects.filter(
            decision_cycle_id=step.cycle_id,
            status='COMPLETED',
        ).aggregate(
            max_order=Max('decision_step__order')
        )['max_order']

        if max_order_with_completed is None:
            return False
        return step.order == max_order_with_completed

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
