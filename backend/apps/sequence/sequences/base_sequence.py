# apps/sequence/sequences/base_sequence.py
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from apps.activities.models import Activity


class Sequence(ABC):
    """
    Abstract base class for all sequence types.
    Defines the interface and common functionality for sequences.
    """
    
    # ===== SEQUENCE VARIANT CONSTANTS =====
    class SequenceVariant:
        """Constants for sequence variants - standardized across all sequence types"""
        STANDARD = 'standard'
        WITHOUT_PHONE = 'without_phone'
        WITHOUT_EMAIL = 'without_email'
        PHONE_ONLY = 'phone_only'
        
        @classmethod
        def get_choices(cls):
            """Return choices for Django field"""
            return [
                (cls.STANDARD, 'Standard (All Channels)'),
                (cls.WITHOUT_PHONE, 'Without Phone'),
                (cls.WITHOUT_EMAIL, 'Without Email'),
                (cls.PHONE_ONLY, 'Phone Only'),
            ]
        
        @classmethod
        def get_display_name(cls, variant):
            """Get human-readable display name for variant"""
            variant_names = {
                cls.STANDARD: 'Standard (All Channels)',
                cls.WITHOUT_PHONE: 'Without Phone',
                cls.WITHOUT_EMAIL: 'Without Email',
                cls.PHONE_ONLY: 'Phone Only',
            }
            return variant_names.get(variant, variant)
    
    @classmethod
    @abstractmethod
    def get_standard_sequence(cls) -> Dict:
        """
        Returns the standard sequence with all available channels
        Must be implemented by subclasses
        """
        pass
        
    @classmethod
    @abstractmethod
    def get_sequence_without_phone(cls) -> Dict:
        """
        Returns sequence for contacts without valid phone (only emails/LinkedIn)
        Must be implemented by subclasses
        """
        pass
        
    @classmethod
    @abstractmethod
    def get_sequence_without_email(cls) -> Dict:
        """
        Returns sequence for contacts without valid email
        Must be implemented by subclasses
        """
        pass
        
    @classmethod
    @abstractmethod
    def get_sequence_phone_only(cls) -> Dict:
        """
        Returns sequence for contacts with only phone (no email/LinkedIn)
        Must be implemented by subclasses
        """
        pass
    
    @classmethod
    def get_sequence_for_channels(cls, has_phone: bool, has_email: bool, has_linkedin: bool) -> tuple[Dict, str]:
        """
        Returns the appropriate sequence AND variant name based on available channels
        
        Args:
            has_phone: Whether contact has valid phone
            has_email: Whether contact has valid email
            has_linkedin: Whether contact has LinkedIn
            
        Returns:
            tuple: (sequence_dict, variant_name)
        """
        if has_phone and has_email:
            return cls.get_standard_sequence(), cls.SequenceVariant.STANDARD
        elif not has_phone and has_email:
            return cls.get_sequence_without_phone(), cls.SequenceVariant.WITHOUT_PHONE
        elif has_phone and not has_email and has_linkedin:
            return cls.get_sequence_without_email(), cls.SequenceVariant.WITHOUT_EMAIL
        elif has_phone and not (has_email or has_linkedin):
            return cls.get_sequence_phone_only(), cls.SequenceVariant.PHONE_ONLY
        else:
            # Fallback to email-only if available, otherwise standard
            if has_email:
                return cls.get_sequence_without_phone(), cls.SequenceVariant.WITHOUT_PHONE
            else:
                return cls.get_standard_sequence(), cls.SequenceVariant.STANDARD
    
    @classmethod
    def get_sequence_by_variant(cls, variant: str) -> Dict:
        """
        Get sequence by variant name - useful for reconstruction and testing
        
        Args:
            variant: Variant name from SequenceVariant constants
            
        Returns:
            Dict: Sequence configuration
        """
        variant_methods = {
            cls.SequenceVariant.STANDARD: cls.get_standard_sequence,
            cls.SequenceVariant.WITHOUT_PHONE: cls.get_sequence_without_phone,
            cls.SequenceVariant.WITHOUT_EMAIL: cls.get_sequence_without_email,
            cls.SequenceVariant.PHONE_ONLY: cls.get_sequence_phone_only,
        }
        
        method = variant_methods.get(variant, cls.get_standard_sequence)
        return method()
    
    @classmethod
    def get_sequence_name(cls) -> str:
        """
        Get the display name for this sequence type
        Should be implemented by subclasses, fallback to class name
        """
        return cls.__name__.replace('Sequence', '')
        
    @classmethod
    def validate_sequence(cls, sequence_dict: Dict) -> bool:
        """
        Validates a sequence dictionary to ensure it has the correct format
        Useful for debugging and ensuring sequence integrity
        """
        if not sequence_dict:
            return False
                     
        # Check required fields in each step
        for step_num, step_config in sequence_dict.items():
            if not isinstance(step_num, int) or step_num < 1:
                return False
                             
            required_fields = ['type', 'min_delay', 'description']
            if not all(field in step_config for field in required_fields):
                return False
                             
            # Ensure activity type is valid
            if step_config['type'] not in [choice[0] for choice in Activity.ActivityType.choices]:
                return False
                         
        return True