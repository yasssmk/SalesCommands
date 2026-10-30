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

Quote check (Sprint Next steps 3.6)
----------------------------------
With the transcript, each stored next step's source_quote (speaker label
removed) is checked by people_evidence.check_quote_evidence -- the TD-279
"quote found in the transcript" step, nothing of the role. Not found -> the
next step is KEPT, metadata.evidence_check = {status: "quote_not_found",
detail: {parts, parts_found}} (PeopleEvidenceStatus values: the front's
PEOPLE_EVIDENCE_PILL map applies), counted (quote_not_found); a quote found
leaves no mark. Never a deletion.

Prompt v2 fields (Sprint Next steps 3.4)
---------------------------------------
  * suggested_date_text (truncated to the column), carried_by_prospect
    (true only when the answer says true), suggested_topics,
    suggested_success_criterion, suggested_internal_names (strings only,
    stripped, non-empty, once each) are persisted as given;
  * suggested_decision_step: a step ref (NEXT_STEPS_STEP_REF_FORMAT, "S4")
    -> the DecisionStep of that order in the next step's cycle (the source
    activity's, same tenant); an unknown / malformed ref, or no cycle ->
    null, counted (step_ref_unknown);
  * suggested_people_names: each prospect name -> a PeopleSignal by
    participant_refs.resolve_people_signal_by_name (the TD-279 word rule, on
    identities) among the NON-rejected People of the cycle and of the source
    activity, same tenant and account -> suggested_people; a name not linked
    (none / ambiguous) stays in suggested_people_names, as written;
  * dedup WITHIN this answer only: NEXT_STEP_DEDUP_KEY (constants.py), the
    first kept, the others dropped (counted).
A v1 answer (no such keys) keeps the column defaults. The counters of the
LAST persist_extracted call are left in `last_persist_counts`, read by the
pipeline for its sub_calls entry.

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
As of F8-3-FIX, the pipeline wraps signal persistence in a single
transaction.atomic() to enforce all-or-nothing semantics on hard crashes
(Ctrl+C, DB errors, OOM). This inverts the prior partial-success design
because:
- Partial success creates ambiguous UX (user sees orphaned signals)
- Idempotency keys make retries free (no risk of duplicates)
- Hard crashes can't be caught by Python try/except — only PostgreSQL
  atomic rollback can guarantee no orphan rows

Note: per-stage LLM errors (timeout, rate-limit, parse error) STILL use
local try/except and remain partial-success — that behavior is preserved.

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

import re

from ..constants import NEXT_STEP_DEDUP_KEY, NEXT_STEPS_STEP_REF_FORMAT
from ..constants import PeopleEvidenceStatus
from .participant_refs import resolve_people_signal_by_name
from .people_evidence import check_quote_evidence
from .safety_filter import passes_safety_filter, safe_float
from .transcript_text import TranscriptText, normalize_text


logger = logging.getLogger(__name__)


# Canonical set of allowed activity-type values, computed once at
# module load. Using a set membership check at the per-signal hot
# path is cheap and avoids a re-iteration of ActivityType.values for
# every raw entry.
_ACTIVITY_TYPE_VALUES = set(ActivityType.values)

# "S{order}" -> ^S(\d+)$ : the step reference of the next_steps context.
_STEP_REF_RE = re.compile(
    '^' + re.escape(NEXT_STEPS_STEP_REF_FORMAT).replace(re.escape('{order}'), r'(\d+)') + '$'
)


def _clean_names(values):
    """Strings only, stripped, non-empty, once each, in order."""
    names = []
    for value in values if isinstance(values, list) else []:
        if isinstance(value, str) and value.strip() and value.strip() not in names:
            names.append(value.strip())
    return names


