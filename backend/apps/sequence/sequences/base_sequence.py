# apps/sequence/sequences/base_sequence.py
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from apps.activities.models import Activity


class Sequence(ABC):
    """
    Abstract base class for all sequence types.
    Defines the interface and common functionality for sequences.
    """
    
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
    def get_sequence_for_channels(cls, has_phone: bool, has_email: bool, has_linkedin: bool) -> Dict:
        """
        Returns the appropriate sequence based on available channels
        This shared method simplifies selection logic across all sequence types
        """
        if has_phone and has_email:
            return cls.get_standard_sequence()
        elif not has_phone and has_email:
            return cls.get_sequence_without_phone()
        elif has_phone and not has_email and has_linkedin:
            return cls.get_sequence_without_email()
        elif has_phone and not (has_email or has_linkedin):
            return cls.get_sequence_phone_only()
        else:
            # Fallback to email-only if available, otherwise standard
            return cls.get_sequence_without_phone() if has_email else cls.get_standard_sequence()
    
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