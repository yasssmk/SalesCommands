# apps/sequence/sequences/chasing_sequence.py
from typing import Dict, List
from apps.activities.models import Activity
from apps.sequence.sequences.base_sequence import Sequence

class ChasingSequence(Sequence):
    """
    Simple chasing sequence class with static methods returning sequence configurations
    """
    
    @staticmethod
    def get_standard_sequence() -> Dict:
        """
        Returns the standard chasing sequence with both calls and emails
        """
        return {
            1: {'type': Activity.ActivityType.CALL, 'min_delay': 0, 'description': 'Initial Outreach Call'},
            2: {'type': Activity.ActivityType.EMAIL, 'min_delay': 1, 'description': 'Follow-up Email'},
            3: {'type': Activity.ActivityType.CALL, 'min_delay': 2, 'description': 'Second Call Attempt'},
            4: {'type': Activity.ActivityType.EMAIL, 'min_delay': 3, 'description': 'Value Proposition Email'},
            5: {'type': Activity.ActivityType.CALL, 'min_delay': 2, 'description': 'Third Call Attempt'},
            6: {'type': Activity.ActivityType.EMAIL, 'min_delay': 4, 'description': 'Case Study Email'},
            7: {'type': Activity.ActivityType.CALL, 'min_delay': 3, 'description': 'Fourth Call Attempt'},
            8: {'type': Activity.ActivityType.EMAIL, 'min_delay': 7, 'description': 'Last Opportunity Email'},
            9: {'type': Activity.ActivityType.CALL, 'min_delay': 3, 'description': 'Final Call'},
            10: {'type': Activity.ActivityType.EMAIL, 'min_delay': 7, 'description': 'Breakup Email'}
        }
    
    @staticmethod
    def get_sequence_without_phone() -> Dict:
        """
        Returns chasing sequence for contacts without valid phone (only emails)
        Spreads 5 email attempts over appropriate delays
        """
        return {
            1: {'type': Activity.ActivityType.EMAIL, 'min_delay': 0, 'description': 'Initial Email Outreach'},
            2: {'type': Activity.ActivityType.EMAIL, 'min_delay': 2, 'description': 'Follow-up Email'},
            3: {'type': Activity.ActivityType.EMAIL, 'min_delay': 4, 'description': 'Value Proposition Email'},
            4: {'type': Activity.ActivityType.EMAIL, 'min_delay': 7, 'description': 'Case Study Email'},
            5: {'type': Activity.ActivityType.EMAIL, 'min_delay': 10, 'description': 'Final Email Attempt'}
        }
    
    @staticmethod
    def get_sequence_without_email() -> Dict:
        """
        Returns chasing sequence for contacts without valid email
        Converts emails to LinkedIn messages, keeps calls
        """
        return {
            1: {'type': Activity.ActivityType.CALL, 'min_delay': 0, 'description': 'Initial Outreach Call'},
            2: {'type': Activity.ActivityType.LINKEDIN, 'min_delay': 1, 'description': 'LinkedIn Connection Request'},
            3: {'type': Activity.ActivityType.CALL, 'min_delay': 2, 'description': 'Second Call Attempt'},
            4: {'type': Activity.ActivityType.LINKEDIN, 'min_delay': 3, 'description': 'LinkedIn Value Proposition'},
            5: {'type': Activity.ActivityType.CALL, 'min_delay': 2, 'description': 'Third Call Attempt'},
            6: {'type': Activity.ActivityType.LINKEDIN, 'min_delay': 4, 'description': 'LinkedIn Case Study'},
            7: {'type': Activity.ActivityType.CALL, 'min_delay': 3, 'description': 'Fourth Call Attempt'},
            8: {'type': Activity.ActivityType.LINKEDIN, 'min_delay': 7, 'description': 'LinkedIn Final Message'},
            9: {'type': Activity.ActivityType.CALL, 'min_delay': 3, 'description': 'Final Call'},
            10: {'type': Activity.ActivityType.LINKEDIN, 'min_delay': 7, 'description': 'LinkedIn Farewell Message'}
        }
    
    @staticmethod
    def get_sequence_phone_only() -> Dict:
        """
        Returns chasing sequence for contacts with only phone (no email/LinkedIn)
        5 call attempts with appropriate spacing
        """
        return {
            1: {'type': Activity.ActivityType.CALL, 'min_delay': 0, 'description': 'Initial Outreach Call'},
            2: {'type': Activity.ActivityType.CALL, 'min_delay': 2, 'description': 'Follow-up Call'},
            3: {'type': Activity.ActivityType.CALL, 'min_delay': 4, 'description': 'Third Call Attempt'},
            4: {'type': Activity.ActivityType.CALL, 'min_delay': 7, 'description': 'Fourth Call Attempt'},
            5: {'type': Activity.ActivityType.CALL, 'min_delay': 10, 'description': 'Final Call Attempt'}
        }