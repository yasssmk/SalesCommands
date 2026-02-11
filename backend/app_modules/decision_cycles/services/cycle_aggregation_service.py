# app_modules/decision_cycles/services/cycle_aggregation_service.py
"""
Cycle Aggregation Service.

Aggregates DecisionStep data into DecisionCycle-level insights.
Composes StepAggregationService and StalledDetectionService to provide:
- Derived cycle status (from steps)
- Progress metrics (validated / total)
- Stalled steps detection
- All stakeholders across the cycle
- Cycle-level timeline

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
from .stalled_detection_service import StalledDetectionService

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
    STATUS_NOT_STARTED = 'NOT_STARTED'
    STATUS_IN_PROGRESS = 'IN_PROGRESS'
    STATUS_ON_TRACK = 'ON_TRACK'
    STATUS_AT_RISK = 'AT_RISK'
    STATUS_STALLED = 'STALLED'
    STATUS_WON = 'WON'
    STATUS_LOST = 'LOST'

    def __init__(self):
        self._step_aggregation = StepAggregationService()
        self._stalled_detection = StalledDetectionService()

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
        return self._derive_status(steps)

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
        steps = list(cycle.steps.all())
        return self._compute_progress(steps)

    def get_stalled_steps(self, cycle):
        """
        List of stalled steps with reasons.

        Returns list of dicts:
        [{'step_id': uuid, 'step_name': str, 'reason': str, 'reason_display': str}]
        """
        stalled = []
        for step in cycle.steps.all():
            result = self._stalled_detection.detect(step)
            if result['is_stalled']:
                stalled.append({
                    'step_id': str(step.id),
                    'step_name': step.name,
                    'reason': result['reason'],
                    'reason_display': result['reason_display'],
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
        return {
            'cycle_status': self.get_cycle_status(cycle),
            'progress': self.get_progress(cycle),
            'stalled_steps': self.get_stalled_steps(cycle),
            'stalled_steps_count': len(self.get_stalled_steps(cycle)),
            'timeline': self.get_cycle_timeline(cycle),
            'is_at_risk': self.get_cycle_status(cycle) in (
                self.STATUS_AT_RISK, self.STATUS_STALLED
            ),
        }

    # ------------------------------------------------------------------
    # BULK METHOD (by_account timeline — zero DB queries)
    # ------------------------------------------------------------------

    def get_bulk_summaries(self, cycles, step_aggregations=None, stalled_results=None, step_derived_statuses=None,):
        """
        Lightweight summaries for cycle list/timeline view.

        Operates on prefetched data only. Optionally accepts pre-computed
        step_aggregations and stalled_results to avoid recomputation.

        Args:
            cycles: iterable of DecisionCycle with prefetched steps + activities
            step_aggregations: dict from StepAggregationService.get_bulk_aggregation()
                               (optional, computed internally if not provided)
            stalled_results: dict from StalledDetectionService.detect_bulk()
                             (optional, computed internally if not provided)

        Returns dict keyed by cycle.id:
        {
            cycle_id: {
                'cycle_status': str,
                'progress': {total_steps, validated_steps, current_step_name, percentage},
                'stalled_steps_count': int,
                'is_at_risk': bool,
                'has_steps_needing_attention': bool,
            }
        }
        """
        # Collect all steps across cycles for bulk computation
        all_steps = []
        cycle_steps_map = {}  # cycle.id -> [steps]

        for cycle in cycles:
            steps = self._get_prefetched_steps(cycle)
            cycle_steps_map[cycle.id] = steps
            all_steps.extend(steps)

        # Compute bulk stalled if not pre-provided
        if stalled_results is None:
            stalled_results = self._stalled_detection.detect_bulk(all_steps)

        results = {}

        for cycle in cycles:
            steps = cycle_steps_map.get(cycle.id, [])

            # Derive status from derived step statuses + stalled results
            cycle_status = self._derive_status_bulk(steps, stalled_results, step_derived_statuses)

            # Progress from derived step statuses
            progress = self._compute_progress(steps, step_derived_statuses)

            # Count stalled steps
            stalled_count = sum(
                1 for s in steps
                if stalled_results.get(s.id, {}).get('is_stalled', False)
            )

            # Any step needs attention
            has_attention = any(
                stalled_results.get(s.id, {}).get(
                    'needs_next_step_attention', False
                )
                for s in steps
            )

            results[cycle.id] = {
                'cycle_status': cycle_status,
                'progress': progress,
                'stalled_steps_count': stalled_count,
                'is_at_risk': cycle_status in (
                    self.STATUS_AT_RISK, self.STATUS_STALLED
                ),
                'has_steps_needing_attention': has_attention,
            }

        return results

    # ------------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------------

    def _derive_status(self, steps):
        """
        Derive cycle status from step list (single-instance path).
        
        Derives step statuses on the fly since s.status (DB field) is never updated.
        """
        if not steps:
            return self.STATUS_NOT_STARTED

        # Derive step statuses on the fly (single-instance path)
        from .step_status_derivation_service import StepStatusDerivationService
        derivation_service = StepStatusDerivationService()
        statuses = [derivation_service.derive(s)['status'] for s in steps]

        # 1. All NOT_STARTED → cycle not started
        if all(s == 'NOT_STARTED' for s in statuses):
            return self.STATUS_NOT_STARTED

        # 2. Any step WON (CLOSE_WON is a deal-level signal) → cycle won
        if any(s == 'WON' for s in statuses):
            return self.STATUS_WON

        # 3. Any REJECTED (CLOSE_LOST/NOT_QUALIFIED) → cycle lost
        if any(s == 'REJECTED' for s in statuses):
            return self.STATUS_LOST

        # 4. All active steps are ON_HOLD → cycle stalled
        active_statuses = [s for s in statuses if s != 'NOT_STARTED']
        if active_statuses and all(s == 'ON_HOLD' for s in active_statuses):
            return self.STATUS_STALLED

        # 5-6. Check for stalled steps
        has_stalled = False
        stalled_count = 0
        for step in steps:
            result = self._stalled_detection.detect(step)
            if result['is_stalled']:
                has_stalled = True
                stalled_count += 1

        if stalled_count > 1:
            return self.STATUS_STALLED
        if stalled_count == 1:
            return self.STATUS_AT_RISK

        return self.STATUS_IN_PROGRESS

    def _derive_status_bulk(self, steps, stalled_results, step_derived_statuses=None):
        """
        Derive cycle status using pre-computed stalled_results and derived step statuses.
        
        Uses step_derived_statuses (from StepStatusDerivationService) instead of
        s.status (DB field) because step status is DERIVED, never written to DB.
        
        Priority:
        1. All NOT_STARTED → NOT_STARTED
        2. All terminal positive (VALIDATED/WON) → WON
        3. Any REJECTED → LOST
        4. All non-NOT_STARTED are ON_HOLD (no forward motion) → STALLED
        5. Stalled count > 1 → STALLED
        6. Stalled count == 1 → AT_RISK
        7. Otherwise → IN_PROGRESS
        """
        if not steps:
            return self.STATUS_NOT_STARTED

        # Use derived statuses if available, fallback to DB field
        if step_derived_statuses:
            statuses = [
                step_derived_statuses.get(s.id, {}).get('status', s.status)
                for s in steps
            ]
        else:
            statuses = [s.status for s in steps]

        # 1. All NOT_STARTED → cycle not started
        if all(s == 'NOT_STARTED' for s in statuses):
            return self.STATUS_NOT_STARTED

        # 2. Any step WON (CLOSE_WON is a deal-level signal) → cycle won
        #    Note: WON beats REJECTED — if somehow both exist, deal is won
        if any(s == 'WON' for s in statuses):
            return self.STATUS_WON

        # 3. Any REJECTED (CLOSE_LOST/NOT_QUALIFIED) → cycle lost
        if any(s == 'REJECTED' for s in statuses):
            return self.STATUS_LOST

        # 4. All active steps are ON_HOLD (no forward motion anywhere)
        active_statuses = [s for s in statuses if s != 'NOT_STARTED']
        if active_statuses and all(s == 'ON_HOLD' for s in active_statuses):
            return self.STATUS_STALLED

        # 5-6. Count stalled from pre-computed results
        stalled_count = sum(
            1 for s in steps
            if stalled_results.get(s.id, {}).get('is_stalled', False)
        )

        if stalled_count > 1:
            return self.STATUS_STALLED
        if stalled_count == 1:
            return self.STATUS_AT_RISK

        return self.STATUS_IN_PROGRESS

    @staticmethod
    def _compute_progress(steps, step_derived_statuses=None):
        """
        Compute progress dict from step list.
        
        Uses step_derived_statuses when available because s.status (DB field)
        is never updated — all step statuses are derived on read.
        """
        if not steps:
            return {
                'total_steps': 0,
                'validated_steps': 0,
                'current_step_name': None,
                'percentage': 0,
            }

        def _get_status(s):
            if step_derived_statuses:
                return step_derived_statuses.get(s.id, {}).get('status', s.status)
            return s.status

        total = len(steps)
        # WON is also a terminal positive status (counts as validated)
        validated = sum(1 for s in steps if _get_status(s) in ('VALIDATED', 'WON'))

        # Current step: first non-terminal step in order
        current_name = None
        sorted_steps = sorted(steps, key=lambda s: s.order)
        for s in sorted_steps:
            if _get_status(s) not in ('VALIDATED', 'WON', 'REJECTED', 'CANCELLED'):
                current_name = s.name
                break

        percentage = round((validated / total) * 100) if total > 0 else 0

        return {
            'total_steps': total,
            'validated_steps': validated,
            'current_step_name': current_name,
            'percentage': percentage,
        }

    @staticmethod
    def _get_prefetched_steps(cycle):
        """Get steps from Django prefetch cache. Never triggers query."""
        cache = getattr(cycle, '_prefetched_objects_cache', {})
        return list(cache.get('steps', []))