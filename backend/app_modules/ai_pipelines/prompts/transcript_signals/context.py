# app_modules/ai_pipelines/prompts/transcript_signals/context.py
"""
Context layer for the transcript_signals prompt family.

Builds the dynamic, per-run context block that grounds the LLM in:
  * The commercial identity of the session (Seller, Prospect, Activity, Contacts)
  * The canonical taxonomy applicable to the target sub-call

What this layer carries
-----------------------
  - Tenant display name (from ClientAccount.name).
  - Prospect commercial identity (company_name, industry, classification).
  - Activity metadata (type, date).
  - Contacts on the activity: first_name + job_title + department only.
  - Canonical enum values per target stage.

No longer carried (S10)
-----------------------
  - TechCatalog entries. The techstack sub-call used to receive the
    tenant's curated catalogue (uuid + label + flags) so the LLM could
    match a mention to an entry. Tech identity is free text now and the
    catalogue has been removed entirely.

What this layer deliberately omits (RGPD / data minimization)
--------------------------------------------------------------
  - Contact emails, phone numbers, postal addresses
        --> never required to extract a commercial signal.
  - User (rep) identity (name, email)
        --> "the Seller AE" is enough; the rep's individual identity
            adds no signal-extraction value.
  - Contact last names
        --> first_name + job_title disambiguates contacts within one
            activity. The transcript itself carries last names verbatim;
            this layer does not re-emit them in the context.

The transcript itself is sent verbatim by the pipeline orchestrator.
That exposure is covered legally (DPA with the LLM provider) -- not
in this module. This module's contract is: inject the MINIMUM context
that improves extraction quality, nothing more.

Versioning
----------
CONTEXT_VERSION is captured in AIPipelineRun.prompt_versions alongside
SYSTEM_PROMPT_VERSION and the per-stage request layer version, for
audit traceability of every prompt revision in production.

Performance
-----------
This builder runs per sub-call (4 sub-calls per pipeline run). For
production use the orchestrator should pass an Activity
prefetched with:

    Activity.objects
        .select_related('account')
        .prefetch_related('contacts', 'contacts__standard_department')
        .get(id=...)

Without prefetching, expect N+1 queries on contacts. The ClientAccount
lookup is a single indexed PK query per call -- small and not cached
in v1. If profiling shows it matters, move tenant_name resolution to
the pipeline orchestrator (resolve once, pass three times).
"""

import logging

from app_modules.signals.constants import (
    ConstraintNature,
    ImpactType,
    SignalDimension,
    SignalWhat,
    UsageScope,
)
from end_users.models import ClientAccount


logger = logging.getLogger(__name__)

CONTEXT_VERSION = 'v1'

_SUPPORTED_STAGES = (
    'pain_impact', 'pain', 'objective', 'impact', 'techstack', 'blocker',
    'constraint', 'competitor',
)

# Stages that carry NO canonical taxonomy (no what/dimension, no nature, no
# scope). They receive the session block only -- emitting an empty taxonomy
# header would waste tokens and confuse the LLM with an irrelevant instruction.
_NO_TAXONOMY_STAGES = ('blocker', 'competitor')


# =============================================================================
# PUBLIC ENTRY POINT
# =============================================================================

