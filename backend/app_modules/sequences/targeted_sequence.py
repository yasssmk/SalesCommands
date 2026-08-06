# app_modules/sequences/targeted_sequence.py
"""
Targeted sequence — waiting for a response / warm follow-up.

Formerly known as FollowUpSequence in apps/sequence/sequences/follow_up_sequence.py.
Ported to app_modules with no dependency on apps/.

Use cases:
- Waiting for client feedback on a proposal
- Following up on promised documents or information
- Checking status after meeting commitments
- Clarifying timeline delays

Lighter and more respectful cadence than Outbound — contact has already engaged.
"""

from typing import Dict
from app_modules.activities.constants import ActivityType
from .base_sequence import Sequence


class TargetedSequence(Sequence):
    """
    Targeted follow-up sequence for warm or engaged contacts.

    Standard variant: 5 steps over ~3 weeks with respectful spacing.
    Email-led to avoid pressure, backed by check-in calls.
    """

    PREFIX = "TGT"
    # An account is in at most one Targeted campaign, so the campaign name is
    # redundant in the title and is omitted.
    INCLUDE_CAMPAIGN_NAME = False

    @classmethod
    def get_sequence_name(cls) -> str:
        return "Targeted"

    # =========================================================================
    # STANDARD — phone + email available
    # =========================================================================

    @classmethod
    def get_standard_sequence(cls) -> Dict:
        """
        5-step sequence opening with a gentle email, then alternating
        check-in calls and clarification emails over ~4 weeks.
        """
        return {
            1: {'type': ActivityType.EMAIL, 'min_delay': 0,  'description': 'Gentle Follow-up Email'},
            2: {'type': ActivityType.CALL,  'min_delay': 3,  'description': 'Status Check-in Call'},
            3: {'type': ActivityType.EMAIL, 'min_delay': 7,  'description': 'Timeline Clarification Email'},
            4: {'type': ActivityType.CALL,  'min_delay': 7,  'description': 'Priority Confirmation Call'},
            5: {'type': ActivityType.EMAIL, 'min_delay': 10, 'description': 'Final Status Request Email'},
        }

    # =========================================================================
    # WITHOUT PHONE — email only
    # =========================================================================

    @classmethod
    def get_sequence_without_phone(cls) -> Dict:
        """
        5-step email-only sequence for contacts without a valid phone number.
        Wider spacing to avoid pressure.
        """
        return {
            1: {'type': ActivityType.EMAIL, 'min_delay': 0,  'description': 'Gentle Follow-up Email'},
            2: {'type': ActivityType.EMAIL, 'min_delay': 4,  'description': 'Status Update Request'},
            3: {'type': ActivityType.EMAIL, 'min_delay': 7,  'description': 'Timeline Clarification Email'},
            4: {'type': ActivityType.EMAIL, 'min_delay': 10, 'description': 'Priority Check Email'},
            5: {'type': ActivityType.EMAIL, 'min_delay': 14, 'description': 'Final Status Request Email'},
        }

    # =========================================================================
    # WITHOUT EMAIL — phone + LinkedIn
    # =========================================================================

    @classmethod
    def get_sequence_without_email(cls) -> Dict:
        """
        4-step sequence using calls and LinkedIn for contacts without email.
        """
        return {
            1: {'type': ActivityType.CALL,    'min_delay': 0,  'description': 'Status Check-in Call'},
            2: {'type': ActivityType.LINKEDIN, 'min_delay': 3,  'description': 'LinkedIn Follow-up Message'},
            3: {'type': ActivityType.CALL,    'min_delay': 7,  'description': 'Priority Confirmation Call'},
            4: {'type': ActivityType.LINKEDIN, 'min_delay': 10, 'description': 'LinkedIn Final Message'},
        }

    # =========================================================================
    # PHONE ONLY — no email, no LinkedIn
    # =========================================================================

    @classmethod
    def get_sequence_phone_only(cls) -> Dict:
        """
        3-step call-only sequence. Minimal — targeted contacts should have
        at least one digital channel available.
        """
        return {
            1: {'type': ActivityType.CALL, 'min_delay': 0,  'description': 'Status Check-in Call'},
            2: {'type': ActivityType.CALL, 'min_delay': 7,  'description': 'Priority Confirmation Call'},
            3: {'type': ActivityType.CALL, 'min_delay': 10, 'description': 'Final Status Call'},
        }

    # =========================================================================
    # LINKEDIN ONLY — no phone, no email
    # =========================================================================

    @classmethod
    def get_sequence_linkedin_only(cls) -> Dict:
        """
        5-step LinkedIn-only sequence for contacts reachable only on LinkedIn.
        Mirrors the WITHOUT_PHONE cadence (same step count and delays), with
        every step sent on LinkedIn.
        """
        return {
            1: {'type': ActivityType.LINKEDIN, 'min_delay': 0,  'description': 'LinkedIn Message'},
            2: {'type': ActivityType.LINKEDIN, 'min_delay': 4,  'description': 'LinkedIn Follow-up'},
            3: {'type': ActivityType.LINKEDIN, 'min_delay': 7,  'description': 'LinkedIn Timeline Clarification'},
            4: {'type': ActivityType.LINKEDIN, 'min_delay': 10, 'description': 'LinkedIn Priority Message'},
            5: {'type': ActivityType.LINKEDIN, 'min_delay': 14, 'description': 'LinkedIn Final Message'},
        }