# apps/sequence/sequences/sequence_dispatcher.py
from typing import Dict, Type, Optional, Tuple
from .base_sequence import Sequence
from .chasing_sequence import ChasingSequence
from .renewal_sequence import RenewalSequence
from .follow_up_sequence import FollowUpSequence  # Assuming this is implemented


class SequenceDispatcher:
    """
    Helper for getting the appropriate sequence based on campaign type and available channels
    Enhanced to support sequence identification and variant tracking
    """
    
    # Sequence type constants
    CHASING = 'CHASING'
    RENEWAL = 'RENEWAL'
    FOLLOW_UP = 'FOLLOW_UP'
    
    # Sequence type choices for Campaign model
    SEQUENCE_CHOICES = [
        (CHASING, 'Chasing'),
        (RENEWAL, 'Contract Renewal'),
        (FOLLOW_UP, 'Follow-up'),
    ]
    
    # Mapping of sequence types to their implementing classes
    SEQUENCE_CLASS_MAP = {
        CHASING: ChasingSequence,
        RENEWAL: RenewalSequence,
        FOLLOW_UP: FollowUpSequence
    }
    
    @classmethod
    def get_sequence(cls, sequence_type: str, has_phone: bool, has_email: bool, has_linkedin: bool) -> Dict:
        """
        Get the appropriate sequence based on sequence type and available channels
        LEGACY METHOD - maintained for backward compatibility
        
        Args:
            sequence_type: The type of sequence (from SEQUENCE_CHOICES)
            has_phone: Whether the contact has a valid phone number
            has_email: Whether the contact has a valid email address
            has_linkedin: Whether the contact has a LinkedIn profile
            
        Returns:
            Dictionary with sequence steps (legacy format)
        """
        # Get the appropriate sequence class
        sequence_class = cls.SEQUENCE_CLASS_MAP.get(sequence_type, ChasingSequence)
        
        # Use the enhanced method but return only the sequence dict for backward compatibility
        sequence_dict, _ = sequence_class.get_sequence_for_channels(has_phone, has_email, has_linkedin)
        return sequence_dict
    
    @classmethod
    def get_sequence_class(cls, sequence_type: str) -> Optional[Type[Sequence]]:
        """
        Get the sequence class for a given sequence type
        
        Args:
            sequence_type: The type of sequence (from SEQUENCE_CHOICES)
            
        Returns:
            Sequence class or None if not found
        """
        return cls.SEQUENCE_CLASS_MAP.get(sequence_type)
    
    @classmethod
    def get_sequence_with_variant(cls, sequence_type: str, has_phone: bool, has_email: bool, has_linkedin: bool) -> Tuple[Dict, str]:
        """
        Get the appropriate sequence AND variant name based on sequence type and available channels
        NEW METHOD - returns enhanced information
        
        Args:
            sequence_type: The type of sequence (from SEQUENCE_CHOICES)
            has_phone: Whether the contact has a valid phone number
            has_email: Whether the contact has a valid email address
            has_linkedin: Whether the contact has a LinkedIn profile
            
        Returns:
            Tuple of (sequence_dict, variant_name)
            
        Raises:
            ValueError: If sequence_type is not supported
        """
        # Get the appropriate sequence class
        sequence_class = cls.get_sequence_class(sequence_type)
        
        if not sequence_class:
            raise ValueError(f"Unsupported sequence type: {sequence_type}")
        
        # Use the enhanced method that returns both sequence and variant
        return sequence_class.get_sequence_for_channels(has_phone, has_email, has_linkedin)
    
    @classmethod
    def get_sequence_display_name(cls, sequence_type: str) -> str:
        """
        Get the human-readable display name for a sequence type
        
        Args:
            sequence_type: The sequence type identifier
            
        Returns:
            Display name or the sequence_type itself if not found
        """
        for choice_tuple in cls.SEQUENCE_CHOICES:
            if choice_tuple[0] == sequence_type:
                return choice_tuple[1]
        return sequence_type
    
    @classmethod
    def get_variant_display_name(cls, sequence_type: str, variant: str) -> str:
        """
        Get the human-readable display name for a sequence variant
        
        Args:
            sequence_type: The sequence type identifier
            variant: The variant identifier
            
        Returns:
            Display name for the variant
        """
        sequence_class = cls.get_sequence_class(sequence_type)
        
        if sequence_class and hasattr(sequence_class, 'SequenceVariant'):
            return sequence_class.SequenceVariant.get_display_name(variant)
        
        # Fallback to base Sequence class
        try:
            from .base_sequence import Sequence
            return Sequence.SequenceVariant.get_display_name(variant)
        except (ImportError, AttributeError):
            # Ultimate fallback
            return variant.replace('_', ' ').title()
    
    @classmethod
    def validate_sequence_type(cls, sequence_type: str) -> bool:
        """
        Validate if a sequence type is supported
        
        Args:
            sequence_type: The sequence type to validate
            
        Returns:
            True if supported, False otherwise
        """
        return sequence_type in cls.SEQUENCE_CLASS_MAP
    
    @classmethod
    def get_available_sequence_types(cls) -> list:
        """
        Get list of all available sequence types
        
        Returns:
            List of available sequence type identifiers
        """
        return list(cls.SEQUENCE_CLASS_MAP.keys())
    
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
        
        # Also add to choices if not already present
        choice_exists = any(choice[0] == sequence_type for choice in cls.SEQUENCE_CHOICES)
        if not choice_exists:
            display_name = getattr(sequence_class, 'get_sequence_name', lambda: sequence_type.title())()
            cls.SEQUENCE_CHOICES.append((sequence_type, display_name))