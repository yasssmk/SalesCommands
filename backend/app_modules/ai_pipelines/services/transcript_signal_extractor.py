# app_modules/ai_pipelines/services/transcript_signal_extractor.py
"""
TranscriptSignalExtractor -- per-stage persistence service for the
TranscriptSignalsPipeline.

Responsibility
--------------
Given a list of raw signal dicts emitted by the LLM for ONE pipeline
stage (pain / objective / impact / techstack / blocker / constraint),
this service:

  1. Filters out LLM-self-declared weak signals (safety filter on
     confidence + is_inferred -- thresholds passed in from the
     pipeline class attributes).
  2. Builds a SignalManager.create() data dict per surviving signal,
     applying stage-specific mappings:
        - Pain        -> 1:1 passthrough.
        - Objective   -> 1:1 passthrough + force scope_level=BUSINESS
                          (and target_contact / target_department stay
                          unset, satisfying ObjectiveSignal.clean()'s
                          BUSINESS branch).
        - Impact      -> 1:1 passthrough + force scope_level=BUSINESS;
                          metric_text and human_impact left unset (rep
                          fills during validation). impact_type is
                          emitted by the LLM and persisted directly.
        - TechStack   -> raw `tech_name` passthrough (normalised by
                          TechStackSignal.save(), not here) + the
                          qualification booleans (is_competitor /
                          is_to_replace); usage_scope (SCALE) filtered to
                          TEAM / COMPANY / UNKNOWN; usage_departments (WHO)
                          resolved to a multi-department M2M via
                          resolve_tech_usage_departments. `is_integration`
                          is NO LONGER extracted -- a required integration is
                          now a ConstraintSignal of nature=TECHNICAL. No
                          catalogue lookup -- see below. The legacy single-FK
                          usage_department is no longer filled (retired).
        - Blocker     -> 1:1 passthrough on summary / source_quote /
                          confidence / is_inferred. `contact` (FK
                          Contact, optional) is NOT extracted in v1
                          -- rep attributes during validation (TD-6).
        - Constraint  -> summary + nature (validated against
                          ConstraintNature, out-of-list dropped) + rigidity
                          (invalid folds to FIRM) + target_department via the
                          shared scope resolver. NEVER what/dimension.
  3. Calls SignalManager.create() for each surviving signal.
  4. Returns the persisted list and the dropped count for audit
     logging by the pipeline.

Drop counting
-------------
Every signal that does not result in a persisted row increments the
`dropped_count`, regardless of the reason: safety-filter rejection,
malformed LLM emission, cross-tenant UUID, validation failure from
SignalManager.create(). The pipeline only needs the integer; granular
reasons live in module logs (WARN level) for ops investigation.

Tech identity is free text (S10)
--------------------------------
The techstack stage used to ask the LLM to match each mention against
the tenant's TechCatalog and emit a UUID, which this service then
re-validated against activity.client_id as defense in depth against a
hallucinated or cross-tenant id.

That whole mechanism is gone, along with the catalogue itself: the LLM
emits the tool name as free text plus the qualification booleans, and
the extractor writes them to `tech_name` / `is_competitor` /
`is_to_replace`. (`is_integration` was retired from this path -- see the
TechStack line above.)

The cross-tenant attack surface disappeared with the UUID: no
tenant-owned identifier is sent to the model or read back from it on
this path.

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
The extractor holds no per-instance state. `persist_stage()` is
effectively a classmethod with `self`. We keep it as an instance
method for symmetry with future variants (e.g. a v2 extractor with
a different filter strategy could subclass).
"""

import logging
import re

from django.db import transaction
from django.utils import timezone

from app_modules.signals.constants import (
    ConstraintNature,
    Rigidity,
    ScopeLevel,
    SignalSource,
    SignalStatus,
)
from app_modules.signals.models import TechStackSignal
from app_modules.signals.services.signal_manager import SignalManager
from core.exceptions import StandardizedValidationError

from .safety_filter import passes_safety_filter, safe_float


logger = logging.getLogger(__name__)


# Allowed values for TechStack usage_scope. usage_scope is the SCALE axis
# (how widely the tool is used) and is kept as-is by the mono->multi
# department migration. Any other value (including "DEPARTMENT", which the
# prompt no longer asks for -- the WHO is carried by usage_departments now)
# is demoted to None.
_TECHSTACK_USAGE_SCOPE_ALLOWED = {'TEAM', 'COMPANY', 'UNKNOWN'}


