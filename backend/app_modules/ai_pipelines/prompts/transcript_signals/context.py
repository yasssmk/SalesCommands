# app_modules/ai_pipelines/prompts/transcript_signals/context.py
"""
Context layer for the transcript_signals prompt family.

Builds the dynamic, per-run context block that grounds the LLM in:
  * The commercial identity of the session (Seller, Prospect, Activity, Contacts)
  * The canonical taxonomy applicable to the target sub-call
  * The tenant's curated TechCatalog (techstack sub-call only)

What this layer carries
-----------------------
  - Tenant display name (from ClientAccount.name).
  - Prospect commercial identity (company_name, industry, classification).
  - Activity metadata (type, date).
  - Contacts on the activity: first_name + job_title + department only.
  - Canonical enum values per target stage.
  - TechCatalog entries (target_stage == 'techstack' only).

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
    ImpactType,
    SignalDimension,
    SignalWhat,
    UsageScope,
)
from app_modules.tech_catalog.models import TechCatalog
from end_users.models import ClientAccount


logger = logging.getLogger(__name__)

CONTEXT_VERSION = 'v1'

_SUPPORTED_STAGES = ('pain', 'objective', 'impact', 'techstack', 'blocker')


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
        target_stage: One of 'pain', 'objective', 'impact', 'techstack',
            'blocker'. Drives which canonical enums are exposed AND
            whether the TechCatalog list is appended.

    Returns:
        str: A ready-to-concatenate context block. Will be combined
        with the request layer by PromptBuilder.assemble() to form the
        final user message.

    Stage-specific block composition:
        pain / objective / impact / techstack
            session + taxonomy (+ techcatalog for techstack)
        blocker
            session only. BlockerSignal carries NO canonical taxonomy
            (no `what` / `dimension` / signal_category) and does not
            consume the TechCatalog. Emitting an empty taxonomy header
            would waste tokens and confuse the LLM with an irrelevant
            instruction; we skip the block entirely.

    Raises:
        ValueError: target_stage is not one of the supported values.
    """
    if target_stage not in _SUPPORTED_STAGES:
        raise ValueError(
            f'Unsupported target_stage: {target_stage!r}. '
            f'Expected one of: {", ".join(_SUPPORTED_STAGES)}.'
        )

    blocks = [_build_session_block(activity)]

    # Taxonomy + techcatalog only for canonical-axis stages.
    # Blocker stage is intentionally session-only: no canonical enums,
    # no catalog dependency. See module docstring of blocker_v1.py.
    if target_stage != 'blocker':
        blocks.append(_build_taxonomy_block(target_stage))
        if target_stage == 'techstack':
            blocks.append(_build_techcatalog_block(activity))

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

    TechStack does NOT use the (what, dimension) pair -- its canonical
    axis is the TechCatalog entry. Its only enum here is usage_scope.

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

    if target_stage == 'pain':
        lines.append(
            '- what (area of the business affected): '
            + _enum_json_array(SignalWhat)
        )
        lines.append(
            '- dimension (friction or outcome experienced): '
            + _enum_json_array(SignalDimension)
        )

    elif target_stage == 'objective':
        # v1: scope_level is forced to BUSINESS by the persistence service
        # (rep refines scope and target during validation).
        lines.append(
            '- what (area of the business targeted): '
            + _enum_json_array(SignalWhat)
        )
        lines.append(
            '- dimension (outcome sought): '
            + _enum_json_array(SignalDimension)
        )

    elif target_stage == 'impact':
        # v1: scope_level is forced to BUSINESS by the persistence
        # service (rep refines scope during validation). metric_text
        # and human_impact are NOT extracted in v1 -- the rep adds
        # them during validation when relevant. See impact_v1.py
        # docstring for the rationale.
        lines.append(
            '- what (area of the business affected): '
            + _enum_json_array(SignalWhat)
        )
        lines.append(
            '- dimension (friction or outcome experienced): '
            + _enum_json_array(SignalDimension)
        )
        lines.append(
            '- impact_type (nature of the observed consequence): '
            + _enum_json_array(ImpactType)
        )

    elif target_stage == 'techstack':
        lines.append(
            '- usage_scope (how widely the prospect uses the tool): '
            + _enum_json_array(UsageScope)
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


# =============================================================================
# TECHCATALOG BLOCK -- Tenant's curated product catalog (techstack only)
# =============================================================================

def _build_techcatalog_block(activity):
    """
    Render the tenant's TechCatalog as a compact reference list for the
    techstack sub-call.

    The LLM uses this list to attempt matching prospect-side tool
    mentions to a curated entry. The request layer (techstack_v1)
    instructs the LLM to emit `tech_catalog_entry_id` when a match
    is found, or `tech_name_raw` otherwise. The persistence service
    creates the signal in PENDING with tech_catalog_entry
    either set (UUID match) or NULL + metadata.pending_tech_name=<raw>
    (rep attaches the catalog entry before validating).

    Token strategy
    --------------
    One entry per line: `<uuid> | <label> [<flags>]`. No truncation in
    v1 -- catalog hygiene is expected to keep the list reasonable.
    If a tenant accumulates a very large catalog we will add
    ranking + truncation in a v2.

    Empty catalog
    -------------
    Rendered with an explicit "(empty)" marker so the LLM understands
    it must always emit `tech_name_raw` (no match possible).

    Tenant isolation
    ----------------
    The TechCatalog queryset is filtered by activity.client_id. Any
    cross-tenant leak here would be a SOC violation -- the filter is
    the single source of truth.
    """
    entries = list(
        TechCatalog.objects
        .filter(client_id=activity.client_id)
        .order_by('company_name', 'product_name')
        .values(
            'id',
            'company_name',
            'product_name',
            'is_competitor',
            'is_integration_target',
        )
    )

    lines = [
        'TECH CATALOG (tenant-curated reference list for tech matching)',
        'Match prospect-side tool mentions to one of these entries when '
        'possible. Emit `tech_catalog_entry_id` with the matching id. '
        'Emit `tech_name_raw` (free text, no id) only if no entry fits.',
    ]

    if not entries:
        lines.append('- (catalog is empty -- always emit tech_name_raw)')
        return '\n'.join(lines)

    for entry in entries:
        if entry['company_name'] == entry['product_name']:
            label = entry['company_name']
        else:
            label = f"{entry['company_name']} / {entry['product_name']}"

        flags = []
        if entry['is_competitor']:
            flags.append('competitor')
        if entry['is_integration_target']:
            flags.append('integration_target')
        flags_str = f" [{', '.join(flags)}]" if flags else ''

        lines.append(f"- {entry['id']} | {label}{flags_str}")

    return '\n'.join(lines)