def build_context_layer(activity, target_stage):
    """
    Assemble the context block for one sub-call of the transcript_signals
    pipeline.

    Args:
        activity: app_modules.activities.models.Activity. Anchor for all
            session grounding (tenant, account, contacts).
        target_stage: One of 'pain_impact', 'pain', 'objective', 'impact',
            'techstack', 'blocker'. Drives which canonical enums are
            exposed. 'pain_impact' is the merged stage (A2) and exposes the
            union of the pain and impact axes.

    Returns:
        str: A ready-to-concatenate context block. Will be combined
        with the request layer by PromptBuilder.assemble() to form the
        final user message.

    Stage-specific block composition:
        pain / objective / impact / techstack
            session + taxonomy. The techstack stage used to receive the
            TechCatalog list on top; the catalogue is gone (S10).
        blocker
            session only. BlockerSignal carries NO canonical taxonomy
            (no `what` / `dimension` / signal_category). Emitting an
            empty taxonomy header would waste tokens and confuse the LLM
            with an irrelevant instruction; we skip the block entirely.

    Raises:
        ValueError: target_stage is not one of the supported values.
    """
    if target_stage not in _SUPPORTED_STAGES:
        raise ValueError(
            f'Unsupported target_stage: {target_stage!r}. '
            f'Expected one of: {", ".join(_SUPPORTED_STAGES)}.'
        )

    blocks = [_build_session_block(activity)]

    # Taxonomy only for canonical-axis stages.
    # Blocker and competitor stages are intentionally session-only: no
    # canonical enums. See module docstring of blocker_v1.py / competitor_v1.py.
    if target_stage not in _NO_TAXONOMY_STAGES:
        blocks.append(_build_taxonomy_block(target_stage))

        # The techstack stage receives no reference list: tech identity
        # is free text (techstack_v1 emits `tech_name`). The tenant
        # catalogue that used to be injected here was removed in S10.

    return '\n\n'.join(b for b in blocks if b)


# =============================================================================
# SESSION BLOCK -- Tenant + Account + Activity + Contacts
# =============================================================================

def _build_session_block(activity):
    """Render the commercial identity grounding block."""
    lines = ['SESSION CONTEXT']

    # --- Tenant (Seller) ---
    tenant_name = _resolve_tenant_name(activity.client_id)
    lines.append(
        f'- Seller (the sales organization conducting the call): {tenant_name}'
    )

    # --- Account (Prospect) ---
    account = activity.account
    extras = []
    if account.industry:
        extras.append(f'Industry: {account.get_industry_display()}')
    if account.classification:
        extras.append(f'Segment: {account.get_classification_display()}')
    suffix = f' ({", ".join(extras)})' if extras else ''
    lines.append(
        f'- Prospect (the account being analyzed): {account.company_name}{suffix}'
    )

    # --- Activity (Type + Date) ---
    activity_type = activity.get_activity_type_display() or 'Activity'
    activity_date = _resolve_activity_date(activity)
    if activity_date:
        lines.append(f'- Activity: {activity_type} on {activity_date}')
    else:
        lines.append(f'- Activity: {activity_type}')

    # --- Contacts present ---
    contact_lines = _build_contact_lines(activity)
    if contact_lines:
        lines.append('- Prospect contacts in this conversation:')
        lines.extend(f'  * {line}' for line in contact_lines)

    return '\n'.join(lines)


def _resolve_tenant_name(client_id):
    """
    Look up the tenant display name for a given client_id UUID.

    ClientAccount is the canonical tenant entity in this platform; its
    `name` field is the human-readable identifier surfaced to end users.

    Falls back to a generic placeholder rather than raising -- a
    missing tenant name should not crash a pipeline run. The fallback
    is logged at WARNING level because a missing ClientAccount for
    an existing Activity indicates a tenant-isolation drift worth
    investigating.
    """
    try:
        return ClientAccount.objects.only('name').get(id=client_id).name
    except ClientAccount.DoesNotExist:
        logger.warning(
            'tenant_name_unresolved',
            extra={
                'client_id': str(client_id),
                'event': 'ai_pipeline_context_build',
            },
        )
        return 'the seller'


def _resolve_activity_date(activity):
    """
    Best-effort human-readable date for the activity.

    Priority:
        1. completed_at  -- the activity actually took place.
        2. scheduled_date -- the planned moment (date only; time of
           day rarely helps signal extraction so it is omitted).
        3. None -- activity is rendered without a date suffix.

    ISO-8601 (YYYY-MM-DD) for unambiguous LLM parsing.
    """
    if activity.completed_at:
        return activity.completed_at.date().isoformat()
    if activity.scheduled_date:
        return activity.scheduled_date.isoformat()
    return None


