# app_modules/ai_pipelines/services/next_step_extractor.py
"""
NextStepExtractor -- persistence service for NextStepsPipeline (Sprint B4).

Responsibility
--------------
Given a list of raw next-step dicts emitted by the LLM, this service:

  1. Filters out LLM-self-declared weak signals (shared safety filter
     on confidence + is_inferred -- thresholds passed in from the
     pipeline class attributes).

  2. Validates `suggested_activity_type` against the ActivityType
     enum -- values outside the enum are dropped at the extractor
     boundary rather than letting them explode inside
     SignalManager.create(). Mirror of TechStackExtractor's
     defense-in-depth on tech_catalog UUID.

  3. Parses `suggested_due_date` leniently:
        * valid ISO YYYY-MM-DD -> persisted on the row.
        * null / missing       -> persisted as None.
        * invalid format       -> coerced to None, signal STILL
                                  persists (the rep refines at
                                  validation time). This matches the
                                  Impact v1 / Blocker v1 philosophy
                                  of deferring fuzzy fields rather
                                  than dropping otherwise-valuable
                                  signals.

  4. Builds a SignalManager.create() data dict with signal_type =
     'next_step'. SignalManager handles the M2M-aware create path
     introduced in Sprint B2 -- but in v1 we never populate the M2M
     (suggested_contacts), so the M2M branch is a no-op.

  5. Returns the persisted list and the dropped count for audit
     logging by the pipeline (single sub-call -- no per-stage
     breakdown).

v1 deferred field
-----------------
`suggested_contacts` (M2M Contact) is NEVER populated by this
extractor. Attribution of contacts to a next-step suggestion is
deferred to the rep during validation (the Next Steps Tab UI in
Sprint F6 exposes a multi-contact selector). Tracked as TD-7 in
TECH_DEBT.md.

Drop counting
-------------
Every signal that does not result in a persisted row increments the
`dropped_count`, regardless of the reason: safety-filter rejection,
malformed LLM emission, invalid activity_type, validation failure
from SignalManager.create(). The pipeline only needs the integer;
granular reasons live in module logs (WARN level) for ops
investigation.

Concurrency / atomicity
-----------------------
Each SignalManager.create() runs as its own implicit Django save()
transaction. We deliberately do NOT wrap the batch in a single
transaction.atomic(): we WANT partial success when one signal fails
validation -- the others should still be persisted and surfaced to
the rep for review.

Statelessness
-------------
The extractor holds no per-instance state. `persist_extracted()` is
effectively a classmethod with `self`. We keep it as an instance
method for symmetry with TranscriptSignalExtractor.
"""

import datetime
import logging

from app_modules.activities.constants import ActivityType
from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.services.signal_manager import SignalManager
from core.exceptions import StandardizedValidationError

from .safety_filter import passes_safety_filter, safe_float


logger = logging.getLogger(__name__)


# Canonical set of allowed activity-type values, computed once at
# module load. Using a set membership check at the per-signal hot
# path is cheap and avoids a re-iteration of ActivityType.values for
# every raw entry.
_ACTIVITY_TYPE_VALUES = set(ActivityType.values)