def _build_department_resolution_index():
    """
    Build the name -> StandardDepartment resolution index over the whole
    (global) StandardDepartment vocabulary.

    Two lookup layers, both keyed on lowercased strings so resolution is
    case-insensitive:

      by_value: the full department name ("customer support" ->
                Customer Support). This is the exact contract the prompt
                asks for -- the grounding list injected in the context
                layer -- made case-tolerant.

      by_word:  a SINGLE word that appears in EXACTLY ONE department name
                ("support" -> Customer Support, "engineering" ->
                Engineering). Words shared by several departments
                ("management" is in General / Product / Security & Risk
                Management; "operations" is in Operations and Retail
                Operations) are AMBIGUOUS and deliberately LEFT OUT -- an
                ambiguous role-word must not resolve to an arbitrary
                department (the "do not over-correct" rule). This is what
                lets the model's transcript-echoed function word ("support"
                for "Customer Support") resolve without a fuzzy match that
                could bind the wrong row.

    Returns (by_value, by_word) -- two dicts of lowercased-key ->
    StandardDepartment.
    """
    from app_modules.core_modules.models import StandardDepartment

    departments = list(StandardDepartment.objects.all())

    by_value = {}
    word_hits = {}  # word -> set of dept ids that contain it (ambiguity check)
    word_dept = {}  # word -> a dept carrying it

    for dept in departments:
        value_lc = dept.name.strip().lower()
        by_value[value_lc] = dept
        for word in re.findall(r'[a-z0-9]+', value_lc):
            word_hits.setdefault(word, set()).add(dept.id)
            word_dept[word] = dept

    # Keep only UNAMBIGUOUS words (present in exactly one department) and
    # never a word that is itself a full department value (avoid shadowing
    # the exact layer with a weaker one).
    by_word = {
        word: word_dept[word]
        for word, ids in word_hits.items()
        if len(ids) == 1 and word not in by_value
    }

    return by_value, by_word


def resolve_tech_usage_departments(raw):
    """
    Resolve the list of departments that USE a tool from the LLM payload.

    The techstack stage emits `usage_departments`: an array of department
    names (from the StandardDepartment vocabulary injected in the context
    layer) explicitly designated as USERS of the tool. This resolves each
    name to a StandardDepartment row and returns the deduplicated list to
    assign to the M2M TechStackSignal.usage_departments.

    Resolution against the SAME controlled vocabulary the shared scope
    resolver (resolve_scope_and_department, above) uses, but made robust to
    the model echoing the transcript's function word instead of the exact
    list label ("support" for "Customer Support", the smoke-proven bug):

      1. case-insensitive EXACT match on the department name
         ("customer support" -> Customer Support);
      2. else a case-insensitive UNAMBIGUOUS single-word match
         ("support" -> Customer Support, because "support" appears in only
         one department name). A word shared by several departments is
         ambiguous and NEVER resolves -- no over-correction.

    StandardDepartment is global reference data (no client_id of its own),
    so the lookup is tenant-safe exactly as for pain/objective/impact/
    constraint -- the tenant boundary lives on the signal, not on the
    shared department rows.

    Guards:
      * a name that resolves to nothing is dropped (never invented);
      * "General Management" is dropped -- a company-wide / executive owner
        is NOT a using department (the company-wide reading is carried by
        usage_scope=COMPANY);
      * duplicates collapse (order-preserving) so ["Sales", "Sales"] -> one.

    A missing / non-list / empty `usage_departments`, or one that resolves
    to nothing, yields [] -- a valid "nobody designated" state.

    Returns:
        list[StandardDepartment] -- possibly empty, deduplicated, in the
        order the model emitted the names.
    """
    from app_modules.core_modules.models import StandardDepartment

    names = raw.get('usage_departments')
    if not isinstance(names, list):
        return []

    by_value, by_word = _build_department_resolution_index()

    resolved = []
    seen_ids = set()
    for name in names:
        if not name or not isinstance(name, str):
            continue
        key = name.strip().lower()
        if not key:
            continue
        # Layer 1: exact (case-insensitive). Layer 2: unambiguous word.
        dept = by_value.get(key) or by_word.get(key)
        if dept is None:
            continue
        if dept.name == StandardDepartment.DepartmentChoices.GENERAL_MANAGEMENT:
            continue
        if dept.id in seen_ids:
            continue
        seen_ids.add(dept.id)
        resolved.append(dept)

    return resolved


