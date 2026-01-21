# app_modules/decision_cycles/services/next_step_draft.py
"""
DEPRECATED: Next Step Draft Service.

This service is NO LONGER USED since Pipeline Steps redesign.

Pipeline steps are now:
- Auto-created when a Decision Cycle is created (7 fixed steps)
- Cannot be created/deleted by users
- Users can only add activities within existing steps

The concept of "drafting a next step" no longer applies.
Users navigate between existing fixed steps instead.

This file is kept for reference only. Will be removed in future cleanup.
"""

import warnings
from ..constants import PipelineStep, DecisionStepStatus, PIPELINE_STEPS_ORDER


class NextStepDraftService:
    """
    DEPRECATED: Service to generate next step draft data.
    
    DO NOT USE - Pipeline steps are now fixed and auto-created.
    
    For navigation between steps, use the step's `order` field
    to find previous/next steps in the pipeline.
    """

    def __init__(self):
        warnings.warn(
            "NextStepDraftService is deprecated. "
            "Pipeline steps are now auto-created and fixed. "
            "Use DecisionStep.order for navigation instead.",
            DeprecationWarning,
            stacklevel=2
        )

    def create_draft(self, current_step, **kwargs):
        """DEPRECATED: No longer creates drafts."""
        warnings.warn(
            "create_draft() is deprecated. Steps cannot be created manually.",
            DeprecationWarning,
            stacklevel=2
        )
        return None

    @staticmethod
    def get_next_step(current_step):
        """
        Get the next pipeline step after the current one.
        
        Use this instead of create_draft() for navigation.
        
        Args:
            current_step: DecisionStep instance
            
        Returns:
            DecisionStep or None
        """
        if not current_step or not current_step.cycle:
            return None
        
        return current_step.cycle.steps.filter(
            order__gt=current_step.order
        ).order_by('order').first()
    
    @staticmethod
    def get_previous_step(current_step):
        """
        Get the previous pipeline step before the current one.
        
        Args:
            current_step: DecisionStep instance
            
        Returns:
            DecisionStep or None
        """
        if not current_step or not current_step.cycle:
            return None
        
        return current_step.cycle.steps.filter(
            order__lt=current_step.order
        ).order_by('-order').first()