class NextStepExtractor:
    """
    Persistence service for NextStepsPipeline.

    Usage:
        extractor = NextStepExtractor()
        persisted, dropped = extractor.persist_extracted(
            raw_signals=[...],
            activity=activity,
            user=user,
            client_id=client_id,
            confidence_min=0.5,
            drop_inferred=True,
        )

    The signature deliberately omits a `stage` parameter
    (NextStepsPipeline is single-stage). All other arguments mirror
    TranscriptSignalExtractor.persist_stage() for symmetry.
    """

    # =========================================================================
    # MAIN ENTRY
    # =========================================================================

    def persist_extracted(
        self,
        *,
        raw_signals,
        activity,
        user,
        client_id,
        confidence_min,
        drop_inferred,
    ):
        """
        Apply safety filter + persist surviving next-step signals.

        Args:
            raw_signals:     list[dict] -- the LLM's emitted signals.
            activity:        app_modules.activities.Activity -- source activity.
            user:            end_users.User -- the rep who triggered the run.
            client_id:       UUID -- tenant scope.
            confidence_min:  float -- LLM signals with confidence < this are
                                       dropped (safety filter).
            drop_inferred:   bool -- if True, drop signals where
                                       is_inferred is True.

        Returns:
            tuple (persisted, dropped_count)
                persisted:     list[NextStepSignal] -- persisted PENDING rows.
                dropped_count: int -- total signals NOT persisted, all
                                reasons combined. The pipeline logs
                                this in AIPipelineRun.sub_calls.
        """
        if not isinstance(raw_signals, list):
            logger.warning(
                'persist_extracted_invalid_input',
                extra={
                    'type': type(raw_signals).__name__,
                    'event': 'ai_pipeline_persist',
                },
            )
            return [], 0

        persisted = []
        dropped_count = 0

        for raw in raw_signals:
            if not isinstance(raw, dict):
                dropped_count += 1
                continue

            # --- Safety filter (shared with TranscriptSignalExtractor) ---
            if not passes_safety_filter(raw, confidence_min, drop_inferred):
                dropped_count += 1
                continue

            # --- Build the create() data dict ---
            data = self._build_next_step_data(raw, activity)
            if data is None:
                # Malformed signal (logged inside the builder).
                dropped_count += 1
                continue

            # --- Persist via SignalManager ---
            try:
                signal = SignalManager.create(
                    data=data,
                    user=user,
                    client_id=client_id,
                )
                persisted.append(signal)
            except StandardizedValidationError as exc:
                logger.warning(
                    'next_step_create_validation_failed',
                    extra={
                        'error': str(exc),
                        'event': 'ai_pipeline_persist',
                    },
                )
                dropped_count += 1
            except Exception as exc:
                # Defensive catch-all: a malformed raw value could trigger
                # a model-level ValidationError or a programming bug.
                # Per-signal failure must not abort the batch.
                logger.error(
                    'next_step_create_unexpected_error',
                    extra={
                        'error': str(exc),
                        'event': 'ai_pipeline_persist',
                    },
                    exc_info=True,
                )
                dropped_count += 1

        return persisted, dropped_count

    # =========================================================================
    # DATA-DICT BUILDER
    # =========================================================================

    def _build_next_step_data(self, raw, activity):
        """
        Build SignalManager.create() data for a NextStepSignal.

        Schema requirements (from next_steps_v1.py):
            suggested_title, suggested_activity_type, source_quote,
            confidence, is_inferred.

        Optional:
            suggested_due_date (ISO YYYY-MM-DD or null).

        Drops on:
            * missing or empty required fields;
            * `suggested_activity_type` outside the ActivityType enum
              (defense in depth -- letting an invalid value reach
              SignalManager.create() would raise inside the model and
              waste a stack trace).

        Lenient on:
            * `suggested_due_date` -- invalid format coerced to None,
              the signal still persists. The rep refines during
              validation. Aligned with Impact v1's "metric_text
              deferred" philosophy.

        v1 deferred fields (NOT extracted from the LLM):
            * suggested_contacts (M2M) -- TD-7.
        """
        required = ('suggested_title', 'suggested_activity_type', 'source_quote')
        if not all(k in raw and raw[k] is not None for k in required):
            return None

        suggested_title = str(raw['suggested_title']).strip()
        source_quote    = str(raw['source_quote']).strip()
        if not suggested_title or not source_quote:
            return None

        # --- Defense in depth: activity_type must be a known DB value ---
        suggested_activity_type = raw.get('suggested_activity_type')
        if suggested_activity_type not in _ACTIVITY_TYPE_VALUES:
            logger.warning(
                'next_step_invalid_activity_type',
                extra={
                    'activity_type': str(suggested_activity_type),
                    'event': 'ai_pipeline_persist',
                },
            )
            return None

        # --- Lenient due-date parsing ---
        suggested_due_date = self._parse_iso_date(raw.get('suggested_due_date'))

        return {
            'signal_type':              'next_step',
            'account':                  activity.account,
            'source_activity':          activity,
            'source':                   SignalSource.LLM_EXTRACTED,
            'status':                   SignalStatus.PENDING,
            'suggested_title':          suggested_title,
            'suggested_activity_type':  suggested_activity_type,
            'suggested_due_date':       suggested_due_date,
            'source_quote':             source_quote,
            'confidence':               safe_float(raw.get('confidence')),
            'is_inferred':              bool(raw.get('is_inferred')),

            # v1: suggested_contacts deferred to validation UI -- TD-7.
            # The M2M is left at its empty default; SignalManager's
            # M2M-aware create path (Sprint B2) is a no-op when the key
            # is not present in `data`.
        }

    # =========================================================================
    # DATE PARSING
    # =========================================================================

    @staticmethod
    def _parse_iso_date(value):
        """
        Parse a YYYY-MM-DD ISO date string to a datetime.date.

        Returns:
            datetime.date on success.
            None on:
                * value is None / missing.
                * value is not a string or is empty after strip.
                * value does not match ISO YYYY-MM-DD format.

        Lenient: invalid format does not raise -- the calling builder
        treats None as "rep refines later". Matches the philosophy of
        deferring fuzzy fields to validation rather than dropping
        otherwise-valuable signals on a date parse failure.
        """
        if value is None:
            return None
        if not isinstance(value, str):
            return None
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return datetime.date.fromisoformat(stripped)
        except ValueError:
            logger.warning(
                'next_step_due_date_parse_failed',
                extra={
                    'raw_value': stripped[:32],
                    'event': 'ai_pipeline_persist',
                },
            )
            return None
