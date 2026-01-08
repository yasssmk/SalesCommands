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

class DecisionStepType(models.TextChoices):
    """
    Type choices for Decision Steps.
    
    Differentiates between seller-side tasks and buyer-side validations.
    """
    MEETING = 'MEETING', _('Meeting')
    CALL = 'CALL', _('Call')
    EMAIL = 'EMAIL', _('Email')
    TASK_SELLER = 'TASK_SELLER', _('Task (Seller)')
    TASK_BUYER = 'TASK_BUYER', _('Task (Buyer)')
    INTERNAL_VALIDATION = 'INTERNAL_VALIDATION', _('Internal Validation')
    OTHER = 'OTHER', _('Other')