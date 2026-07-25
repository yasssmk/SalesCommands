# app_modules/decision_cycles/services/cycle_aggregation_service.py
"""
Cycle Aggregation Service.

Aggregates DecisionStep data into DecisionCycle-level insights.
Composes StepAggregationService and StalledDetectionService to provide:
- Derived cycle status (explicit outcome first, then from steps)
- Progress metrics (validated / total)
- Stalled steps detection
- All stakeholders across the cycle
- Cycle-level timeline

Two-layer architecture:
    1. cycle.outcome (WON/LOST/ON_HOLD/NOT_QUALIFIED) → explicit, overrides all
    2. else → derive from step statuses (NOT_STARTED / STALLED / IN_PROGRESS)

Usage:
    service = CycleAggregationService()

    # Single cycle (detail view)
    summary = service.get_cycle_summary(cycle)

    # Bulk (by_account timeline — zero DB queries, uses prefetched data)
    summaries = service.get_bulk_summaries(cycles_queryset)
"""

from django.utils import timezone

from core.logging import get_logger

from .step_aggregation_service import StepAggregationService

logger = get_logger(__name__)


class CycleAggregationService:
    """
    Aggregates step-level data into cycle-level insights.

    Design:
    - Stateless: no stored state between calls.
    - Composes StepAggregationService + StalledDetectionService.
    - Single-instance methods: trigger DB queries via sub-services.
    - Bulk methods: operate on prefetched data only, zero additional queries.
    - Returns plain dicts (serializable).
    """

    # Derived cycle statuses (not stored in DB — computed on read)
    # Explicit outcomes (from cycle.outcome field):
    STATUS_WON = 'WON'
    STATUS_LOST = 'LOST'
    STATUS_ON_HOLD = 'ON_HOLD'
    # Derived from steps (when cycle.outcome is null):
    STATUS_NOT_STARTED = 'NOT_STARTED'
    STATUS_OVERDUE = 'OVERDUE'
    STATUS_IN_PROGRESS = 'IN_PROGRESS'
    STATUS_STALLED = 'STALLED'

    def __init__(self):
        self._step_aggregation = StepAggregationService()

    # ------------------------------------------------------------------
    # SINGLE-INSTANCE METHODS (detail view — DB queries acceptable)
    # ------------------------------------------------------------------

    def get_cycle_status(self, cycle):
        """
        Derive overall cycle status from steps.

        Logic:
        - All steps NOT_STARTED → NOT_STARTED
        - Any step REJECTED → LOST
        - All steps VALIDATED → WON
        - Any step stalled → STALLED or AT_RISK
        - Otherwise → IN_PROGRESS / ON_TRACK

        Returns status string constant.
        """
        steps = list(cycle.steps.all())
        return self._derive_status(steps, cycle=cycle)

    def get_progress(self, cycle):
        """
        Progress metrics for the cycle.

        Returns dict:
        {
            'total_steps': int,
            'validated_steps': int,
            'current_step_name': str | None,
            'percentage': int (0-100),
        }
        """
        from .step_status_derivation_service import StepStatusDerivationService

        steps = list(cycle.steps.prefetch_related('activities'))
        derived = StepStatusDerivationService().derive_bulk(steps)
        return self._compute_progress(steps, derived)

    def get_stalled_steps(self, cycle):
        """
        List of stalled steps.

        Uses StepStatusDerivationService to check derived_status == STALLED.

        Returns list of dicts:
        [{'step_id': uuid, 'step_name': str}]
        """
        from .step_status_derivation_service import StepStatusDerivationService
        derivation_service = StepStatusDerivationService()

        stalled = []
        for step in cycle.steps.all():
            result = derivation_service.derive(step)
            if result['status'] == 'STALLED':
                stalled.append({
                    'step_id': str(step.id),
                    'step_name': step.name,
                })
        return stalled

    def get_all_stakeholders(self, cycle):
        """
        All contacts across all steps, deduplicated.

        Returns list of dicts (same format as StepAggregationService.get_all_contacts).
        """
        seen_ids = set()
        stakeholders = []

        for step in cycle.steps.all():
            contacts = self._step_aggregation.get_all_contacts(step)
            for contact in contacts:
                cid = contact['id']
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    stakeholders.append(contact)

        return stakeholders

    def get_cycle_timeline(self, cycle):
        """
        Cycle-level timeline derived from step timelines.

        Returns dict:
        {
            'first_activity_date': date | None,
            'last_activity_date': date | None,
            'earliest_expected_end': date | None,
            'latest_expected_end': date | None,
            'is_overdue': bool,
        }
        """
        first_dates = []
        last_dates = []
        expected_ends = []

        for step in cycle.steps.all():
            timeline = self._step_aggregation.get_timeline(step)
            if timeline['effective_start']:
                first_dates.append(timeline['effective_start'])
            if timeline['effective_end']:
                last_dates.append(timeline['effective_end'])
            if timeline['manual_expected_end']:
                expected_ends.append(timeline['manual_expected_end'])

        today = timezone.now().date()
        latest_expected = max(expected_ends) if expected_ends else None

        return {
            'first_activity_date': min(first_dates) if first_dates else None,
            'last_activity_date': max(last_dates) if last_dates else None,
            'earliest_expected_end': min(expected_ends) if expected_ends else None,
            'latest_expected_end': latest_expected,
            'is_overdue': (
                latest_expected < today if latest_expected else False
            ),
        }

    def get_cycle_summary(self, cycle):
        """
        Full summary dict combining all cycle-level insights.
        Used by cycle detail serializer.

        Returns dict with all sub-results.
        """
        stalled_steps = self.get_stalled_steps(cycle)
        cycle_status = self.get_cycle_status(cycle)
        return {
            'cycle_status': cycle_status,
            'progress': self.get_progress(cycle),
            'stalled_steps': stalled_steps,
            'stalled_steps_count': len(stalled_steps),
            'timeline': self.get_cycle_timeline(cycle),
            'is_at_risk': cycle_status in (self.STATUS_STALLED, self.STATUS_OVERDUE),
        }

    # ------------------------------------------------------------------
    # BULK METHOD (by_account timeline — zero DB queries)
    # ------------------------------------------------------------------

    def get_bulk_summaries(self, cycles, step_derived_statuses=None):
        """
        Lightweight summaries for cycle list/timeline view.

        Operates on prefetched data only. Uses step_derived_statuses
        to count STALLED steps directly (no StalledDetectionService).

        Args:
            cycles: iterable of DecisionCycle with prefetched steps + activities
            step_derived_statuses: dict from StepStatusDerivationService.derive_bulk()
                                   (optional, computed internally if not provided)

        Returns dict keyed by cycle.id:
        {
            cycle_id: {
                'cycle_status': str,
                'progress': {total_steps, validated_steps, current_step_name, percentage},
                'stalled_steps_count': int,
                'is_at_risk': bool,
            }
        }
        """
        from .derivation_sql import CYCLE_STATUS_ALIAS

        cycles = list(cycles)

        # Fast path: cycles carrying the SQL cycle-state annotation are read
        # directly (single source of truth — see services/derivation_sql.py).
        # The Python fallback below stays the parity oracle and is computed
        # ONLY for cycles that lack the annotation (by_account, the KPI), so
        # their behaviour is unchanged.
        cycle_steps_map = {}
        need_python = [
            cycle for cycle in cycles
            if getattr(cycle, CYCLE_STATUS_ALIAS, None) is None
        ]

        if need_python:
            all_steps = []
            for cycle in need_python:
                steps = self._get_prefetched_steps(cycle)
                cycle_steps_map[cycle.id] = steps
                all_steps.extend(steps)

            # Compute derived statuses if not pre-provided
            if step_derived_statuses is None:
                from .step_status_derivation_service import StepStatusDerivationService
                step_derived_statuses = StepStatusDerivationService().derive_bulk(all_steps)

        results = {}

        for cycle in cycles:
            if getattr(cycle, CYCLE_STATUS_ALIAS, None) is not None:
                results[cycle.id] = self._summary_from_annotations(cycle)
                continue

            steps = cycle_steps_map.get(cycle.id, [])

            # Derive cycle status: explicit outcome first, then from steps
            cycle_status = self._derive_status_bulk(steps, step_derived_statuses, cycle=cycle)

            # Progress from derived step statuses
            progress = self._compute_progress(steps, step_derived_statuses)

            # Count stalled steps from derived statuses
            stalled_count = sum(
                1 for s in steps
                if step_derived_statuses.get(s.id, {}).get('status') == 'STALLED'
            )

            results[cycle.id] = {
                'cycle_status': cycle_status,
                'progress': progress,
                'stalled_steps_count': stalled_count,
                'is_at_risk': cycle_status in (self.STATUS_STALLED, self.STATUS_OVERDUE),
            }

        return results

    def _summary_from_annotations(self, cycle):
        """
        Build the summary dict from the SQL cycle-state annotations
        (annotate_cycle_state) — the same shape _derive_status_bulk +
        _compute_progress produce, so consumers cannot tell which path ran.
        """
        from .derivation_sql import (
            CYCLE_STATUS_ALIAS,
            CURRENT_STEP_NAME_ALIAS,
            CURRENT_STEP_ORDER_ALIAS,
            VALIDATED_STEPS_COUNT_ALIAS,
            TOTAL_STEPS_COUNT_ALIAS,
            STALLED_STEPS_COUNT_ALIAS,
        )

        cycle_status = getattr(cycle, CYCLE_STATUS_ALIAS)
        total = getattr(cycle, TOTAL_STEPS_COUNT_ALIAS) or 0
        validated = getattr(cycle, VALIDATED_STEPS_COUNT_ALIAS) or 0
        percentage = round((validated / total) * 100) if total > 0 else 0

        return {
            'cycle_status': cycle_status,
            'progress': {
                'total_steps': total,
                'validated_steps': validated,
                'current_step_name': getattr(cycle, CURRENT_STEP_NAME_ALIAS),
                'current_step_order': getattr(cycle, CURRENT_STEP_ORDER_ALIAS),
                'percentage': percentage,
            },
            'stalled_steps_count': getattr(cycle, STALLED_STEPS_COUNT_ALIAS) or 0,
            'is_at_risk': cycle_status in (self.STATUS_STALLED, self.STATUS_OVERDUE),
        }

    # ------------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------------

    def _derive_status(self, steps, cycle=None):
        """
        Derive cycle status (single-instance path).

        Priority:
        1. cycle.outcome (explicit) → WON / LOST / ON_HOLD
        2. All NOT_STARTED → NOT_STARTED
        3. Any step OVERDUE → OVERDUE (late but active work exists)
        4. Any step IN_PROGRESS or VALIDATED → IN_PROGRESS
        5. All active steps STALLED → STALLED (deal dormant)
        6. Fallback → IN_PROGRESS
        """
        # 1. Explicit outcome overrides everything
        if cycle and cycle.outcome:
            outcome = cycle.outcome
            if outcome in ('WON',):
                return self.STATUS_WON
            if outcome in ('LOST', 'NOT_QUALIFIED'):
                return self.STATUS_LOST
            if outcome == 'ON_HOLD':
                return self.STATUS_ON_HOLD

        if not steps:
            return self.STATUS_NOT_STARTED

        # Derive step statuses on the fly (single-instance path)
        from .step_status_derivation_service import StepStatusDerivationService
        derivation_service = StepStatusDerivationService()
        statuses = [derivation_service.derive(s)['status'] for s in steps]


        # 2. All NOT_STARTED → cycle not started
        if all(s == 'NOT_STARTED' for s in statuses):
            return self.STATUS_NOT_STARTED

        # 3. Any step OVERDUE → OVERDUE (late but active work exists)
        if any(s == 'OVERDUE' for s in statuses):
            return self.STATUS_OVERDUE

        # 4. Any step STALLED → cycle stalled (deal has dormant area needing attention)
        # Checked BEFORE IN_PROGRESS: even if other steps are validated,
        # a stalled step signals the deal needs action.
        if any(s == 'STALLED' for s in statuses):
            return self.STATUS_STALLED

        # 5. Any step with active work → in progress
        if any(s in ('IN_PROGRESS', 'VALIDATED') for s in statuses):
            return self.STATUS_IN_PROGRESS

        # 6. Fallback
        return self.STATUS_IN_PROGRESS

    def _derive_status_bulk(self, steps, step_derived_statuses=None, cycle=None):
        """
        Derive cycle status from pre-computed data (bulk path).

        Priority:
        1. cycle.outcome (explicit) → WON / LOST / ON_HOLD
        2. All NOT_STARTED → NOT_STARTED
        3. Any step OVERDUE → OVERDUE (late but active work exists)
        4. Any step IN_PROGRESS or VALIDATED → IN_PROGRESS
        5. All active steps STALLED → STALLED (deal dormant)
        6. Fallback → IN_PROGRESS
        """
        # 1. Explicit outcome overrides everything
        if cycle and cycle.outcome:
            outcome = cycle.outcome
            if outcome in ('WON',):
                return self.STATUS_WON
            if outcome in ('LOST', 'NOT_QUALIFIED'):
                return self.STATUS_LOST
            if outcome == 'ON_HOLD':
                return self.STATUS_ON_HOLD

        if not steps:
            return self.STATUS_NOT_STARTED

        # Step statuses are DERIVED on read (there is no stored step status).
        if step_derived_statuses is None:
            from .step_status_derivation_service import StepStatusDerivationService
            step_derived_statuses = StepStatusDerivationService().derive_bulk(steps)
        statuses = [
            step_derived_statuses.get(s.id, {}).get('status')
            for s in steps
        ]

        # 2. All NOT_STARTED → cycle not started
        if all(s == 'NOT_STARTED' for s in statuses):
            return self.STATUS_NOT_STARTED

        # 3. Any step OVERDUE → OVERDUE (late but active work exists)
        if any(s == 'OVERDUE' for s in statuses):
            return self.STATUS_OVERDUE

        # 4. Any step STALLED → cycle stalled (deal has dormant area needing attention)
        # Checked BEFORE IN_PROGRESS: even if other steps are validated,
        # a stalled step signals the deal needs action.
        if any(s == 'STALLED' for s in statuses):
            return self.STATUS_STALLED

        # 5. Any step with active work → in progress
        if any(s in ('IN_PROGRESS', 'VALIDATED') for s in statuses):
            return self.STATUS_IN_PROGRESS

        # 6. Fallback
        return self.STATUS_IN_PROGRESS

    @staticmethod
    def _compute_progress(steps, step_derived_statuses=None):
        """
        Compute progress dict from step list.

        Step statuses are DERIVED on read (there is no stored step status);
        callers pass step_derived_statuses. When absent, a step reads as
        NOT_STARTED rather than touching any stored column.
        """
        if not steps:
            return {
                'total_steps': 0,
                'validated_steps': 0,
                'current_step_name': None,
                'current_step_order': None,
                'percentage': 0,
            }

        def _get_status(s):
            if step_derived_statuses:
                return step_derived_statuses.get(s.id, {}).get('status', 'NOT_STARTED')
            return 'NOT_STARTED'

        total = len(steps)

        # VALIDATED is the only terminal positive step status now
        # (WON/LOST are cycle-level outcomes, not step statuses)
        validated = sum(1 for s in steps if _get_status(s) == 'VALIDATED')

        # Current step: first non-validated step in order
        current_name = None
        current_order = None
        sorted_steps = sorted(steps, key=lambda s: s.order)
        for s in sorted_steps:
            if _get_status(s) != 'VALIDATED':
                current_name = s.name
                current_order = s.order
                break

        percentage = round((validated / total) * 100) if total > 0 else 0

        return {
            'total_steps': total,
            'validated_steps': validated,
            'current_step_name': current_name,
            'current_step_order': current_order,
            'percentage': percentage,
        }

    @staticmethod
    def _get_prefetched_steps(cycle):
        """Get steps from Django prefetch cache. Never triggers query."""
        cache = getattr(cycle, '_prefetched_objects_cache', {})
        return list(cache.get('steps', []))