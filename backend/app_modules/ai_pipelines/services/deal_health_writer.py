# app_modules/ai_pipelines/services/deal_health_writer.py
"""
DealHealthWriter — validates the LLM diagnostic output and persists
a DealHealthSnapshot.

Structural validation only (no safety filter — the output is a single
JSON object, not a list of signals). On validation failure, raises
PromptParseError so the pipeline maps it to PARSE_ERROR.
"""

import logging

from ..prompts.base import PromptParseError


logger = logging.getLogger(__name__)


_REQUIRED_DIMENSION_KEYS = (
    'problem_recognized',
    'felt_pain',
    'impact_understood',
    'desired_gain',
    'urgency',
    'willingness_to_act',
    'solution_trust',
)

_VALID_STATUSES = frozenset({
    'confirmed',
    'suggested',
    'unclear',
    'missing_evidence',
    'contradictory',
})

_VALID_GAP_KINDS = frozenset({'qualification', 'procedural'})


class DealHealthWriter:
    """
    Validates and persists a DealHealthSnapshot from parsed LLM output.

    Usage:
        snapshot = DealHealthWriter().write(
            parsed=parsed_json,
            decision_cycle=dc,
            run=pipeline_run,
            user=user,
            client_id=client_id,
        )
    """

    def write(self, *, parsed, decision_cycle, run, user, client_id):
        """
        Validate the parsed diagnostic JSON and create a DealHealthSnapshot.

        Args:
            parsed:          dict — the parsed LLM response.
            decision_cycle:  DecisionCycle instance.
            run:             AIPipelineRun instance (linked to the snapshot).
            user:            User who triggered the pipeline.
            client_id:       UUID — tenant scope.

        Returns:
            DealHealthSnapshot: the persisted snapshot.

        Raises:
            PromptParseError: if the parsed JSON fails structural validation.
        """
        self._validate(parsed)

        from app_modules.decision_cycles.models import DealHealthSnapshot

        snapshot = DealHealthSnapshot(
            decision_cycle=decision_cycle,
            diagnostic=parsed,
            pipeline_run=run,
        )
        snapshot.save(user=user, client_id=client_id)

        logger.info(
            'deal_health_snapshot_created',
            extra={
                'snapshot_id': str(snapshot.id),
                'cycle_id': str(decision_cycle.id),
                'run_id': str(run.id),
                'event': 'ai_pipeline_persist',
            },
        )

        return snapshot

    # =========================================================================
    # STRUCTURAL VALIDATION
    # =========================================================================

    def _validate(self, parsed):
        if not isinstance(parsed, dict):
            raise PromptParseError(
                'Deal health diagnostic must be a JSON object.'
            )

        # global_reading
        if not isinstance(parsed.get('global_reading'), str):
            raise PromptParseError(
                'Missing or invalid "global_reading" (expected string).'
            )

        # dimensions
        self._validate_dimensions(parsed.get('dimensions'))

        # discovery_gaps
        self._validate_gaps(parsed.get('discovery_gaps'))

        # levers
        self._validate_levers(parsed.get('levers'))

    def _validate_dimensions(self, dimensions):
        if not isinstance(dimensions, list):
            raise PromptParseError(
                'Missing or invalid "dimensions" (expected list).'
            )

        if len(dimensions) != 7:
            raise PromptParseError(
                f'Expected exactly 7 dimensions, got {len(dimensions)}.'
            )

        seen_keys = []
        for dim in dimensions:
            if not isinstance(dim, dict):
                raise PromptParseError(
                    'Each dimension must be a JSON object.'
                )

            key = dim.get('key')
            if key not in _REQUIRED_DIMENSION_KEYS:
                raise PromptParseError(
                    f'Unknown or missing dimension key: "{key}". '
                    f'Expected one of: {", ".join(_REQUIRED_DIMENSION_KEYS)}.'
                )

            status = dim.get('status')
            if status not in _VALID_STATUSES:
                raise PromptParseError(
                    f'Invalid status "{status}" for dimension "{key}". '
                    f'Expected one of: {", ".join(sorted(_VALID_STATUSES))}.'
                )

            seen_keys.append(key)

        expected = list(_REQUIRED_DIMENSION_KEYS)
        if seen_keys != expected:
            raise PromptParseError(
                f'Dimension keys must appear in order: {expected}. '
                f'Got: {seen_keys}.'
            )

    @staticmethod
    def _validate_gaps(gaps):
        if not isinstance(gaps, list):
            raise PromptParseError(
                'Missing or invalid "discovery_gaps" (expected list).'
            )

        for gap in gaps:
            if not isinstance(gap, dict):
                raise PromptParseError(
                    'Each discovery gap must be a JSON object.'
                )
            kind = gap.get('kind')
            if kind not in _VALID_GAP_KINDS:
                raise PromptParseError(
                    f'Invalid gap kind "{kind}". '
                    f'Expected "qualification" or "procedural".'
                )

    @staticmethod
    def _validate_levers(levers):
        if not isinstance(levers, dict):
            raise PromptParseError(
                'Missing or invalid "levers" (expected object).'
            )

        for group in ('desires', 'value', 'cost', 'constraints'):
            items = levers.get(group)
            if not isinstance(items, list):
                raise PromptParseError(
                    f'Missing or invalid levers.{group} (expected list).'
                )
