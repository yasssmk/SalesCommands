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