def _build_contact_lines(activity):
    """
    Render one descriptor per contact attached to the activity.

    Format per descriptor: "<first_name> (<job_title>, <department>)"
        - Missing first_name --> "Contact" placeholder.
        - Missing job_title --> "role unknown" placeholder.
        - Missing department --> dropped from the parenthesis.
        - email / phone --> NEVER rendered (see module docstring).

    Returns:
        list[str]: One descriptor per contact. Empty list when the
        activity has no linked contacts (the caller skips the
        "Prospect contacts" line entirely in that case).
    """
    descriptors = []
    for contact in activity.contacts.all():
        name = (contact.first_name or '').strip() or 'Contact'
        job = (contact.job_title or '').strip() or 'role unknown'

        department = None
        if contact.standard_department:
            # standard_department.name is a TextChoices field; display
            # via get_name_display(). Pattern reused from
            # ActivityContactSerializer.get_department_name.
            department = contact.standard_department.get_name_display()

        if department:
            descriptors.append(f'{name} ({job}, {department})')
        else:
            descriptors.append(f'{name} ({job})')
    return descriptors


# =============================================================================
# TAXONOMY BLOCK -- Canonical enums per target stage
# =============================================================================

def _build_taxonomy_block(target_stage):
    """
    Render the per-stage canonical taxonomy as a JSON-array of allowed
    string values for each axis.

    Pain, Objective, and Impact all anchor on the SignalWhat x
    SignalDimension canonical pair (the canonical_key of the resulting
    signal). Impact additionally carries an `impact_type` axis
    (ImpactType enum) that classifies the nature of the consequence
    (financial / time / human / strategic / ...).

    TechStack does NOT use the (what, dimension) pair -- it is identified
    by its free-text `tech_name` (S10). Its only enum here is usage_scope.

    # TODO(S10 -> AI-sprint): the techstack branch below exposes
    # usage_scope only. is_competitor and is_integration are no longer
    # techstack booleans (retired to the CompetitorSignal / ConstraintSignal
    # stages). If the surviving is_to_replace flag ever needs grounding data
    # to be set reliably, this is where that block belongs, next to the other
    # per-stage context. See the matching TODO in techstack_v1.py.

    Field-level extraction details (which fields the LLM must emit,
    when to OMIT a signal) live in the per-stage request layer
    (pain_v1.py, objective_v1.py, impact_v1.py, techstack_v1.py).

    Deferred axes per stage (forced to a hardcoded default by the
    persistence service, rep refines during validation):
      * Objective: scope_level forced to BUSINESS.
      * Impact:    scope_level forced to BUSINESS; metric_text and
                   human_impact left empty.
    """
    lines = [
        'CANONICAL TAXONOMY '
        '(pick exactly one value from each list, or OMIT the signal)'
    ]

    if target_stage == 'pain_impact':
        # Merged pain + impact stage: the union of the pain axes and the
        # impact axes. `what` / `dimension` apply to both; `impact_type`
        # applies to IMPACT signals only; the scope block applies to both
        # (each signal resolves its own scope independently).
        lines.extend(_what_dimension_lines())
        lines.append(
            '- impact_type (nature of the observed consequence -- '
            'IMPACT signals only): '
            + _enum_json_array(ImpactType)
        )
        lines.extend(_scope_taxonomy_lines())

    elif target_stage == 'pain':
        lines.extend(_what_dimension_lines())
        lines.extend(_scope_taxonomy_lines())

    elif target_stage == 'objective':
        lines.extend(_what_dimension_lines())
        lines.extend(_scope_taxonomy_lines())

    elif target_stage == 'impact':
        lines.extend(_what_dimension_lines())
        lines.append(
            '- impact_type (nature of the observed consequence): '
            + _enum_json_array(ImpactType)
        )
        lines.extend(_scope_taxonomy_lines())

    elif target_stage == 'techstack':
        # usage_scope = SCALE axis (how widely). usage_departments = WHO
        # axis (which departments use the tool, multi-department). Both are
        # emitted per tool; the department list is drawn from the
        # StandardDepartment controlled vocabulary so the extractor resolves
        # each name by exact match (no fuzzy matching), same contract as the
        # shared scope block for pain/objective/impact/constraint.
        from app_modules.core_modules.models import StandardDepartment
        lines.append(
            '- usage_scope (SCALE -- how widely the prospect uses the tool): '
            + _enum_json_array(UsageScope)
        )
        lines.append(
            '- usage_departments (WHO -- the department(s) that USE the '
            'tool; pick zero or more values from this list, exact strings): '
            + _enum_json_array(StandardDepartment.DepartmentChoices)
        )

    elif target_stage == 'constraint':
        # Constraint is DETACHED from the what x dimension canonical axes
        # (sub-step 1): no _what_dimension_lines here. It is classified on
        # `nature` and scoped on the multi-department target_departments list
        # (sub-step 1c) — no scope_level, no single FK. The department vocab is
        # injected as a list of valid names, cloning the techstack
        # usage_departments contract, so the extractor resolves each name by
        # exact match (no fuzzy matching). _scope_taxonomy_lines stays untouched
        # for pain/objective/impact.
        from app_modules.core_modules.models import StandardDepartment
        lines.append(
            '- nature (kind of decision criterion; pick EXACTLY ONE code): '
            + _enum_coded_list(ConstraintNature)
        )
        lines.append(
            '- target_departments (WHO the constraint concerns; pick zero or '
            'more values from this list, exact strings; [] when no specific '
            'department is named): '
            + _enum_json_array(StandardDepartment.DepartmentChoices)
        )

    return '\n'.join(lines)


