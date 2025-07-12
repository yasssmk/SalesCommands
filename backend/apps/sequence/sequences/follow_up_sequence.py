# apps/sequence/sequences/follow_up_sequence.py
from typing import Dict
from apps.activities.models import Activity
from .base_sequence import Sequence


class FollowUpSequence(Sequence):
    """
    Follow-up sequence implementation for situations where we're waiting for a response
    that hasn't been received. More respectful and collaborative than chasing sequence.
    
    Use cases:
    - Waiting for client feedback on proposal
    - Following up on promised documents/information
    - Checking status after meeting commitments
    - Clarifying timeline delays
    """

    @classmethod
    def get_sequence_name(cls) -> str:
        """Get the display name for this sequence type"""
        return "Follow-up"
    
    @classmethod
    def get_standard_sequence(cls) -> Dict:
        """
        Returns the standard follow-up sequence with both calls and emails
        5 steps over ~3 weeks with respectful timing
        """
        return {
            1: {'type': Activity.ActivityType.EMAIL, 'min_delay': 0, 'description': 'Gentle Follow-up Email'},
            2: {'type': Activity.ActivityType.CALL, 'min_delay': 3, 'description': 'Status Check-in Call'},
            3: {'type': Activity.ActivityType.EMAIL, 'min_delay': 7, 'description': 'Timeline Clarification Email'},
            4: {'type': Activity.ActivityType.CALL, 'min_delay': 7, 'description': 'Priority Confirmation Call'},
            5: {'type': Activity.ActivityType.EMAIL, 'min_delay': 10, 'description': 'Final Status Request Email'}
        }
    
    @classmethod
    def get_sequence_without_phone(cls) -> Dict:
        """
        Returns follow-up sequence for contacts without valid phone (only emails)
        5 email touchpoints with appropriate spacing
        """
        return {
            1: {'type': Activity.ActivityType.EMAIL, 'min_delay': 0, 'description': 'Gentle Follow-up Email'},
            2: {'type': Activity.ActivityType.EMAIL, 'min_delay': 4, 'description': 'Status Check-in Email'},
            3: {'type': Activity.ActivityType.EMAIL, 'min_delay': 7, 'description': 'Timeline Clarification Email'},
            4: {'type': Activity.ActivityType.EMAIL, 'min_delay': 10, 'description': 'Priority Confirmation Email'},
            5: {'type': Activity.ActivityType.EMAIL, 'min_delay': 14, 'description': 'Final Status Request Email'}
        }
    
    @classmethod
    def get_sequence_without_email(cls) -> Dict:
        """
        Returns follow-up sequence for contacts without valid email
        Uses calls and LinkedIn messages
        """
        return {
            1: {'type': Activity.ActivityType.CALL, 'min_delay': 0, 'description': 'Gentle Follow-up Call'},
            2: {'type': Activity.ActivityType.LINKEDIN, 'min_delay': 3, 'description': 'LinkedIn Status Check-in'},
            3: {'type': Activity.ActivityType.CALL, 'min_delay': 7, 'description': 'Timeline Clarification Call'},
            4: {'type': Activity.ActivityType.LINKEDIN, 'min_delay': 7, 'description': 'LinkedIn Priority Message'},
            5: {'type': Activity.ActivityType.CALL, 'min_delay': 10, 'description': 'Final Status Call'}
        }
    
    @classmethod
    def get_sequence_phone_only(cls) -> Dict:
        """
        Returns follow-up sequence for contacts with only phone
        5 call attempts with respectful spacing
        """
        return {
            1: {'type': Activity.ActivityType.CALL, 'min_delay': 0, 'description': 'Gentle Follow-up Call'},
            2: {'type': Activity.ActivityType.CALL, 'min_delay': 4, 'description': 'Status Check-in Call'},
            3: {'type': Activity.ActivityType.CALL, 'min_delay': 7, 'description': 'Timeline Clarification Call'},
            4: {'type': Activity.ActivityType.CALL, 'min_delay': 10, 'description': 'Priority Confirmation Call'},
            5: {'type': Activity.ActivityType.CALL, 'min_delay': 14, 'description': 'Final Status Call'}
        }
    
    @classmethod
    def get_sequence_linkedin_only(cls) -> Dict:
        """
        Returns follow-up sequence for contacts with only LinkedIn
        5 LinkedIn messages with professional spacing
        """
        return {
            1: {'type': Activity.ActivityType.LINKEDIN, 'min_delay': 0, 'description': 'LinkedIn Follow-up Message'},
            2: {'type': Activity.ActivityType.LINKEDIN, 'min_delay': 5, 'description': 'LinkedIn Status Check-in'},
            3: {'type': Activity.ActivityType.LINKEDIN, 'min_delay': 8, 'description': 'LinkedIn Timeline Clarification'},
            4: {'type': Activity.ActivityType.LINKEDIN, 'min_delay': 12, 'description': 'LinkedIn Priority Message'},
            5: {'type': Activity.ActivityType.LINKEDIN, 'min_delay': 15, 'description': 'LinkedIn Final Request'}
        }