def resolve_scope_and_department(raw):
    """
    Resolve (scope_level, target_department) for a qualification signal
    (pain / objective / impact) from the LLM-emitted payload.

    Shared by the three builders so the guards live in ONE place.

    The v0 offers the model only BUSINESS | DEPARTMENT (PERSONAL is not
    surfaced in the prompt). Three safety-net guards fold anything that
    would otherwise produce an inconsistent row back to BUSINESS:

      GUARD 1 (anti-PERSONAL): any scope_level other than the literal
        "DEPARTMENT" -- including "PERSONAL", missing, or junk -- resolves
        to BUSINESS with no department. Only an explicit DEPARTMENT can
        carry a department.

      unresolved department: a DEPARTMENT scope whose target_department
        name does not resolve to a StandardDepartment row folds to
        BUSINESS + None. The signal is NOT dropped and nothing is raised
        -- an unresolved department is business-normal (rep refines
        later).

      GUARD 2 (general-management -> BUSINESS): a resolved department that
        is "General Management" folds to BUSINESS + None. A company-wide /
        executive observation is BUSINESS by definition, even if the model
        tagged the GM department.

    Returns:
        tuple (scope_level: str, target_department: StandardDepartment | None)
    """
    from app_modules.core_modules.models import StandardDepartment

    scope_raw = raw.get('scope_level')

    # GUARD 1 — anything that is not an explicit DEPARTMENT is BUSINESS.
    if scope_raw != ScopeLevel.DEPARTMENT:
        return ScopeLevel.BUSINESS, None

    # DEPARTMENT requested — resolve the department by exact name.
    name = raw.get('target_department')
    department = None
    if name:
        department = (
            StandardDepartment.objects.filter(name=name).first()
        )

    # Unresolved department name -> fold to BUSINESS (no drop, no raise).
    if department is None:
        return ScopeLevel.BUSINESS, None

    # GUARD 2 — General Management is a company-wide / executive scope.
    if department.name == StandardDepartment.DepartmentChoices.GENERAL_MANAGEMENT:
        return ScopeLevel.BUSINESS, None

    return ScopeLevel.DEPARTMENT, department


def resolve_constraint_departments(raw):
    """
    Resolve the list of departments a constraint concerns from the LLM payload
    (sub-step 1c). Constraint moved from a single FK (scope_level +
    target_department, via the shared resolve_scope_and_department) to the
    multi-department target_departments M2M — a constraint can be owned by IT
    AND Security & Risk at once.

    Direct clone of resolve_tech_usage_departments (TechStack.usage_departments,
    above): the constraint stage now emits `target_departments`, an array of
    department names drawn from the StandardDepartment vocabulary injected in
    the context layer. Same controlled vocabulary and the same two resolution
    layers, so a name resolves exactly as it does for tech usage:

      1. case-insensitive EXACT match on the department name;
      2. else a case-insensitive UNAMBIGUOUS single-word match (a word shared
         by several departments never resolves — no over-correction).

    StandardDepartment is global reference data (no client_id of its own), so
    the lookup is tenant-safe exactly as for the shared scope resolver — the
    tenant boundary lives on the signal, not on the department rows.

    Guards (mirror of resolve_tech_usage_departments, and of the conservative
    single-FK guards resolve_scope_and_department applied before):
      * a name that resolves to nothing is DROPPED (never invented);
      * "General Management" is dropped — a company-wide / executive owner is
        not a specific concerned department (the BUSINESS reading);
      * duplicates collapse (order-preserving).

    A missing / non-list / empty `target_departments`, or one that resolves to
    nothing, yields [] — a valid "no specific department" (company-wide /
    cross-departmental) state. This does NOT touch resolve_scope_and_department,
    which pain/objective/impact keep using unchanged.

    Returns:
        list[StandardDepartment] — possibly empty, deduplicated, in the order
        the model emitted the names.
    """
    from app_modules.core_modules.models import StandardDepartment

    names = raw.get('target_departments')
    if not isinstance(names, list):
        return []

    by_value, by_word = _build_department_resolution_index()

    resolved = []
    seen_ids = set()
    for name in names:
        if not name or not isinstance(name, str):
            continue
        key = name.strip().lower()
        if not key:
            continue
        # Layer 1: exact (case-insensitive). Layer 2: unambiguous word.
        dept = by_value.get(key) or by_word.get(key)
        if dept is None:
            continue
        if dept.name == StandardDepartment.DepartmentChoices.GENERAL_MANAGEMENT:
            continue
        if dept.id in seen_ids:
            continue
        seen_ids.add(dept.id)
        resolved.append(dept)

    return resolved


def resolve_scope_and_departments(raw):
    """
    Resolve (scope_level, list[StandardDepartment]) for a Pain / Impact signal
    (sub-step 2c) — the multi-department analog of resolve_scope_and_department.

    Unlike Constraint (1c), Pain/Impact KEEP scope_level (descriptive): only the
    department moves from a single FK to the target_departments LIST. The prompt
    now emits `target_departments` (a list of names, like techstack/constraint)
    plus scope_level, and this resolver mirrors the single-FK guards of
    resolve_scope_and_department, extended to a list:

      * scope_level other than the literal "DEPARTMENT" (PERSONAL, missing,
        junk, BUSINESS) -> BUSINESS + [] ;
      * a DEPARTMENT scope whose names do not resolve (or resolve only to
        General Management, which resolve_constraint_departments drops) ->
        BUSINESS + [] (the "no resolvable department is business-normal" rule) ;
      * otherwise DEPARTMENT + the deduplicated list of resolved departments.

    The department list itself is resolved by resolve_constraint_departments —
    the generic `target_departments` list resolver (name is historical; it is
    not constraint-specific), reading the SAME controlled vocabulary and the
    same two-layer (exact + unambiguous-word) matching.

    This function is NEW: pain/impact call it instead of the shared
    resolve_scope_and_department, which is left UNTOUCHED for Objective (still
    single-FK, mono-department).

    Returns:
        tuple (scope_level: str, target_departments: list[StandardDepartment])
    """
    scope_raw = raw.get('scope_level')

    # GUARD 1 — anything that is not an explicit DEPARTMENT is BUSINESS + [].
    if scope_raw != ScopeLevel.DEPARTMENT:
        return ScopeLevel.BUSINESS, []

    departments = resolve_constraint_departments(raw)

    # No resolvable department (unresolved names / General-Management only) ->
    # fold to BUSINESS with no department, mirroring the single-FK guard.
    if not departments:
        return ScopeLevel.BUSINESS, []

    return ScopeLevel.DEPARTMENT, departments