def _enum_json_array(enum_cls):
    """
    Render a Django TextChoices enum as a JSON-array of its DB values.

    Example for SignalWhat:
        ["OPS", "TECH", "DATA", "PEOPLE", "GROWTH"]

    We expose DB values (not labels) because that is what the model
    must emit back to us -- no translation step needed on read.
    """
    return '[' + ', '.join(f'"{v}"' for v in enum_cls.values) + ']'


def _enum_coded_list(enum_cls):
    """
    Render a Django TextChoices enum as a code+label list:

        "OPS" (Operations / Process), "TECH" (Technology / System), ...

    The model must EMIT the code (the DB value) -- that is what the
    persistence layer stores. The parenthetical label is a gloss so the
    model can map a business AREA it reads in the transcript
    ("operational", "reporting", "hiring") to the right code, instead of
    grabbing a surface word. Codes are the contract; labels are the hint.
    """
    return ', '.join(f'"{v}" ({label})' for v, label in enum_cls.choices)


def _what_dimension_lines():
    """
    Render the shared `what` (DOMAIN) / `dimension` (MEASURE AXIS) block
    for the pain / objective / impact / pain_impact stages.

    The distinction is stated hard because the LLM has been observed to
    pull a DIMENSION word ("cost") into the DOMAIN slot -- e.g. "reduce
    operational costs by 15%" stored as what=COST instead of what=OPS.
    `what` is the business AREA; `dimension` is the MEASURE. A dimension
    word is NEVER a valid `what`.
    """
    return [
        '- what = DOMAIN (the business AREA concerned). Pick EXACTLY ONE '
        'code from: ' + _enum_coded_list(SignalWhat),
        '- dimension = MEASURE AXIS (the kind of friction / outcome). Pick '
        'EXACTLY ONE code from: ' + _enum_coded_list(SignalDimension),
        '- DOMAIN vs DIMENSION: `what` is the AREA, `dimension` is the '
        'MEASURE. A word like "cost / coût", "time / temps" or "quality" is '
        'ALWAYS a dimension, NEVER a `what`. If an observation is about '
        'operations, `what`="OPS" and the cost belongs in dimension="COST" -- '
        'never the reverse. Never invent a `what` value outside the list above.',
    ]


