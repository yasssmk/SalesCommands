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

    def write(self, *, parsed, decision_cycle, run, user, client_id,
              declared_step=None, prompt_versions=None, sources_cursor=None,
              schema_version=None):
        """
        Validate the parsed diagnostic JSON and create a DealHealthSnapshot.

        Args:
            parsed:          dict — the parsed LLM response.
            decision_cycle:  DecisionCycle instance.
            run:             AIPipelineRun instance (linked to the snapshot).
            user:            User who triggered the pipeline.
            client_id:       UUID — tenant scope.
            declared_step:   PipelineStep value of the cycle's current step
                             when the diagnostic was produced (derived once
                             by the evidence builder), or None.
            prompt_versions: the pipeline PROMPT_VERSIONS (copied: the run
                             FK is SET_NULL). Sprint « Deal health v2 »,
                             step 2.
            sources_cursor:  per source type, the latest change read by this
                             diagnostic (the evidence builder's cursor, step
                             3b) — the next run reads only what is newer.
            schema_version:  the shape of `parsed` (DEAL_HEALTH_SCHEMA_V1
                             default, V2 for the « manager / coach »
                             diagnostic, step 5): picks the validation and
                             is persisted; a V2 also persists its
                             estimated step.

        Returns:
            DealHealthSnapshot: the persisted snapshot.

        Raises:
            PromptParseError: if the parsed JSON fails structural validation.
        """
        from app_modules.decision_cycles.constants import (
            DEAL_HEALTH_SCHEMA_V1,
            DEAL_HEALTH_SCHEMA_V2,
        )
        from app_modules.decision_cycles.models import DealHealthSnapshot

        version = schema_version or DEAL_HEALTH_SCHEMA_V1
        self._validate(parsed)
        estimated = {}
        if version == DEAL_HEALTH_SCHEMA_V2:
            self._validate_v2(parsed)
            estimated = parsed['estimated_step']

        snapshot = DealHealthSnapshot(
            decision_cycle=decision_cycle,
            diagnostic=parsed,
            pipeline_run=run,
            declared_step=declared_step,
            prompt_versions=dict(prompt_versions or {}),
            sources_cursor=dict(sources_cursor or {}),
            schema_version=version,
            estimated_step=estimated.get('step'),
            estimated_step_reason=estimated.get('reason', ''),
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

    # =========================================================================
    # v2 — « MANAGER / COACH » DIAGNOSTIC (sprint « Deal health v2 », step 5)
    # =========================================================================

    def _validate_v2(self, parsed):
        """The v2 keys, on top of the v1 validation (every v1 key is kept,
        amendment A5). A refusal is a PromptParseError: nothing is written
        (no snapshot, no profile)."""
        from app_modules.ai_pipelines.constants import (
            DEAL_HEALTH_BANT_LETTERS,
            DEAL_HEALTH_BANT_STATUSES,
            DEAL_HEALTH_MISSING_INFO_LEVELS,
            DEAL_HEALTH_TOP_ARGUMENTS_MAX,
        )
        from app_modules.decision_cycles.constants import (
            PIPELINE_STEPS_ORDER,
            PROFILE_CONVICTION_STATE,
            STAKEHOLDER_PROFILE_FIELDS,
        )
        from app_modules.decision_cycles.services.stakeholder_service import (
            validate_ai_profile_values,
        )
        from core.exceptions import StandardizedValidationError

        for key in ('summary', 'strategic_conclusion'):
            if not isinstance(parsed.get(key), str) or not parsed[key].strip():
                raise PromptParseError(f'Missing or invalid "{key}" (expected text).')

        for axis in ('needs_and_urgency', 'credibility', 'fit_and_value'):
            value = parsed.get(axis)
            if not isinstance(value, dict) or value.get('status') not in _VALID_STATUSES \
                    or not isinstance(value.get('assessment'), str):
                raise PromptParseError(
                    f'Missing or invalid "{axis}" (expected {{status, assessment}}).'
                )

        if not isinstance(parsed.get('buying_process'), dict):
            raise PromptParseError('Missing or invalid "buying_process" (expected object).')

        bant = parsed.get('bant')
        if not isinstance(bant, dict):
            raise PromptParseError('Missing or invalid "bant" (expected object).')
        for letter in DEAL_HEALTH_BANT_LETTERS:
            item = bant.get(letter)
            if not isinstance(item, dict) or item.get('status') not in DEAL_HEALTH_BANT_STATUSES \
                    or not isinstance(item.get('reason'), str):
                raise PromptParseError(
                    f'Invalid "bant.{letter}": expected {{status: '
                    f'{" | ".join(DEAL_HEALTH_BANT_STATUSES)}, reason}}.'
                )

        for key in ('levers_to_invest', 'missing_info', 'top_arguments', 'stakeholders'):
            if not isinstance(parsed.get(key), list):
                raise PromptParseError(f'Missing or invalid "{key}" (expected list).')
        if not isinstance(parsed.get('objectives'), dict):
            raise PromptParseError('Missing or invalid "objectives" (expected object).')

        for item in parsed['missing_info']:
            if not isinstance(item, dict) or item.get('level') not in DEAL_HEALTH_MISSING_INFO_LEVELS:
                raise PromptParseError(
                    f'Invalid "missing_info" level: expected one of '
                    f'{", ".join(DEAL_HEALTH_MISSING_INFO_LEVELS)}.'
                )

        estimated = parsed.get('estimated_step')
        if not isinstance(estimated, dict) or estimated.get('step') not in [str(s) for s in PIPELINE_STEPS_ORDER] \
                or not isinstance(estimated.get('reason'), str):
            raise PromptParseError(
                'Invalid "estimated_step": expected {step: one of the 5 pipeline steps, reason}.'
            )

        for target in parsed['top_arguments']:
            if not isinstance(target, dict) or not isinstance(target.get('arguments'), list) \
                    or len(target['arguments']) > DEAL_HEALTH_TOP_ARGUMENTS_MAX:
                raise PromptParseError(
                    f'Invalid "top_arguments": at most {DEAL_HEALTH_TOP_ARGUMENTS_MAX} '
                    f'arguments per target.'
                )

        for entry in parsed['stakeholders']:
            if not isinstance(entry, dict) or not isinstance(entry.get('ref'), str):
                raise PromptParseError('Invalid "stakeholders" entry (expected {ref, ...}).')
            if not entry.get(PROFILE_CONVICTION_STATE):
                raise PromptParseError('Missing "conviction_state" for a stakeholder.')
            try:
                validate_ai_profile_values(
                    {field: entry.get(field) for field in STAKEHOLDER_PROFILE_FIELDS}
                )
            except StandardizedValidationError as exc:
                raise PromptParseError(f'Invalid stakeholder profile: {exc.detail}') from exc

    @staticmethod
    def apply_profiles(*, parsed, decision_cycle, run, roster):
        """
        Write the v2 stakeholder profiles through THE profile write point
        (stakeholder_service.apply_ai_profile, with the run id). A label is
        resolved server side against the prompt's roster (llm_people), never
        by the LLM; an unknown label, or a person with no stakeholder row on
        the cycle, is skipped and traced.

        Returns:
            dict — the counters recorded in the run's sub_calls
            (persist_counts): profiles_written, profile_fields_kept,
            unknown_stakeholder_refs, refs_without_stakeholder.
        """
        from app_modules.ai_pipelines.services.llm_people import stakeholder_for
        from app_modules.decision_cycles.constants import STAKEHOLDER_PROFILE_FIELDS
        from app_modules.decision_cycles.services.stakeholder_service import (
            apply_ai_profile,
        )

        counts = {
            'profiles_written': 0,
            'profile_fields_kept': 0,
            'unknown_stakeholder_refs': [],
            'refs_without_stakeholder': [],
        }
        entries = parsed.get('stakeholders') if isinstance(parsed, dict) else None
        if not entries:
            return counts
        for entry in entries:
            ref = entry.get('ref', '')
            identity = roster.identity_of(ref) if roster is not None else None
            if identity is None:
                counts['unknown_stakeholder_refs'].append(ref)
                continue
            stakeholder = stakeholder_for(decision_cycle, identity)
            if stakeholder is None:
                counts['refs_without_stakeholder'].append(ref)
                continue
            result = apply_ai_profile(
                stakeholder,
                {field: entry.get(field) for field in STAKEHOLDER_PROFILE_FIELDS},
                run,
            )
            if result['written']:
                counts['profiles_written'] += 1
            counts['profile_fields_kept'] += len(result['kept'])
        if counts['unknown_stakeholder_refs'] or counts['refs_without_stakeholder']:
            logger.warning(
                'deal_health_profiles_unresolved_refs',
                extra={
                    'run_id': str(run.id),
                    'unknown_count': len(counts['unknown_stakeholder_refs']),
                    'without_stakeholder_count': len(counts['refs_without_stakeholder']),
                    'event': 'ai_pipeline_persist',
                },
            )
        return counts
