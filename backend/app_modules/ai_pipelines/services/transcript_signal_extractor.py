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
                          is_to_replace); usage in three cases
                          (_techstack_usage_scope: DEPARTMENT iff departments
                          resolved, else COMPANY or UNKNOWN); usage_departments
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

import datetime
import logging
import re

from django.db import transaction
from django.utils import timezone

from app_modules.signals.constants import (
    ConstraintNature,
    InfluenceLevel,
    PeopleRole,
    Rigidity,
    ScopeLevel,
    SignalSource,
    SignalStatus,
    UsageScope,
)
from app_modules.signals.models import CompetitorSignal, PeopleSignal, TechStackSignal
from app_modules.signals.services.signal_cluster_service import SignalClusterService
from app_modules.signals.services.signal_manager import SignalManager
from core.exceptions import StandardizedValidationError

from .identified_people import identified_people_in_deal
from .participant_refs import resolve_participant_ref
from .safety_filter import passes_safety_filter, safe_float


logger = logging.getLogger(__name__)


def _techstack_usage_scope(raw_scope, departments):
    """
    TechStack usage in THREE cases (Sprint TechStack, T0) — same normalisation
    as data migration 0045:

      * at least one RESOLVED usage department -> DEPARTMENT (the departments
        decide, whatever scope the model emitted);
      * else COMPANY when the model said COMPANY;
      * else UNKNOWN — "not said" (null / missing), the retired TEAM, a
        DEPARTMENT whose departments did not resolve, or any garbage value.

    Guarantees DEPARTMENT <=> at least one usage department, and never null.
    """
    if departments:
        return UsageScope.DEPARTMENT
    if raw_scope == UsageScope.COMPANY:
        return UsageScope.COMPANY
    return UsageScope.UNKNOWN


# TechStack usage_start_year bounds (Sprint TechStack T4) — a year outside is
# a model slip, dropped to null (same bounds as the Activity edit drawer).
_TECHSTACK_MIN_USAGE_YEAR = 1980
_TECHSTACK_MAX_USAGE_YEARS_AHEAD = 1

_ISO_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

# D2 — note appended when a discontinuation is stated without a valid date
# (the rep sets the date by hand from it). `quote` = the signal's source_quote.
_TECHSTACK_UNDATED_DISCONTINUATION_NOTE = 'Discontinuation mentioned without a date: "{quote}"'


