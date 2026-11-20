# app_modules/decision_cycles/constants.py
"""
Constants for Decision Cycle module.

Contains fixed choices for Pipeline Steps, Step Status, and Cycle Outcome.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


# ==========================================================================
# PIPELINE STEPS
# ==========================================================================

class PipelineStep(models.TextChoices):
    """
    Fixed pipeline steps for Decision Cycles.

    Auto-created steps (5): QUALIFICATION → CLOSING.
    IMPLEMENTATION and GO_LIVE kept in enum for backward compatibility
    with existing cycles but are NOT auto-created for new cycles.

    Users CANNOT create, delete, or reorder steps.
    Users CAN only add activities within each step.
    """
    QUALIFICATION = 'QUALIFICATION', _('Qualification')
    TECHNICAL_FIT = 'TECHNICAL_FIT', _('Technical Fit')
    SOLUTION_VALIDATION = 'SOLUTION_VALIDATION', _('Solution Validation')
    BUSINESS_CASE = 'BUSINESS_CASE', _('Business Case')
    CLOSING = 'CLOSING', _('Closing')
    # Kept for backward compatibility — NOT auto-created for new cycles
    IMPLEMENTATION = 'IMPLEMENTATION', _('Implementation')
    GO_LIVE = 'GO_LIVE', _('Go Live')


# Pipeline step configuration — only 5 steps auto-created for new cycles
# Order determines display sequence (left to right)
PIPELINE_STEPS_CONFIG = [
    {
        'step': PipelineStep.QUALIFICATION,
        'order': 1,
        'activity_optional': False,
        'description': 'Identify needs and validate opportunity fit',
    },
    {
        'step': PipelineStep.TECHNICAL_FIT,
        'order': 2,
        'activity_optional': False,
        'description': 'Validate technical and operational requirements',
    },
    {
        'step': PipelineStep.SOLUTION_VALIDATION,
        'order': 3,
        'activity_optional': False,
        'description': 'Confirm solution meets buyer criteria',
    },
    {
        'step': PipelineStep.BUSINESS_CASE,
        'order': 4,
        'activity_optional': False,
        'description': 'Secure budget and business approval',
    },
    {
        'step': PipelineStep.CLOSING,
        'order': 5,
        'activity_optional': False,
        'description': 'Finalize contract and legal terms',
    },
]

# Quick lookup helpers
PIPELINE_STEPS_ORDER = [cfg['step'] for cfg in PIPELINE_STEPS_CONFIG]
ACTIVITY_OPTIONAL_STEPS = [cfg['step'] for cfg in PIPELINE_STEPS_CONFIG if cfg['activity_optional']]

# Legacy alias for backward compatibility during migration
# TODO: Remove after full migration
DecisionStage = PipelineStep


# ==========================================================================
# CYCLE OUTCOME (NEW — two-layer architecture)
# ==========================================================================

class CycleOutcome(models.TextChoices):
    """
    Explicit cycle-level strategic decision.

    These are set by user action (close/reopen), NOT derived from activities.
    When set, cycle.outcome overrides all step-based status derivation.

    WON / LOST / NOT_QUALIFIED → terminal (PLANNED activities auto-cancelled)
    ON_HOLD → paused (PLANNED activities kept, deal alive but frozen)
    """
    WON = 'WON', _('Won')
    LOST = 'LOST', _('Lost')
    ON_HOLD = 'ON_HOLD', _('On Hold')
    NOT_QUALIFIED = 'NOT_QUALIFIED', _('Not Qualified')


# Terminal outcomes that auto-cancel PLANNED activities
TERMINAL_OUTCOMES = frozenset([CycleOutcome.WON, CycleOutcome.LOST, CycleOutcome.NOT_QUALIFIED])

# Sprint « Deal health v2 », 6c (PO): the outcomes that CLOSE a cycle for the
# deal health — no new analysis (A10, DEAL_HEALTH_CYCLE_CLOSED). ON_HOLD is a
# pause, not a closure: the deal health runs there (with its « nothing new »
# guard). The terminal outcomes above, one list.
DEAL_HEALTH_CLOSED_OUTCOMES = TERMINAL_OUTCOMES

# Step 8 (PO decision n° 7): the deal health's freshness applies from this
# declared step on (the order of PIPELINE_STEPS_ORDER) — before it, too
# little is known for a diagnostic to be expected.
DEAL_HEALTH_MIN_STEP = PipelineStep.TECHNICAL_FIT


# ==========================================================================
# STEP STATUS (SIMPLIFIED)
# ==========================================================================

class DecisionStepStatus(models.TextChoices):
    """
    Status of a Decision Step in the pipeline.

    ALL statuses are DERIVED automatically from activity data.
    No manual status change — the step observes its activities.

    Derivation priority (highest first):
    1. OVERDUE     — step deadline passed OR any PLANNED activity past scheduled/due date
    2. VALIDATED   — ALL activities completed (0 PLANNED) + later step has activities
    3. IN_PROGRESS — at least 1 PLANNED activity exists
    4. STALLED     — completed activities exist, no PLANNED, no activity in later steps
    5. NOT_STARTED — no activities

    IN_CHASING: Reserved for future Campaign/Sequence feature (not auto-derived).

    Removed (moved to CycleOutcome): WON, REJECTED, ON_HOLD
    """
    NOT_STARTED = 'NOT_STARTED', _('Not Started')
    IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
    STALLED = 'STALLED', _('Stalled')
    IN_CHASING = 'IN_CHASING', _('In Chasing')
    OVERDUE = 'OVERDUE', _('Overdue')
    VALIDATED = 'VALIDATED', _('Validated')

# ==========================================================================
# DEAL HEALTH SNAPSHOT — schema versions (sprint « Deal health v2 »)
# ==========================================================================
#
# DealHealthSnapshot.schema_version: the shape of its `diagnostic` JSON.
#   V1 — the original diagnostic (7 dimensions, gaps, levers, themes).
#        Every snapshot written before the v2 prompt, and the default.
#   V2 — the « manager / coach » diagnostic (sprint « Deal health v2 »,
#        step 5); it keeps every key V1 readers use (DealHealthView, the
#        prep call).
DEAL_HEALTH_SCHEMA_V1 = 1
DEAL_HEALTH_SCHEMA_V2 = 2


# ==========================================================================
# STAKEHOLDER PROFILE (sprint « Deal health v2 », step 4)
# ==========================================================================
#
# Stakeholder.profile — what helps convince this person, per FIELD:
#   {field: {value, source, updated_at, updated_by, original_value}}
# Written ONLY by services/stakeholder_service.apply_ai_profile /
# apply_manual_profile. `source` takes the SignalSource values
# (signals/constants.py): LLM_EXTRACTED (the AI), LLM_MODIFIED (an AI value
# edited by a user, original_value kept), MANUAL (entered by a user). The AI
# never overwrites a MANUAL or LLM_MODIFIED field.

class ConvictionState(models.TextChoices):
    """How convinced the stakeholder is (closed list, amendment A8)."""
    CHAMPION   = 'CHAMPION',   _('Champion')
    SUPPORTIVE = 'SUPPORTIVE', _('Supportive')
    NEUTRAL    = 'NEUTRAL',    _('Neutral')
    SKEPTICAL  = 'SKEPTICAL',  _('Skeptical')
    OPPOSED    = 'OPPOSED',    _('Opposed')
    UNKNOWN    = 'UNKNOWN',    _('Unknown')


PROFILE_CONVICTION_STATE = 'conviction_state'
PROFILE_CONVINCING_METRICS = 'convincing_metrics'
PROFILE_FRUSTRATIONS = 'frustrations'
PROFILE_CONVICTION_STRATEGY = 'conviction_strategy'
PROFILE_COMMUNICATION_STYLE = 'communication_style'
PROFILE_COMMUNICATION_LANGUAGE = 'communication_language'

STAKEHOLDER_PROFILE_FIELDS = (
    PROFILE_CONVICTION_STATE,
    PROFILE_CONVINCING_METRICS,
    PROFILE_FRUSTRATIONS,
    PROFILE_CONVICTION_STRATEGY,
    PROFILE_COMMUNICATION_STYLE,
    PROFILE_COMMUNICATION_LANGUAGE,
)

# communication_language: a BCP-47 tag ("fr", "en-US", "pt-BR"), the
# convention of BaseSignal.language_original (signals/models/base_model.py,
# max 10 characters): a 2-3 letter language, optional subtags.
PROFILE_LANGUAGE_MAX_LENGTH = 10
PROFILE_LANGUAGE_PATTERN = r'^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$'

# Free-text fields: a bound so one value can never bloat the row / prompt.
PROFILE_TEXT_MAX_LENGTH = 2000