def _scope_taxonomy_lines():
    """
    Render the scope_level + target_department taxonomy shared by the
    pain / objective / impact / constraint stages.

    scope_level is deliberately restricted to BUSINESS | DEPARTMENT --
    PERSONAL is NOT offered to the model. Scope is decided by the SUBJECT
    of the observation (which department it concerns), never by the
    seniority or department of the speaker. target_department is drawn
    from the controlled StandardDepartment vocabulary (DB values), so
    whatever the model emits resolves by an exact name lookup in the
    extractor -- no fuzzy matching. It is REQUIRED when scope_level is
    DEPARTMENT and null otherwise.

    Emission threshold (over-attribution guard)
    -------------------------------------------
    The model was observed to OVER-ATTRIBUTE a department: it tagged a
    company-wide requirement to a department off a technical theme-word
    ("encryption" -> IT) or off the speaker's own department, with no
    department actually designated as the subject. The rule below raises
    the emission threshold: DEPARTMENT is emitted ONLY when a department
    is explicitly named or unambiguously designated as the owning
    subject; WHEN IN DOUBT, BUSINESS. An explicit anti-over-correction
    clause keeps a genuinely designated department from being folded back
    to BUSINESS -- the guard raises the threshold, it does not forbid
    DEPARTMENT.

    The backend applies the same restriction as a safety net (any value
    other than DEPARTMENT folds to BUSINESS; an unresolved department
    folds to BUSINESS), so a drifting model emission never produces an
    invalid row.
    """
    # Lazy import: StandardDepartment lives in core_modules; importing it
    # at module load would couple the prompt package to that app's load
    # order for no benefit (this builder runs at request time only).
    from app_modules.core_modules.models import StandardDepartment

    return [
        '- scope_level (organisational scope of the observation): '
        '["BUSINESS", "DEPARTMENT"] '
        '-- the scope is determined by the SUBJECT of the observation '
        '(which perimeter the pain/objective/impact/constraint concerns), '
        'NOT by who is speaking. Emit DEPARTMENT ONLY when one specific '
        'department is EXPLICITLY NAMED or unambiguously DESIGNATED as the '
        'subject that owns the observation ("the IT department requires", '
        '"our DSI mandates", "the Marketing team owns this", "Finance '
        'imposes"); use that department verbatim from the list below, even '
        'if a person from another department says it, and even if the '
        'financial consequence hits the whole company. Otherwise emit '
        'BUSINESS: no department is named, or the observation is '
        'company-wide or cross-departmental. WHEN IN DOUBT, emit BUSINESS '
        'with target_department = null -- BUSINESS is the safe default. '
        'A technical theme-word alone (SSO, ERP, encryption, chiffrement, '
        'cloud, API) does NOT designate a department: "we need end-to-end '
        'encryption" with no department named is company-wide -> BUSINESS, '
        'never IT. The seniority, role, or department of the SPEAKER never '
        'determines scope, in EITHER direction -- an IT lead stating a '
        'company-wide need is still BUSINESS, and a CEO describing one '
        'explicitly named department is still DEPARTMENT. '
        'ANTI-OVER-CORRECTION: a department that IS explicitly named or '
        'clearly designated as the subject MUST stay that department -- do '
        'NOT fold a legitimately designated department back to BUSINESS; '
        'fold to BUSINESS only what is genuinely undesignated. Never emit '
        'any other value.',
        '- SCOPE EXAMPLES (designation decides -- not the speaker, not a '
        'technical word): '
        '"the IT department requires integration with their SAP instance" '
        '-> scope_level="DEPARTMENT", target_department="IT" (IT is '
        'explicitly designated as the owner); '
        '"we need end-to-end encryption" (no department named) '
        '-> scope_level="BUSINESS", target_department=null (a technical '
        'need alone does not designate a department).',
        '- target_department (REQUIRED when scope_level is "DEPARTMENT", '
        'null when "BUSINESS"; pick exactly one value from this list): '
        + _enum_json_array(StandardDepartment.DepartmentChoices),
    ]
