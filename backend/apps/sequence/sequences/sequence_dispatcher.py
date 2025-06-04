# apps/sequence/sequences/sequence_dispatcher.py
from typing import Dict, Type
from .base_sequence import Sequence
from .chasing_sequence import ChasingSequence
from .renewal_sequence import RenewalSequence


class SequenceDispatcher:
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
    
    # Mapping of sequence types to their implementing classes
    SEQUENCE_CLASS_MAP = {
        CHASING: ChasingSequence,
        RENEWAL: RenewalSequence,
        # FOLLOW_UP: FollowUpSequence,  # To be implemented
    }
    
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
        # Get the appropriate sequence class
        sequence_class = cls.SEQUENCE_CLASS_MAP.get(sequence_type, ChasingSequence)
        
        # Use the common method from the base class to select the right sequence
        return sequence_class.get_sequence_for_channels(has_phone, has_email, has_linkedin)
    
    @classmethod
    def register_sequence_class(cls, sequence_type: str, sequence_class: Type[Sequence]) -> None:
        """
        Register a new sequence class for a given type
        This allows dynamic extension of available sequences
        
        Args:
            sequence_type: The sequence type identifier
            sequence_class: The sequence class to use for this type
        """
        cls.SEQUENCE_CLASS_MAP[sequence_type] = sequence_class


# # apps/sequence/sequences/sequence_dispatcher.py
# from typing import Dict, Optional

# class SequenceDisptacher:
#     """
#     Helper for getting the appropriate sequence based on campaign type and available channels
#     """
    
#     # Sequence type constants
#     CHASING = 'CHASING'
#     RENEWAL = 'RENEWAL'
#     FOLLOW_UP = 'FOLLOW_UP'
    
#     # Sequence type choices for Campaign model
#     SEQUENCE_CHOICES = [
#         (CHASING, 'Chasing'),
#         (RENEWAL, 'Contract Renewal'),
#         (FOLLOW_UP, 'Opportunity Follow-up'),
#     ]
    
#     @classmethod
#     def get_sequence(cls, sequence_type: str, has_phone: bool, has_email: bool, has_linkedin: bool) -> Dict:
#         """
#         Get the appropriate sequence based on sequence type and available channels
        
#         Args:
#             sequence_type: The type of sequence (from SEQUENCE_CHOICES)
#             has_phone: Whether the contact has a valid phone number
#             has_email: Whether the contact has a valid email address
#             has_linkedin: Whether the contact has a LinkedIn profile
            
#         Returns:
#             Dictionary with sequence steps
#         """
#         # Determine channel configuration
#         channel_config = 'standard'
#         if not has_phone and has_email:
#             channel_config = 'without_phone'
#         elif has_phone and not has_email and has_linkedin:
#             channel_config = 'without_email'
#         elif has_phone and not (has_email or has_linkedin):
#             channel_config = 'phone_only'
        
#         # Call the appropriate sequence handler based on sequence type
#         if sequence_type == cls.CHASING:
#             from apps.sequence.sequences.chasing_sequence import ChasingSequence
            
#             if channel_config == 'standard':
#                 return ChasingSequence.get_standard_sequence()
#             elif channel_config == 'without_phone':
#                 return ChasingSequence.get_sequence_without_phone()
#             elif channel_config == 'without_email':
#                 return ChasingSequence.get_sequence_without_email()
#             elif channel_config == 'phone_only':
#                 return ChasingSequence.get_sequence_phone_only()
                

        
#         # Default fallback
#         from apps.sequence.sequences.chasing_sequence import ChasingSequence
#         return ChasingSequence.get_standard_sequence()