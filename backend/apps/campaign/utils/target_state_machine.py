# apps/campaign/utils/target_state_machine.py - UPDATED

from typing import Dict, List, Optional, Set
from datetime import datetime
from django.utils import timezone
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignErrorMessages


class TargetStateMachine:
    """
    State machine for managing CampaignTarget status transitions
    Updated to match existing CampaignTarget.Status choices
    """
    
    # All possible states with descriptions (FIXED: PENDING instead of NEW)
    STATES = {
        'PENDING': 'Newly created target, not yet started',
        'IN_PROGRESS': 'Target being actively worked',
        'CALLBACK_PENDING': 'Waiting for scheduled callback',
        'COMPLETED': 'Target objective achieved',
        'STOPPED': 'Target discontinued (not interested, wrong contact, etc.)'
    }
    
    # Valid transitions: source_state -> [allowed_destination_states] (UPDATED)
    VALID_TRANSITIONS = {
        'PENDING': ['IN_PROGRESS'],
        'IN_PROGRESS': ['CALLBACK_PENDING', 'COMPLETED', 'STOPPED'],
        'CALLBACK_PENDING': ['IN_PROGRESS', 'COMPLETED', 'STOPPED'],
        'COMPLETED': [],  # Final state - no transitions allowed
        'STOPPED': []     # Final state - no transitions allowed
    }
    
    # Business triggers that cause state changes (UPDATED)
    BUSINESS_TRIGGERS = {
        'campaign_started': 'IN_PROGRESS',
        'first_activity_started': 'IN_PROGRESS',
        'callback_requested': 'CALLBACK_PENDING', 
        'callback_expired': 'IN_PROGRESS',
        'successful_activity': 'COMPLETED',
        'meeting_scheduled': 'COMPLETED',
        'lead_created': 'COMPLETED',
        'opportunity_created': 'COMPLETED',
        'not_interested': 'STOPPED',
        'wrong_contact': 'STOPPED',
        'invalid_contact_info': 'STOPPED',
        'unsubscribed': 'STOPPED',
        'manual_completion': 'COMPLETED',
        'manual_stop': 'STOPPED'
    }
    
    # Final states that cannot be changed
    FINAL_STATES = {'COMPLETED', 'STOPPED'}
    
    @classmethod
    def validate_transition(cls, from_state: str, to_state: str, trigger: str = None) -> None:
        """
        Validate state transition and raise StandardizedValidationError if invalid
        
        Args:
            from_state: Current state
            to_state: Desired state  
            trigger: Business trigger causing the transition
            
        Raises:
            StandardizedValidationError: If transition is invalid
        """
        # Validate states exist
        if not cls.is_valid_state(from_state):
            raise StandardizedValidationError(
                CampaignErrorMessages.TARGET_INVALID_STATE.format(state=from_state)
            )
            
        if not cls.is_valid_state(to_state):
            raise StandardizedValidationError(
                CampaignErrorMessages.TARGET_INVALID_STATE.format(state=to_state)
            )
        
        # Same state is always allowed (no-op)
        if from_state == to_state:
            return
            
        # Check if transition is allowed
        if not cls.can_transition(from_state, to_state):
            allowed = cls.get_allowed_transitions(from_state)
            raise StandardizedValidationError(
                CampaignErrorMessages.TARGET_TRANSITION_INVALID.format(
                    from_state=from_state,
                    to_state=to_state,
                    allowed_transitions=', '.join(allowed) if allowed else 'none'
                )
            )
        
        # Validate trigger if provided
        if trigger and not cls.is_valid_trigger(trigger, to_state):
            raise StandardizedValidationError(
                CampaignErrorMessages.TARGET_TRANSITION_INVALID_TRIGGER.format(
                    trigger=trigger,
                    from_state=from_state,
                    to_state=to_state
                )
            )
    
    @classmethod
    def is_valid_state(cls, state: str) -> bool:
        """Check if a state is valid"""
        return state in cls.STATES
    
    @classmethod
    def can_transition(cls, from_state: str, to_state: str) -> bool:
        """Check if transition from one state to another is allowed"""
        if not cls.is_valid_state(from_state) or not cls.is_valid_state(to_state):
            return False
            
        # Same state is always allowed (no-op)
        if from_state == to_state:
            return True
            
        return to_state in cls.VALID_TRANSITIONS.get(from_state, [])