# app_modules/decision_cycles/constants.py
"""
Constants for Decision Cycle module.

Contains fixed choices for Decision Stages and Step Status.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class DecisionStage(models.TextChoices):
    """
    Fixed decision stages for layout/grouping.
    
    These are NOT steps - they are structural stages
    used for visual organization of the timeline.
    Same stages for all Decision Cycles, not optional.
    """
    EXPLORATION = 'EXPLORATION', _('Exploration')
    CRITERIA_VALIDATION = 'CRITERIA_VALIDATION', _('Criteria Validation')
    SOLUTION_CONFIRMATION = 'SOLUTION_CONFIRMATION', _('Solution Confirmation')
    BUSINESS_VALIDATION = 'BUSINESS_VALIDATION', _('Business Validation')
    FORMALIZATION = 'FORMALIZATION', _('Formalization')


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