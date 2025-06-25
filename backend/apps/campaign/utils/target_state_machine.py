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
        'manual_stop': 'STOPPED',
        'campaign_activated': 'IN_PROGRESS',      # DRAFT/PAUSED → ACTIVE
        'campaign_resumed': 'IN_PROGRESS',        # PAUSED → ACTIVE  
        'campaign_paused': 'CALLBACK_PENDING',    # ACTIVE → PAUSED (optionnel)
        'campaign_reactivated': 'IN_PROGRESS'     # Générique pour réactivation
    }
    
    # Final states that cannot be changed
    FINAL_STATES = {'COMPLETED', 'STOPPED'}
    
    @classmethod
    def validate_transition(cls, from_state: str, to_state: str, trigger: str = None) -> None:
        """
        ✅ VERSION DEBUG avec logs détaillés
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
        
        print(f"✅ States are valid")
        
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
    
    @classmethod
    def get_allowed_transitions(cls, from_state: str) -> List[str]:
        """
        Get list of states that can be transitioned to from the given state
        
        Args:
            from_state: Current state to check transitions from
            
        Returns:
            List[str]: List of allowed destination states
        """
        if not cls.is_valid_state(from_state):
            return []
            
        # Simply return the list from VALID_TRANSITIONS - same logic as can_transition()
        return cls.VALID_TRANSITIONS.get(from_state, [])
    
    @classmethod
    def is_final_state(cls, state: str) -> bool:
        """
        Check if a state is a final state (no further transitions allowed)
        
        Args:
            state: State to check
            
        Returns:
            bool: True if state is final (COMPLETED or STOPPED)
        """
        return state in cls.FINAL_STATES
    
    @classmethod
    def is_valid_trigger(cls, trigger: str, to_state: str) -> bool:
        """
        Check if a business trigger is valid for transitioning to the given state
        
        Args:
            trigger: Business trigger causing the transition
            to_state: Target state for the transition
            
        Returns:
            bool: True if trigger is valid for the target state
        """
        if not trigger or not to_state:
            return True  # No trigger validation needed
            
        # Check if the trigger maps to the target state
        expected_state = cls.BUSINESS_TRIGGERS.get(trigger)
        return expected_state == to_state
    
    @classmethod
    def get_triggers_for_state(cls, to_state: str) -> List[str]:
        """
        Get all business triggers that can lead to the given state
        
        Args:
            to_state: Target state
            
        Returns:
            List[str]: List of triggers that can cause transition to this state
        """
        triggers = []
        for trigger, state in cls.BUSINESS_TRIGGERS.items():
            if state == to_state:
                triggers.append(trigger)
        return triggers
    
    @classmethod
    def get_state_info(cls, state: str) -> Dict:
        """
        Get comprehensive information about a state
        
        Args:
            state: State to get information about
            
        Returns:
            Dict: Complete state information
        """
        if not cls.is_valid_state(state):
            return {}
            
        return {
            'state': state,
            'description': cls.STATES.get(state, ''),
            'is_final': cls.is_final_state(state),
            'allowed_transitions': cls.get_allowed_transitions(state),
            'business_triggers': cls.get_triggers_for_state(state)
        }