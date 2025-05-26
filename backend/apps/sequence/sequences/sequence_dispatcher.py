# apps/sequence/sequences/sequence_dispatcher.py
from typing import Dict, Optional

class SequenceDisptacher:
    """
    Helper for getting the appropriate sequence based on campaign type and available channels
    """
    
    # Sequence type constants
    CHASING = 'CHASING'
    RENEWAL = 'RENEWAL'
    FOLLOW_UP = 'FOLLOW_UP'
    
    # Sequence type choices for Campaign model
    SEQUENCE_CHOICES = [
        (CHASING, 'Chasing'),
        (RENEWAL, 'Contract Renewal'),
        (FOLLOW_UP, 'Opportunity Follow-up'),
    ]
    
    @classmethod
    def get_sequence(cls, sequence_type: str, has_phone: bool, has_email: bool, has_linkedin: bool) -> Dict:
        """
        Get the appropriate sequence based on sequence type and available channels
        
        Args:
            sequence_type: The type of sequence (from SEQUENCE_CHOICES)
            has_phone: Whether the contact has a valid phone number
            has_email: Whether the contact has a valid email address
            has_linkedin: Whether the contact has a LinkedIn profile
            
        Returns:
            Dictionary with sequence steps
        """
        # Determine channel configuration
        channel_config = 'standard'
        if not has_phone and has_email:
            channel_config = 'without_phone'
        elif has_phone and not has_email and has_linkedin:
            channel_config = 'without_email'
        elif has_phone and not (has_email or has_linkedin):
            channel_config = 'phone_only'
        
        # Call the appropriate sequence handler based on sequence type
        if sequence_type == cls.CHASING:
            from apps.sequence.sequences.chasing_sequence import ChasingSequence
            
            if channel_config == 'standard':
                return ChasingSequence.get_standard_sequence()
            elif channel_config == 'without_phone':
                return ChasingSequence.get_sequence_without_phone()
            elif channel_config == 'without_email':
                return ChasingSequence.get_sequence_without_email()
            elif channel_config == 'phone_only':
                return ChasingSequence.get_sequence_phone_only()
                

        
        # Default fallback
        from apps.sequence.sequences.chasing_sequence import ChasingSequence
        return ChasingSequence.get_standard_sequence()