def _techstack_usage_year(value):
    """An integer year within the module bounds (int or digit string), else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if not isinstance(value, int):
        return None
    max_year = timezone.now().year + _TECHSTACK_MAX_USAGE_YEARS_AHEAD
    if not _TECHSTACK_MIN_USAGE_YEAR <= value <= max_year:
        return None
    return value


def _iso_date(value):
    """A real calendar date written YYYY-MM-DD, else None (never guessed)."""
    if not isinstance(value, str) or not _ISO_DATE_RE.match(value.strip()):
        return None
    try:
        return datetime.date.fromisoformat(value.strip())
    except ValueError:
        return None


def _clean_text(value):
    """Stripped text; None / missing -> ''."""
    return str(value).strip() if value is not None else ''


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


def resolve_person_department(name):
    """
    Resolve the SINGLE department of a person cited in the transcript
    (People stage) from the LLM-emitted department name.

    PeopleSignal.target_department is a single FK (a person belongs to one
    department) with no scope_level, so neither resolve_scope_and_department
    (needs scope_level=DEPARTMENT) nor resolve_constraint_departments (a list)
    fits. Same controlled vocabulary and the same two resolution layers as
    resolve_tech_usage_departments / resolve_constraint_departments, via the
    shared _build_department_resolution_index:

      1. case-insensitive EXACT match on the department name;
      2. else a case-insensitive UNAMBIGUOUS single-word match (a word shared
         by several departments never resolves — no over-correction).

    Unlike the scope resolvers, "General Management" is KEPT: a CEO / managing
    director legitimately belongs to it — the company-wide reading those
    resolvers guard against does not apply to a person.

    Returns:
        StandardDepartment | None — None for a missing / non-string / blank /
        unresolved name (never invented).
    """
    if not name or not isinstance(name, str):
        return None
    key = name.strip().lower()
    if not key:
        return None

    by_value, by_word = _build_department_resolution_index()
    return by_value.get(key) or by_word.get(key)


# =============================================================================
# IN-EXTRACTION DEDUPLICATION (shared by TechStack and People)
# =============================================================================

def _deduplicate_candidates(candidates, key_fn, fill_groups=()):
    """
    Merge the candidates of ONE extraction that share a grouping key.

    For each group the FIRST candidate wins (all its fields kept); the
    source_quote of every later member is appended to the winner's
    metadata.additional_quotes for traceability. A candidate whose key is
    None is NEVER merged (kept as is). Order of first occurrence preserved.

    fill_groups (D3, TechStack): tuples of fields filled TOGETHER — when the
    winner's first field of a group is EMPTY (None / '' / False) and a later
    member's is not, the whole group is copied from that member (the first
    non-empty one wins). Fields already set on the winner are never
    overwritten.

    Args:
        candidates:  list[dict] -- data dicts built for SignalManager.create().
        key_fn:      callable(dict) -> hashable | None -- the grouping key.
        fill_groups: tuple[tuple[str, ...]] -- field groups to complete.

    Returns:
        list[dict] -- the surviving candidates.
    """
    groups = {}
    survivors = []

    for data in candidates:
        key = key_fn(data)
        if key is None:
            survivors.append(data)
            continue

        if key not in groups:
            groups[key] = data
            survivors.append(data)
        else:
            winner = groups[key]
            for group in fill_groups:
                if not winner.get(group[0]) and data.get(group[0]):
                    for field in group:
                        winner[field] = data.get(field)
            extra_quote = data.get('source_quote')
            if extra_quote:
                if not winner.get('metadata'):
                    winner['metadata'] = {}
                additional = winner['metadata'].setdefault('additional_quotes', [])
                additional.append(extra_quote)

    return survivors


def _techstack_dedup_key(data):
    """TechStack grouping key: the normalised tech name (S10)."""
    return TechStackSignal._normalize_tech_name(data.get('tech_name'))


def _competitor_dedup_key(data):
    """
    Competitor grouping key (Sprint Competitor C3): the normalised competitor
    name, computed with CompetitorSignal._normalize_competitor_name -- the rule
    save() uses for competitor_name_normalized, which the DC cluster groups on.
    In-batch only: a competitor cited several times in ONE transcript is one
    signal; across activities the DC cluster does the grouping.
    """
    return CompetitorSignal._normalize_competitor_name(data.get('competitor_name'))


def _people_dedup_key(data):
    """
    People grouping key: the SAME per-person identity as the DC People
    cluster (SignalClusterService._people_cluster_key), computed on a
    transient, never-saved PeopleSignal built from the candidate:

      * a resolved contact -> 'contact:<id>';
      * else a name -> 'name:<normalised full_name>|dept:<department id>'
        ("Marc / Finance" and "Marc / IT" are two persons); the name is
        normalised with PeopleSignal._normalize_full_name, the rule save()
        applies;
      * else -> 'signal:<id>' with the transient instance's fresh uuid, i.e.
        a key unique to the candidate: a person with neither contact nor
        name ("our CFO") is never merged.
    """
    candidate = PeopleSignal(
        target_contact=data.get('target_contact'),
        target_department=data.get('target_department'),
        full_name_normalized=PeopleSignal._normalize_full_name(data.get('full_name')),
    )
    return SignalClusterService._people_cluster_key(candidate)


def _loggable_identity_key(key):
    """
    An identity key safe for the logs: the contact / signal id is kept, the
    normalised NAME (which may carry a last name) is redacted.
    """
    if key.startswith('name:'):
        _name, _sep, dept = key.partition('|')
        return f'name:[redacted]|{dept}'
    return key


def _drop_people_already_in_deal(candidates, activity):
    """
    Server-side safety net of the People stage: drop every candidate whose
    identity (the SAME key as the in-extraction dedup, _people_dedup_key ->
    SignalClusterService._people_cluster_key) matches a person ALREADY
    identified in the activity's deal (identified_people_in_deal -- the very
    set the context lists to the LLM). The LLM is told not to re-emit them but
    does not always comply.

    No decision cycle -> no filter. A candidate with neither contact nor name
    gets a unique 'signal:<uuid>' key and is therefore never filtered (the
    "to identify" rule).

    Returns:
        tuple (kept_candidates, dropped_count)
    """
    existing = {
        SignalClusterService._people_cluster_key(signal): signal
        for signal in identified_people_in_deal(activity)
    }
    if not existing:
        return candidates, 0

    kept = []
    for data in candidates:
        key = _people_dedup_key(data)
        match = existing.get(key)
        if match is None:
            kept.append(data)
            continue
        logger.warning(
            'people_already_identified_in_dc',
            extra={
                'identity_key': _loggable_identity_key(key),
                'existing_signal_id': str(match.id),
                'decision_cycle_id': str(activity.decision_cycle_id),
                'activity_id': str(activity.id),
                'event': 'ai_pipeline_persist',
            },
        )
    return kept, len(candidates) - len(kept)


# Stage -> grouping key of the in-extraction deduplication.
_DEDUP_KEY_BY_STAGE = {
    'techstack':  _techstack_dedup_key,
    'people':     _people_dedup_key,
    'competitor': _competitor_dedup_key,
}

# Stage -> field groups a later duplicate may complete when EMPTY on the
# winner (D3, Sprint TechStack T4). The discontinuation pair travels together.
_DEDUP_FILL_GROUPS_BY_STAGE = {
    'techstack': (
        ('usage_start_year',),
        ('renewal_date',),
        ('cost_description',),
        ('notes',),
        ('is_discontinued', 'discontinued_date'),
    ),
}

# PeopleSignal.full_name column width -- an over-long LLM name is truncated
# rather than failing the insert inside the pipeline transaction.
_PEOPLE_FULL_NAME_MAX_LENGTH = PeopleSignal._meta.get_field('full_name').max_length


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
            stage:           'pain' | 'objective' | 'impact' | 'techstack' | 'blocker' |
                             'constraint' | 'competitor' | 'people'.
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

        # --- Phase 1.5: Deduplicate candidates (TechStack, People, Competitor) ---
        dedup_key = _DEDUP_KEY_BY_STAGE.get(stage)
        if dedup_key is not None and len(candidates) > 1:
            before = len(candidates)
            candidates = _deduplicate_candidates(
                candidates, dedup_key, _DEDUP_FILL_GROUPS_BY_STAGE.get(stage, ()),
            )
            dropped_count += before - len(candidates)

        # --- Phase 1.6: People only — never recreate a person already
        # identified in the activity's deal (server-side safety net) ---
        if stage == 'people' and candidates:
            candidates, already_identified = _drop_people_already_in_deal(
                candidates, activity,
            )
            dropped_count += already_identified

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

        Grouping key (S10): the NORMALISED tech name, computed with
        TechStackSignal._normalize_tech_name -- the very function the
        model's save() uses -- so a batch groups on exactly the same rule
        the persisted `tech_name_normalized` column will carry.

        Delegates to the shared _deduplicate_candidates (also used by the
        People stage): the FIRST candidate wins -- including its
        qualification booleans -- and additional source_quote values are
        stored in metadata.additional_quotes for traceability.
        """
        return _deduplicate_candidates(
            candidates, _techstack_dedup_key, _DEDUP_FILL_GROUPS_BY_STAGE['techstack'],
        )

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
        if stage == 'people':
            return self._build_people_data(raw, activity)

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

        Schema requirements (from techstack_v1.py, prompt v3):
            tech_name (required, free text),
            usage_scope + usage_departments (three cases, see below),
            usage_start_year, renewal_date, cost_description,
            is_discontinued, discontinued_date, notes (ONLY when said),
            source_quote, confidence, is_inferred.
            (is_to_replace left the schema in v3 -- forced to False here;
            is_competitor / is_integration were retired earlier.)

        Tech identity (S10):
            The LLM emits the tool name as free text and the extractor
            writes it verbatim to `tech_name`. TechStackSignal.save() derives
            `tech_name_normalized` from it -- do NOT normalise here, or
            the raw display text would be lost.

        usage_scope (three cases, see _techstack_usage_scope):
            * resolved departments -> DEPARTMENT;
            * else COMPANY when emitted as COMPANY;
            * else UNKNOWN ("not said", the retired TEAM, an unresolved
              DEPARTMENT, garbage). Never null.

        usage_departments (WHO uses the tool -- multi-department M2M):
            resolve_tech_usage_departments maps the emitted names to
            StandardDepartment rows; SignalManager.create applies the list
            via .set() after the row is saved.

        Lifecycle + notes (prompt v3):
            * usage_start_year -- an integer within the module bounds
              (_TECHSTACK_MIN_USAGE_YEAR .. current year +
              _TECHSTACK_MAX_USAGE_YEARS_AHEAD), else None;
            * renewal_date / discontinued_date -- a real YYYY-MM-DD date,
              else None;
            * cost_description / notes -- stripped text ('' when absent);
            * D2 -- is_discontinued without a valid discontinued_date ->
              not discontinued, no date, the source_quote appended to the
              notes; a date without the flag is ignored.
            (D3 -- a later mention of the same tool completes the EMPTY
            fields: see _deduplicate_candidates / _DEDUP_FILL_GROUPS_BY_STAGE.)

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

            # is_to_replace left the output schema (prompt v3, Sprint
            # TechStack T4): the column stays in the DB, always False on
            # extraction (out of the UI; its replacement is TD-199).
            'is_to_replace':   False,
        }

        # --- lifecycle + notes (prompt v3): ONLY when said, never guessed ---
        data['usage_start_year'] = _techstack_usage_year(raw.get('usage_start_year'))
        data['renewal_date'] = _iso_date(raw.get('renewal_date'))
        data['cost_description'] = _clean_text(raw.get('cost_description'))
        notes = _clean_text(raw.get('notes'))

        # D2 — discontinued requires a valid date (model rule). Without one the
        # signal is NOT discontinued, and the stated phrase is kept in the
        # notes so the rep can set the date by hand.
        discontinued_date = _iso_date(raw.get('discontinued_date'))
        is_discontinued = bool(raw.get('is_discontinued'))
        if is_discontinued and discontinued_date is None:
            is_discontinued = False
            phrase = _TECHSTACK_UNDATED_DISCONTINUATION_NOTE.format(
                quote=_clean_text(raw['source_quote']),
            )
            notes = f'{notes}\n{phrase}' if notes else phrase
        data['is_discontinued'] = is_discontinued
        data['discontinued_date'] = discontinued_date if is_discontinued else None
        data['notes'] = notes

        # --- usage in three cases ---
        # Always assign the resolved department list (possibly empty).
        # SignalManager.create pops M2M values and applies them with .set()
        # post-save. The resolved departments decide DEPARTMENT; otherwise
        # COMPANY or UNKNOWN (never null) — see _techstack_usage_scope.
        departments = resolve_tech_usage_departments(raw)
        data['usage_departments'] = departments
        data['usage_scope'] = _techstack_usage_scope(
            raw.get('usage_scope'), departments,
        )

        return data

    # ---------------------- Blocker ----------------------

    def _build_blocker_data(self, raw, activity):
        """
        Build SignalManager.create() data for a Blocker signal.

        Schema requirements (from blocker_v1.py):
            summary, source_quote, confidence, is_inferred
            (+ optional raised_by)

        `contact` attribution (blocker_v2 -- Objection S3)
        --------------------------------------------------
        The LLM returns `raised_by`, the REFERENCE ("P1", ...) of a
        participant from the closed list rendered by the context layer.
        It is resolved via services/participant_refs.py against the same
        list (tenant + account filtered) -- never by name, never guessed
        (mirror of the department resolver above). Resolved -> `contact`
        is set. Absent / null / invalid -> `contact` stays unset (model
        default None), a warning is logged on a non-null reference that
        does not resolve, and the signal is NEVER dropped for this reason.

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

        data = {
            'signal_type':     'blocker',
            'account':         activity.account,
            'source_activity': activity,
            'source':          SignalSource.LLM_EXTRACTED,
            'status':          SignalStatus.PENDING,
            'summary':         summary,
            'source_quote':    source_quote,
            'confidence':      self._safe_float(raw.get('confidence')),
            'is_inferred':     bool(raw.get('is_inferred')),
        }

        # Objection S3: resolve the participant reference. The server never
        # forces an attribution; an unresolved reference keeps the signal.
        raised_by = raw.get('raised_by')
        contact = resolve_participant_ref(raised_by, activity)
        if contact is not None:
            data['contact'] = contact
        elif raised_by is not None:
            logger.warning(
                'blocker_raised_by_unresolved',
                extra={
                    'raised_by': str(raised_by),
                    'activity_id': str(activity.id),
                    'event': 'ai_pipeline_persist',
                },
            )

        return data

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

    # ---------------------- People ----------------------

    def _build_people_data(self, raw, activity):
        """
        Build SignalManager.create() data for a People signal.

        Schema requirements (from people_v1.py):
            role, source_quote, confidence, is_inferred
            (+ optional participant_ref, full_name, influence, department,
            notes).

        Drop / fold rules (mirror of the existing builders):
          * blank / missing source_quote -> DROPPED (as blocker / constraint);
          * role absent or out of PeopleRole -> DROPPED + warning, never
            coerced (as constraint `nature`);
          * influence out of the SIGNAL InfluenceLevel -> None (nullable
            column, so no default is forced -- unlike constraint `rigidity`);
          * participant_ref resolved via services/participant_refs.py
            (tenant + account filtered, never by name). Resolved -> contact
            set, full_name DERIVED from the contact (first + last name) and
            department = the contact's standard_department when set, else
            the extracted one. Non-null but unresolved -> signal KEPT without
            contact + warning (as blocker `raised_by`); full_name and
            department then come from the extraction;
          * no contact, no name and no department after resolution ->
            DROPPED + warning. Checked HERE: persist_stage feeds
            SignalManager.create directly -- neither the People serializer
            nor PeopleSignal.clean() runs on this path (TD-249).

        decision_cycle / campaign are auto-propagated from source_activity
        by SignalManager._propagate_activity_context -- not by this builder.
        """
        raw_quote = raw.get('source_quote')
        source_quote = str(raw_quote).strip() if raw_quote is not None else ''
        if not source_quote:
            return None

        role = raw.get('role')
        if role not in PeopleRole.values:
            logger.warning(
                'people_role_out_of_taxonomy',
                extra={
                    'event': 'ai_pipeline_persist',
                    'raw_role': role,
                    'source_activity_id': str(getattr(activity, 'id', '')),
                },
            )
            return None

        influence = raw.get('influence')
        if influence not in InfluenceLevel.values:
            influence = None

        participant_ref = raw.get('participant_ref')
        contact = resolve_participant_ref(participant_ref, activity)
        if contact is not None:
            full_name = f'{contact.first_name or ""} {contact.last_name or ""}'.strip()
            department = (
                contact.standard_department
                or resolve_person_department(raw.get('department'))
            )
        else:
            if participant_ref is not None:
                logger.warning(
                    'people_participant_ref_unresolved',
                    extra={
                        'participant_ref': str(participant_ref),
                        'activity_id': str(activity.id),
                        'event': 'ai_pipeline_persist',
                    },
                )
            raw_name = raw.get('full_name')
            full_name = raw_name.strip() if isinstance(raw_name, str) else ''
            department = resolve_person_department(raw.get('department'))

        full_name = full_name[:_PEOPLE_FULL_NAME_MAX_LENGTH]

        if contact is None and department is None and not full_name:
            logger.warning(
                'people_no_identity',
                extra={
                    'activity_id': str(activity.id),
                    'event': 'ai_pipeline_persist',
                },
            )
            return None

        raw_notes = raw.get('notes')
        notes = raw_notes.strip() if isinstance(raw_notes, str) else ''

        return {
            'signal_type':       'people',
            'account':           activity.account,
            'source_activity':   activity,
            'source':            SignalSource.LLM_EXTRACTED,
            'status':            SignalStatus.PENDING,
            'role':              role,
            'influence':         influence,
            'full_name':         full_name,
            'target_contact':    contact,
            'target_department': department,
            'notes':             notes,
            'source_quote':      source_quote,
            'confidence':        self._safe_float(raw.get('confidence')),
            'is_inferred':       bool(raw.get('is_inferred')),

            # canonical_key is forced to None and full_name_normalized is
            # derived by PeopleSignal.save().
        }

    # =========================================================================
    # MISC HELPERS (delegated to the shared module)
    # =========================================================================

    @staticmethod
    def _safe_float(value, default=0.0):
        """Delegate to services.safety_filter.safe_float."""
        return safe_float(value, default)