def _clean_text(value):
    return value.strip() if isinstance(value, str) else ''


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
            drop_inferred=False,
            transcript=transcript,
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
        source_run=None,
        transcript=None,
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
            transcript:      str | None -- the analysed transcript; when
                                       given, a speaker label of THIS
                                       transcript copied at the head of
                                       source_quote is removed (TD-282 (2),
                                       same rule as TranscriptSignalExtractor).

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
        transcript_text = TranscriptText(transcript) if transcript is not None else None
        self.last_persist_counts = counts = {
            'step_ref_unknown': 0, 'deduplicated': 0,
            'people_linked': 0, 'people_unlinked': 0, 'quote_not_found': 0,
        }
        seen_keys = set()
        people_candidates = None   # read once, on the first prospect name

        for raw in raw_signals:
            if not isinstance(raw, dict):
                dropped_count += 1
                continue

            # --- Safety filter (shared with TranscriptSignalExtractor) ---
            if not passes_safety_filter(raw, confidence_min, drop_inferred):
                dropped_count += 1
                continue

            # TD-282 (2): "Thomas Lefèvre: Envoyez-les..." -> "Envoyez-les..."
            # when the prefix is a speaker label of THIS transcript (never
            # another ":").
            if transcript_text is not None and 'source_quote' in raw:
                raw = {**raw, 'source_quote': transcript_text.strip_speaker_label(
                    raw['source_quote'])}

            # --- Build the create() data dict ---
            data = self._build_next_step_data(raw, activity)
            if data is None:
                # Malformed signal (logged inside the builder).
                dropped_count += 1
                continue

            # --- Dedup within THIS answer (never across activities) ---
            key = self._dedup_key(data)
            if key in seen_keys:
                counts['deduplicated'] += 1
                dropped_count += 1
                continue
            seen_keys.add(key)

            # --- v2: step ref -> DecisionStep; prospect names -> People ---
            ref = raw.get('suggested_decision_step')
            step = self._resolve_step_ref(ref, activity)
            if step is None and isinstance(ref, str) and ref.strip():
                counts['step_ref_unknown'] += 1
            data['suggested_decision_step'] = step

            names = _clean_names(raw.get('suggested_people_names'))
            if names and people_candidates is None:
                people_candidates = self._people_candidates(activity)
            linked, kept = [], []
            for name in names:
                people = resolve_people_signal_by_name(name, people_candidates or [])
                if people is None:
                    kept.append(name)
                elif people not in linked:
                    linked.append(people)
            counts['people_linked'] += len(names) - len(kept)
            counts['people_unlinked'] += len(kept)
            data['suggested_people_names'] = kept
            if linked:
                data['suggested_people'] = linked

            # --- 3.6: the quote checked against the transcript (TD-279 step
            # a)); not found -> KEPT and marked, never dropped ---
            if transcript_text is not None:
                status, detail = check_quote_evidence(data['source_quote'], transcript_text)
                if status != PeopleEvidenceStatus.OK:
                    counts['quote_not_found'] += 1
                    data['metadata'] = {'evidence_check': {'status': status.value, 'detail': detail}}

            if source_run is not None:
                data['source_run'] = source_run

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

    # Counters of the LAST persist_extracted call (module docstring).
    last_persist_counts = None

    # =========================================================================
    # v2 FIELDS -- step ref, People candidates, dedup key
    # =========================================================================

    @staticmethod
    def _resolve_step_ref(ref, activity):
        """The DecisionStep a step ref designates in the activity's cycle
        (same tenant); None for no / unknown / malformed ref or no cycle."""
        from app_modules.decision_cycles.models import DecisionStep

        match = _STEP_REF_RE.match(ref.strip()) if isinstance(ref, str) else None
        if match is None or activity.decision_cycle_id is None:
            return None
        return DecisionStep.objects.filter(
            cycle_id=activity.decision_cycle_id,
            client_id=activity.client_id,
            order=int(match.group(1)),
        ).first()

    @staticmethod
    def _people_candidates(activity):
        """The NON-rejected People of the activity's cycle and of the
        activity itself, same tenant and account."""
        from django.db.models import Q
        from app_modules.signals.models import PeopleSignal

        scope = Q(source_activity=activity)
        if activity.decision_cycle_id is not None:
            scope |= Q(decision_cycle_id=activity.decision_cycle_id)
        return list(
            PeopleSignal.objects
            .filter(scope, client_id=activity.client_id, account_id=activity.account_id)
            .exclude(status=SignalStatus.REJECTED)
            .select_related('target_contact')
        )

    @staticmethod
    def _dedup_key(data):
        return tuple(
            normalize_text(data.get(field)) if isinstance(data.get(field), str)
            else data.get(field)
            for field in NEXT_STEP_DEDUP_KEY
        )

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
            suggested_due_date (ISO YYYY-MM-DD or null),
            suggested_objective (free text; the proposed activity's
            purpose / stakes — feeds Activity.call_to_action).

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

        # --- Objective (the proposed activity's purpose / stakes) ---
        # LLM-emitted free text; tolerated absent (persisted empty, never a
        # drop). Feeds Activity.call_to_action at materialisation via the
        # mapping in activities/serializers.py.
        suggested_objective = str(raw.get('suggested_objective') or '').strip()

        # --- Prompt v2 scalar fields (Sprint Next steps 3.4) ---
        from app_modules.signals.models import NextStepSignal
        date_text_max = NextStepSignal._meta.get_field('suggested_date_text').max_length

        return {
            'signal_type':              'next_step',
            'account':                  activity.account,
            'source_activity':          activity,
            'source':                   SignalSource.LLM_EXTRACTED,
            'status':                   SignalStatus.PENDING,
            'suggested_title':          suggested_title,
            'suggested_activity_type':  suggested_activity_type,
            'suggested_due_date':       suggested_due_date,
            'suggested_objective':      suggested_objective,
            'suggested_date_text':      _clean_text(raw.get('suggested_date_text'))[:date_text_max],
            'carried_by_prospect':      raw.get('carried_by_prospect') is True,
            'suggested_topics':         _clean_text(raw.get('suggested_topics')),
            'suggested_success_criterion': _clean_text(raw.get('suggested_success_criterion')),
            'suggested_internal_names': _clean_names(raw.get('suggested_internal_names')),
            'source_quote':             source_quote,
            'confidence':               safe_float(raw.get('confidence')),
            'is_inferred':              bool(raw.get('is_inferred')),

            # v1: suggested_contacts deferred to validation UI -- TD-7.
            # The M2M is left at its empty default; SignalManager's
            # M2M-aware create path (Sprint B2) is a no-op when the key
            # is not present in `data`.
            #
            # THIS is the reason suggested_contacts is a DORMANT capability:
            # the field is fully wired downstream (API write + front
            # display) but the extraction pipeline never fills it, because
            # the key is intentionally absent here. Do not add it back until
            # suggested-contact resolution lands (TD-7).
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
