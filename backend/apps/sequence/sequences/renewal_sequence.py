# apps/sequence/sequences/renewal_sequence.py
from typing import Dict
from apps.activities.models import Activity
from .base_sequence import Sequence


class RenewalSequence(Sequence):
    """
    Renewal sequence implementation for contract renewals
    Shows how easily new sequence types can be added
    """

    @classmethod
    def get_sequence_name(cls) -> str:
        """Get the display name for this sequence type"""
        return "Renewals"
    
    @classmethod
    def get_standard_sequence(cls) -> Dict:
        """
        Returns the standard renewal sequence with both calls and emails
        """
        return {
            1: {'type': Activity.ActivityType.EMAIL, 'min_delay': 0, 'description': 'Renewal Notification Email'},
            2: {'type': Activity.ActivityType.CALL, 'min_delay': 3, 'description': 'Renewal Follow-up Call'},
            3: {'type': Activity.ActivityType.EMAIL, 'min_delay': 5, 'description': 'Renewal Benefits Email'},
            4: {'type': Activity.ActivityType.CALL, 'min_delay': 5, 'description': 'Final Renewal Call'},
            5: {'type': Activity.ActivityType.EMAIL, 'min_delay': 2, 'description': 'Last Chance Email'}
        }
    
    @classmethod
    def get_sequence_without_phone(cls) -> Dict:
        """
        Returns renewal sequence for contacts without valid phone
        """
        return {
            1: {'type': Activity.ActivityType.EMAIL, 'min_delay': 0, 'description': 'Renewal Notification Email'},
            2: {'type': Activity.ActivityType.EMAIL, 'min_delay': 3, 'description': 'Renewal Follow-up Email'},
            3: {'type': Activity.ActivityType.EMAIL, 'min_delay': 5, 'description': 'Renewal Benefits Email'},
            4: {'type': Activity.ActivityType.EMAIL, 'min_delay': 7, 'description': 'Final Reminder Email'}
        }
    
    @classmethod
    def get_sequence_without_email(cls) -> Dict:
        """
        Returns renewal sequence for contacts without valid email
        """
        return {
            1: {'type': Activity.ActivityType.CALL, 'min_delay': 0, 'description': 'Renewal Notification Call'},
            2: {'type': Activity.ActivityType.CALL, 'min_delay': 5, 'description': 'Renewal Follow-up Call'},
            3: {'type': Activity.ActivityType.CALL, 'min_delay': 5, 'description': 'Final Renewal Call'}
        }
    
    @classmethod
    def get_sequence_phone_only(cls) -> Dict:
        """
        Returns renewal sequence for contacts with only phone
        """
        return cls.get_sequence_without_email()  # Same in this case