class TranscriptSignalExtractor:
    """
    Stage-by-stage persistence for the TranscriptSignalsPipeline.

    Usage:
        extractor = TranscriptSignalExtractor()
        persisted, dropped = extractor.persist_stage(
            stage='pain',
            raw_signals=[...],
            activity=activity,
            user=user,
            client_id=client_id,
            confidence_min=0.5,
            drop_inferred=True,
        )
    """

    # =========================================================================
    # MAIN ENTRY
    # =========================================================================

    def persist_stage(
        self,
        *,
        stage,
        raw_signals,
        activity,
        user,
        client_id,
        confidence_min,
        drop_inferred,
        source_run=None,
    ):
        """
        Apply safety filter + persist surviving signals for one stage.

        Args:
            stage:           'pain' | 'objective' | 'impact' | 'techstack' | 'blocker' | 'constraint'.
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
                persisted:     list of concrete signal instances
                                (PainSignal / ObjectiveSignal /
                                ImpactSignal / TechStackSignal /
                                BlockerSignal).
                dropped_count: int -- total signals NOT persisted, all reasons
                                combined. The pipeline logs this in
                                AIPipelineRun.sub_calls.
        """
        if not isinstance(raw_signals, list):
            logger.warning(
                'persist_stage_invalid_input',
                extra={
                    'stage': stage,
                    'type': type(raw_signals).__name__,
                    'event': 'ai_pipeline_persist',
                },
            )
            return [], 0

        persisted = []
        dropped_count = 0

        # --- Phase 1: Build all data dicts (filter + transform) ---
        candidates = []
        for raw in raw_signals:
            if not isinstance(raw, dict):
                dropped_count += 1
                continue

            if not self._passes_safety_filter(raw, confidence_min, drop_inferred):
                dropped_count += 1
                continue

            data = self._build_signal_data(
                stage=stage,
                raw=raw,
                activity=activity,
                client_id=client_id,
            )
            if data is None:
                dropped_count += 1
                continue

            candidates.append(data)

        # --- Phase 1.5: Deduplicate TechStack candidates ---
        if stage == 'techstack' and len(candidates) > 1:
            before = len(candidates)
            candidates = self._deduplicate_techstack(candidates)
            dropped_count += before - len(candidates)

        # --- Phase 2: Persist surviving candidates ---
        for data in candidates:
            if source_run is not None:
                data['source_run'] = source_run
            try:
                signal = SignalManager.create(
                    data=data,
                    user=user,
                    client_id=client_id,
                )
                persisted.append(signal)
            except StandardizedValidationError as exc:
                logger.warning(
                    'signal_create_validation_failed',
                    extra={
                        'stage': stage,
                        'error': str(exc),
                        'event': 'ai_pipeline_persist',
                    },
                )
                dropped_count += 1
            except Exception as exc:
                logger.error(
                    'signal_create_unexpected_error',
                    extra={
                        'stage': stage,
                        'error': str(exc),
                        'event': 'ai_pipeline_persist',
                    },
                    exc_info=True,
                )
                dropped_count += 1

        return persisted, dropped_count

    # =========================================================================
    # SAFETY FILTER (delegated to the shared module)
    # =========================================================================
    #
    # The policy (drop on missing/low confidence + drop_inferred) lives
    # in services/safety_filter.py so it is shared with NextStepExtractor
    # and any future extractor. We keep a thin static-method wrapper on
    # the class for backwards-compat with any caller that already spells
    # `TranscriptSignalExtractor._passes_safety_filter`, but the
    # implementation is a one-line delegation.

    @staticmethod
    def _passes_safety_filter(raw, confidence_min, drop_inferred):
        """Delegate to services.safety_filter.passes_safety_filter."""
        return passes_safety_filter(raw, confidence_min, drop_inferred)

    # =========================================================================
    # TECHSTACK DEDUPLICATION
    # =========================================================================

    @staticmethod
    def _deduplicate_techstack(candidates):
        """
        Merge multiple TechStack candidates that refer to the same tool.

        Grouping key (S10): the NORMALISED tech name. The key is computed
        with TechStackSignal._normalize_tech_name -- the very function
        the model's save() uses -- so a batch groups on exactly the same
        rule the persisted `tech_name_normalized` column will carry.
        Duplicating the lower/strip/collapse logic here would let the two
        drift apart silently.

        This replaces the previous key (catalog entry id, falling back to
        metadata.pending_tech_name): the extractor no longer resolves a
        catalogue entry, and the raw name now lives on `tech_name`.

        For each group the FIRST candidate wins -- including its
        qualification booleans. Additional source_quote values are stored
        in metadata.additional_quotes for traceability.
        """
        groups = {}
        order = []

        for data in candidates:
            key = TechStackSignal._normalize_tech_name(data.get('tech_name'))

            if key not in groups:
                groups[key] = data
                order.append(key)
            else:
                winner = groups[key]
                extra_quote = data.get('source_quote')
                if extra_quote:
                    if not winner.get('metadata'):
                        winner['metadata'] = {}
                    additional = winner['metadata'].setdefault('additional_quotes', [])
                    additional.append(extra_quote)

        return [groups[k] for k in order]

    # =========================================================================
    # DATA-DICT BUILDERS
    # =========================================================================

    def _build_signal_data(self, *, stage, raw, activity, client_id):
        """
        Dispatch to the per-stage data-dict builder.

        Returns:
            dict ready for SignalManager.create(), or None on malformed input.
        """
        if stage == 'pain':
            return self._build_pain_data(raw, activity)
        if stage == 'objective':
            return self._build_objective_data(raw, activity)
        if stage == 'impact':
            return self._build_impact_data(raw, activity)
        if stage == 'techstack':
            return self._build_techstack_data(raw, activity, client_id)
        if stage == 'blocker':
            return self._build_blocker_data(raw, activity)
        if stage == 'constraint':
            return self._build_constraint_data(raw, activity)
        if stage == 'competitor':
            return self._build_competitor_data(raw, activity)

        logger.warning(
            'persist_stage_unknown_stage',
            extra={'stage': stage, 'event': 'ai_pipeline_persist'},
        )
        return None

    # ---------------------- Pain ----------------------

    def _build_pain_data(self, raw, activity):
        """
        Build SignalManager.create() data for a Pain signal.

        Schema requirements (from pain_v1.py):
            what, dimension, summary, source_quote, confidence, is_inferred
        """
        required = ('what', 'dimension', 'summary', 'source_quote')
        if not all(k in raw and raw[k] is not None for k in required):
            return None

        # Scope is LLM-extracted; scope_level is KEPT (descriptive) and the
        # department is now the multi-department target_departments LIST
        # (sub-step 2c) resolved by resolve_scope_and_departments (the shared
        # resolve_scope_and_department is left for Objective). The legacy FK
        # target_department is NO LONGER written (M2M carrier since 2b; drop 2d).
        # SignalManager.create pops the M2M and applies it via .set() post-save.
        scope_level, target_departments = resolve_scope_and_departments(raw)

        return {
            'signal_type':      'pain',
            'account':          activity.account,
            'source_activity':  activity,
            'source':           SignalSource.LLM_EXTRACTED,
            'status':           SignalStatus.PENDING,
            'what':             raw['what'],
            'dimension':        raw['dimension'],
            'summary':          raw['summary'],
            'source_quote':     raw['source_quote'],
            'confidence':       self._safe_float(raw.get('confidence')),
            'is_inferred':      bool(raw.get('is_inferred')),

            'scope_level':         scope_level,
            'target_departments':  target_departments,
        }

    # ---------------------- Objective ----------------------

    def _build_objective_data(self, raw, activity):
        """
        Build SignalManager.create() data for an Objective signal.

        Schema requirements (from objective_v1.py):
            what, dimension, summary, source_quote, confidence, is_inferred

        BUSINESS-scope hardcoded fields (v1):
            scope_level         = ScopeLevel.BUSINESS
            target_contact      = (unset, defaults to None)
            target_department   = (unset, defaults to None)
        """
        required = ('what', 'dimension', 'summary', 'source_quote')
        if not all(k in raw and raw[k] is not None for k in required):
            return None

        # Scope + department are now LLM-extracted (BUSINESS | DEPARTMENT)
        # with the shared safety-net guards. Replaces the previous forced
        # scope_level=BUSINESS. target_contact stays unset (PERSONAL is not
        # offered), so the built dict always satisfies ObjectiveSignal.clean():
        #   DEPARTMENT -> target_department set, target_contact absent;
        #   BUSINESS   -> neither set.
        scope_level, target_department = resolve_scope_and_department(raw)

        return {
            'signal_type':      'objective',
            'account':          activity.account,
            'source_activity':  activity,
            'source':           SignalSource.LLM_EXTRACTED,
            'status':           SignalStatus.PENDING,
            'what':             raw['what'],
            'dimension':        raw['dimension'],
            'summary':          raw['summary'],
            'source_quote':     raw['source_quote'],
            'confidence':       self._safe_float(raw.get('confidence')),
            'is_inferred':      bool(raw.get('is_inferred')),

            'scope_level':        scope_level,
            'target_department':  target_department,
        }
    
    # ---------------------- Impact ----------------------

    def _build_impact_data(self, raw, activity):
        """
        Build SignalManager.create() data for an Impact signal.

        Schema requirements (from impact_v1.py):
            what, dimension, impact_type, summary, source_quote,
            confidence, is_inferred.

        impact_type is REQUIRED at the model level (ImpactSignal.clean())
        and emitted on every signal by the LLM. Missing or null
        impact_type -> drop the signal.

        BUSINESS-scope hardcoded fields (v1):
            scope_level    = ScopeLevel.BUSINESS  (rep promotes during
                                                    validation)

        Optional Impact fields left unset (rep adds during validation):
            metric_text    -- free-text quantified value; LLM
                              normalisation of fuzzy units is brittle
                              at MVP scope.
            human_impact   -- fuzzy emotion qualifier (FRUSTRATION /
                              OVERLOAD / STRESS / DEMOTIVATION /
                              CONFLICT); mapping a quote to a precise
                              category yields too much noise at MVP.

        These defaults satisfy ImpactSignal.clean()'s required-fields
        rule (source_activity NOT NULL; impact_type / what / dimension /
        summary / scope_level all populated).
        """
        required = ('what', 'dimension', 'impact_type', 'summary', 'source_quote')
        if not all(k in raw and raw[k] is not None for k in required):
            return None

        # Scope is LLM-extracted; scope_level is KEPT (descriptive) and the
        # department is now the multi-department target_departments LIST
        # (sub-step 2c) resolved by resolve_scope_and_departments. ImpactSignal.
        # clean() has no scope-conditional rule, so scope_level is purely
        # descriptive. The legacy FK target_department is NO LONGER written
        # (M2M carrier since 2b; drop 2d). Objective keeps the shared resolver.
        scope_level, target_departments = resolve_scope_and_departments(raw)

        return {
            'signal_type':      'impact',
            'account':          activity.account,
            'source_activity':  activity,
            'source':           SignalSource.LLM_EXTRACTED,
            'status':           SignalStatus.PENDING,
            'what':             raw['what'],
            'dimension':        raw['dimension'],
            'impact_type':      raw['impact_type'],
            'summary':          raw['summary'],
            'source_quote':     raw['source_quote'],
            'confidence':       self._safe_float(raw.get('confidence')),
            'is_inferred':      bool(raw.get('is_inferred')),

            'scope_level':         scope_level,
            'target_departments':  target_departments,

            # metric_text and human_impact NOT extracted in v1 -- rep
            # fills during validation. The fields are nullable on the
            # model, so omitting them from the data dict is safe.
        }

    # ---------------------- TechStack ----------------------

    def _build_techstack_data(self, raw, activity, client_id):
        """
        Build SignalManager.create() data for a TechStack signal.

        Schema requirements (from techstack_v1.py):
            tech_name (required, free text),
            is_competitor / is_to_replace (booleans),
            usage_scope (optional),
            source_quote, confidence, is_inferred.
            (is_integration is no longer extracted -- now a TECHNICAL
            constraint; see the constraint stage.)

        Tech identity (S10):
            The LLM emits the tool name as free text and the extractor
            writes it verbatim to `tech_name`. TechStackSignal.save() derives
            `tech_name_normalized` from it -- do NOT normalise here, or
            the raw display text would be lost.

            `metadata['pending_tech_name']` is no longer written -- the
            column is the identity carrier now, and a second copy of the
            same string could only drift from it.

        Qualification booleans:
            Two independent flags (is_competitor / is_to_replace), coerced
            with bool() so a JSON "true" / 1 / null from the model can never
            land a non-boolean in the DB. Both absent -> both False, meaning
            "a tool the account simply uses". (is_integration was retired
            from this path -- now a TECHNICAL constraint.)

        usage_scope filtering (SCALE axis -- how widely, kept as-is):
            * "TEAM" / "COMPANY" / "UNKNOWN"  -> propagate to model.
            * Anything else (incl. "DEPARTMENT", no longer asked for) or
              missing -> demote to None. Model field is nullable.

        usage_departments (WHO uses the tool -- multi-department M2M):
            The LLM emits `usage_departments`, an array of department names
            explicitly designated as USERS of the tool. resolve_tech_usage_
            departments maps them to StandardDepartment rows (exact-name,
            deduped, dropping unresolved / General Management). The list is
            passed in the data dict; SignalManager.create applies it via
            .set() after the row is saved (M2M can't be set pre-save).
            An empty list ("nobody designated") is valid and assigned as-is.

            The legacy single-FK `usage_department` is intentionally NOT set
            here anymore -- the WHO is carried by the M2M. The FK is being
            retired; while it still exists it stays null on extracted rows.

        Drops:
            * missing / blank source_quote -> drop (schema).
            * missing / blank tech_name    -> drop. Without a name the
              observation has no identity at all: it could not be
              displayed, grouped or de-duplicated.
        """
        if not raw.get('source_quote'):
            return None

        tech_name = raw.get('tech_name')
        if tech_name is None or str(tech_name).strip() == '':
            logger.warning(
                'techstack_missing_tech_name',
                extra={'event': 'ai_pipeline_persist'},
            )
            return None

        data = {
            'signal_type':     'tech_stack',
            'account':         activity.account,
            'source_activity': activity,
            'source':          SignalSource.LLM_EXTRACTED,
            'status':          SignalStatus.PENDING,
            'source_quote':    raw['source_quote'],
            'confidence':      self._safe_float(raw.get('confidence')),
            'is_inferred':     bool(raw.get('is_inferred')),

            # Raw, verbatim. TechStackSignal.save() computes the
            # normalised grouping key from it.
            'tech_name':       str(tech_name),

            # is_integration and is_competitor are NO LONGER extracted:
            #  * a required integration is captured as a ConstraintSignal of
            #    nature=TECHNICAL (constraint stage);
            #  * a competitor is captured as a CompetitorSignal (competitor
            #    stage) — sub-step 5.
            # Both columns stay (neutralised, default False) pending their
            # schema drop (sub-step 8). is_to_replace is untouched.
            'is_to_replace':   bool(raw.get('is_to_replace')),
        }

        # --- usage_scope filtering (SCALE axis, kept as-is) ---
        usage_scope_raw = raw.get('usage_scope')
        if usage_scope_raw in _TECHSTACK_USAGE_SCOPE_ALLOWED:
            data['usage_scope'] = usage_scope_raw
        # else: leave unset (None) -- model field is nullable.

        # --- usage_departments (WHO -- multi-department M2M) ---
        # Always assign the resolved list (possibly empty). SignalManager
        # .create pops M2M values and applies them with .set() post-save.
        # The legacy single-FK usage_department is deliberately left unset.
        data['usage_departments'] = resolve_tech_usage_departments(raw)

        return data

    # ---------------------- Blocker ----------------------

    def _build_blocker_data(self, raw, activity):
        """
        Build SignalManager.create() data for a Blocker signal.

        Schema requirements (from blocker_v1.py):
            summary, source_quote, confidence, is_inferred

        v1 deliberately omits `contact` attribution
        ---------------------------------------------
        BlockerSignal.contact (FK Contact, nullable) is NOT extracted in
        v1 -- the LLM may not reliably map "the CFO" / "Jane" to a
        Contact UUID from free text. Rep attributes during validation
        in the Activity workspace. Mirror of Impact v1 which defers
        metric_text and human_impact for the same robustness reason.
        Tracked as TD-6 in TECH_DEBT.md.

        Other deferred BlockerSignal fields
        -----------------------------------
        BlockerSignal does NOT participate in cluster aggregation:
            signal_category    -- shadow-overridden to None on the
                                  model; never set here.
            canonical_key      -- forced to None by BlockerSignal.save()
                                  regardless of any value passed in.

        decision_cycle / campaign are auto-propagated from
        source_activity by SignalManager._propagate_activity_context --
        not by this builder.
        """
        required = ('summary', 'source_quote')
        if not all(k in raw and raw[k] is not None for k in required):
            return None

        # Non-empty source_quote: an empty verbatim defeats the audit
        # purpose of the column. Empty summary likewise carries no
        # signal value.
        summary = str(raw['summary']).strip()
        source_quote = str(raw['source_quote']).strip()
        if not summary or not source_quote:
            return None

        return {
            'signal_type':     'blocker',
            'account':         activity.account,
            'source_activity': activity,
            'source':          SignalSource.LLM_EXTRACTED,
            'status':          SignalStatus.PENDING,
            'summary':         summary,
            'source_quote':    source_quote,
            'confidence':      self._safe_float(raw.get('confidence')),
            'is_inferred':     bool(raw.get('is_inferred')),

            # v1: contact attribution deferred to validation UI -- TD-6.
            # Field stays at model default (None).
        }

    # ---------------------- Constraint ----------------------

    def _build_constraint_data(self, raw, activity):
        """
        Build SignalManager.create() data for a Constraint signal.

        Schema requirements (from constraint_v1.py):
            summary, nature, rigidity, source_quote, confidence, is_inferred
            (+ target_departments: the list of concerned departments).

        Detached from what x dimension (sub-step 1): NEVER pass what/dimension.
        ConstraintSignal is classified on `nature` and scoped on the
        multi-department target_departments M2M only.

        `nature` is validated against ConstraintNature -- an out-of-list value
        is DROPPED (return None), never coerced, so a hallucinated kind never
        lands a row. Mirror of the strict stance the model applies to `what`.

        `rigidity` is REQUIRED on the model; an invalid / missing emission
        folds to FIRM (the cautious default -- treat an unqualified
        requirement as non-negotiable).

        `target_departments` is resolved by resolve_constraint_departments
        (sub-step 1c) — the multi-department clone of the TechStack usage
        resolver: a list of names -> a deduplicated list of StandardDepartment,
        unresolved names dropped, [] when none. Constraint no longer uses the
        shared resolve_scope_and_department (which pain/objective/impact keep),
        and the legacy single-FK target_department is NO LONGER written (the
        M2M is the scope carrier since sub-step 1b; the FK drop is sub-step 1d).
        """
        required = ('summary', 'nature', 'source_quote')
        if not all(k in raw and raw[k] is not None for k in required):
            return None

        summary = str(raw['summary']).strip()
        source_quote = str(raw['source_quote']).strip()
        if not summary or not source_quote:
            return None

        # nature: strict — drop (do not coerce) an out-of-vocabulary value.
        nature = raw.get('nature')
        if nature not in ConstraintNature.values:
            logger.warning(
                'constraint_nature_out_of_taxonomy',
                extra={
                    'event': 'ai_pipeline_persist',
                    'raw_nature': nature,
                    'source_activity_id': str(getattr(activity, 'id', '')),
                },
            )
            return None

        # rigidity: required on the model — fold an invalid/missing value to
        # FIRM (cautious default).
        rigidity = raw.get('rigidity')
        if rigidity not in Rigidity.values:
            rigidity = Rigidity.FIRM

        # Scope: multi-department list (sub-step 1c). SignalManager.create pops
        # the M2M and applies it with .set() after the row is saved. The legacy
        # single-FK target_department is deliberately left unset (M2M is the
        # carrier since 1b; the shared resolve_scope_and_department is untouched
        # for pain/objective/impact).
        target_departments = resolve_constraint_departments(raw)

        return {
            'signal_type':      'constraint',
            'account':          activity.account,
            'source_activity':  activity,
            'source':           SignalSource.LLM_EXTRACTED,
            'status':           SignalStatus.PENDING,
            'summary':          summary,
            'nature':           nature,
            'rigidity':         rigidity,
            'target_departments': target_departments,
            'source_quote':     source_quote,
            'confidence':       self._safe_float(raw.get('confidence')),
            'is_inferred':      bool(raw.get('is_inferred')),

            # NEVER what/dimension (detached, sub-step 1). canonical_key is
            # forced to None by ConstraintSignal.save().
        }

    # ---------------------- Competitor ----------------------

    def _build_competitor_data(self, raw, activity):
        """
        Build SignalManager.create() data for a Competitor signal.

        Schema requirements (from competitor_v1.py):
            summary, competitor_name, source_quote, confidence, is_inferred

        Detached (sub-step 1): NEVER pass nature / rigidity / scope_level /
        target_department / what / dimension. CompetitorSignal carries only
        competitor_name (+ its derived normalised key) and the narrative
        summary; canonical_key is forced to None and competitor_name_normalized
        is derived by CompetitorSignal.save().

        A missing required key, or a blank summary / source_quote /
        competitor_name after strip, DROPS the signal (return None) — mirror of
        the strict stance _build_constraint_data applies.
        """
        required = ('summary', 'source_quote', 'competitor_name')
        if not all(k in raw and raw[k] is not None for k in required):
            return None

        summary = str(raw['summary']).strip()
        source_quote = str(raw['source_quote']).strip()
        competitor_name = str(raw['competitor_name']).strip()
        if not summary or not source_quote or not competitor_name:
            return None

        return {
            'signal_type':      'competitor',
            'account':          activity.account,
            'source_activity':  activity,
            'source':           SignalSource.LLM_EXTRACTED,
            'status':           SignalStatus.PENDING,
            'summary':          summary,
            'competitor_name':  competitor_name,
            'source_quote':     source_quote,
            'confidence':       self._safe_float(raw.get('confidence')),
            'is_inferred':      bool(raw.get('is_inferred')),

            # NEVER nature/rigidity/scope_level/target_department/what/dimension
            # (detached). canonical_key is forced to None and
            # competitor_name_normalized is derived by CompetitorSignal.save().
        }

    # =========================================================================
    # MISC HELPERS (delegated to the shared module)
    # =========================================================================

    @staticmethod
    def _safe_float(value, default=0.0):
        """Delegate to services.safety_filter.safe_float."""
        return safe_float(value, default)