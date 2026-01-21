# app_modules/decision_cycles/constants.py
"""
Constants for Decision Cycle module.

Contains fixed choices for Decision Stages and Step Status.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class PipelineStep(models.TextChoices):
    """
    Fixed pipeline steps for Decision Cycles.
    
    These steps are AUTO-CREATED when a Decision Cycle is created.
    Users CANNOT create, delete, or reorder these steps.
    Users CAN only add activities within each step.
    
    Steps are displayed as columns in the pipeline view.
    Activities are displayed as cards within each column.
    
    IMPORTANT: To modify step names or add/remove steps,
    update this enum and run the migration.
    """
    QUALIFICATION = 'QUALIFICATION', _('Qualification')
    TECHNICAL_FIT = 'TECHNICAL_FIT', _('Technical Fit')
    SOLUTION_VALIDATION = 'SOLUTION_VALIDATION', _('Solution Validation')
    BUSINESS_CASE = 'BUSINESS_CASE', _('Business Case')
    CLOSING = 'CLOSING', _('Closing')
    IMPLEMENTATION = 'IMPLEMENTATION', _('Implementation')
    GO_LIVE = 'GO_LIVE', _('Go Live')


# Pipeline step configuration
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
    {
        'step': PipelineStep.IMPLEMENTATION,
        'order': 6,
        'activity_optional': True,  # Often client-side, no AE action
        'description': 'Deploy and configure solution',
    },
    {
        'step': PipelineStep.GO_LIVE,
        'order': 7,
        'activity_optional': True,  # Often client-side, no AE action
        'description': 'Launch and verify successful adoption',
    },
]

# Quick lookup helpers
PIPELINE_STEPS_ORDER = [cfg['step'] for cfg in PIPELINE_STEPS_CONFIG]
ACTIVITY_OPTIONAL_STEPS = [cfg['step'] for cfg in PIPELINE_STEPS_CONFIG if cfg['activity_optional']]


# Legacy alias for backward compatibility during migration
# TODO: Remove after full migration
DecisionStage = PipelineStep


class DecisionStepStatus(models.TextChoices):
    """
    Status choices for Decision Steps.
    
    VALIDATED = explicit client approval
    REJECTED = explicit refusal / loss
    """
    NOT_STARTED = 'NOT_STARTED', _('Not Started')
    PENDING_CLIENT = 'PENDING_CLIENT', _('Pending Client')
    IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
    IN_CHASING = 'IN_CHASING', _('In Chasing')
    VALIDATED = 'VALIDATED', _('Validated')
    REJECTED = 'REJECTED', _('Rejected')
    ON_HOLD = 'ON_HOLD', _('On Hold')
    CANCELLED = 'CANCELLED', _('Cancelled')

class StalledReason(models.TextChoices):
    """
    Reasons why a DecisionStep might be considered stalled.
    
    Used for computed property detection and UI warnings.
    """
    NONE = 'NONE', _('Not stalled')
    NO_ACTIVITY = 'NO_ACTIVITY', _('No activities linked')
    NO_FUTURE_ACTIVITY = 'NO_FUTURE_ACTIVITY', _('No future activities planned')
    NO_NEXT_STEP = 'NO_NEXT_STEP', _('Last activity marked no next step agreed')
    EXPECTED_END_PASSED = 'EXPECTED_END_PASSED', _('Expected end date has passed')
    WAITING_TOO_LONG = 'WAITING_TOO_LONG', _('No activity in 7+ days')