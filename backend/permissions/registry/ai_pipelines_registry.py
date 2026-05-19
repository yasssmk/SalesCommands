# permissions/registry/ai_pipelines_registry.py
"""
Permissions registry for the AI Pipelines module.

The AI Pipelines module orchestrates LLM calls for the platform. Its
inaugural use case (Sprint LLM Transcript Extraction) extracts Pain,
Objective, and TechStack signals from a sales-call transcript pasted
by the rep into an Activity. Each pipeline run is recorded as an
`AIPipelineRun` audit document — metadata only (no transcript stored,
only its sha256 input_hash) so the surface is suitable for collective
tenant-wide read access.

Permission matrix:

    +----------+--------+---------+------------+
    | Action   | admin  | manager | individual |
    +----------+--------+---------+------------+
    | create   | client | client  | client     |
    | read     | client | client  | client     |
    | update   | none   | none    | none       |
    | delete   | none   | none    | none       |
    +----------+--------+---------+------------+

Covered ViewSets / APIViews (all declare `module = 'ai_pipelines'`):
  * TranscriptSignalsExtractView (POST extract endpoint — Phase G)
  * Future read endpoints for AIPipelineRun audit display (out of
    scope for the current sprint but the registry is forward-compatible).

Notes on scope choices:

  * create = `client` for ALL tiers
        Every sales rep needs to extract signals from their own call
        transcripts — that is the core UX of the Wrap-Up tab. The
        creation flow itself is gated by tenant isolation: the
        `TranscriptSignalsExtractView` resolves the supplied
        `activity_id` against a tenant-scoped queryset, so a rep
        cannot trigger extraction on another tenant's activity.

  * read = `client` for ALL tiers
        AIPipelineRun documents are audit records, not sensitive
        payload. The transcript itself is never persisted: only its
        sha256 input_hash, the prompt versions, provider/model
        metadata, status, sub-call timings, and total token counts.
        Tenant-wide visibility lets managers oversee usage and lets
        individuals see their own run history. If future SOC 2
        controls demand narrower access, narrowing to `mine` for
        individual / `team` for manager is a one-line change here.

  * update = `none` for ALL tiers
        Pipeline runs are immutable audit records — they reflect what
        actually happened during an extraction. Mutating them after
        the fact would erode their value.

  * delete = `none` for ALL tiers
        Audit retention is the goal. If a tenant needs to purge runs
        (e.g. GDPR-driven account deletion), that flow is owned by
        the tenant-admin cleanup process, not by per-record DELETEs
        here.

  * No 'team' / 'mine' scopes used
        Same rationale as `signals_registry`: the orchestration
        surface is tenant-wide by design. Inter-rep boundaries — if
        ever needed — belong in `permissions/ownership.py`, not in
        this registry.

OWNERSHIP_MAP coupling:

    The `ai_pipelines` entry in `permissions/ownership.py` (A.10)
    declares ownership_type = 'none' and only `client_account_fk` is
    set (`'client_id'`). This makes ScopedQuerysetMixin filter
    strictly by tenant for all tiers, consistent with the matrix
    above. AIPipelineRun has no concept of per-record ownership
    beyond the `user` FK (which records WHO triggered the run for
    audit) — not a visibility boundary.

Custom actions on the views:

    None for MVP. The single endpoint (TranscriptSignalsExtractView)
    is a POST that triggers extraction — gated by `create` here.
    No `action_policies` declared on the view. Future read endpoints
    for AIPipelineRun listing will rely on the `read` action above.
"""

from typing import Dict, Literal


# ============================================================================
# TYPE ALIASES
# ============================================================================

Action = Literal['create', 'read', 'update', 'delete']
Tier = Literal['admin', 'manager', 'individual']
Scope = Literal['client', 'team', 'mine', 'none']
ModulePermissions = Dict[Action, Dict[Tier, Scope]]


# ============================================================================
# AI_PIPELINES REGISTRY
# ============================================================================

AI_PIPELINES_REGISTRY: Dict[str, ModulePermissions] = {

    # ========================================================================
    # AI_PIPELINES MODULE
    # Covers all LLM orchestration endpoints (transcript-signal
    # extraction in this sprint; pre-call game plan generation and
    # other pipelines in later sprints).
    # Ownership: none (tenant-wide visibility on audit records).
    # ========================================================================
    'ai_pipelines': {
        'create': {
            'admin':      'client',  # Admins can extract
            'manager':    'client',  # Managers can extract
            'individual': 'client',  # Reps can extract — primary UX
        },
        'read': {
            'admin':      'client',  # Admin sees the full audit trail
            'manager':    'client',  # Manager oversees team usage
            'individual': 'client',  # Reps see their own run history
        },
        'update': {
            'admin':      'none',    # Audit records are immutable
            'manager':    'none',
            'individual': 'none',
        },
        'delete': {
            'admin':      'none',    # Audit retention
            'manager':    'none',
            'individual': 'none',
        },
    },

}