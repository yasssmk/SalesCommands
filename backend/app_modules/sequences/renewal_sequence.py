# app_modules/sequences/renewal_sequence.py
"""
Renewal sequence — contract renewal outreach.

Formerly known as RenewalSequence in apps/sequence/sequences/renewal_sequence.py.
Ported to app_modules with no dependency on apps/.

Use case: re-engaging existing clients whose contract is approaching expiration.
Lighter cadence than Outbound — relationship already established.

Status: COMING SOON — sequence logic is complete but this type is not yet
exposed in the UI or SequenceDispatcher choices for end users.
"""

from typing import Dict
from app_modules.activities.constants import ActivityType
from .base_sequence import Sequence


class RenewalSequence(Sequence):
    """
    Contract renewal sequence.

    Standard variant: 5 steps, email-led with follow-up calls.
    Shorter and more respectful than Outbound — client relationship exists.
    """

    @classmethod
    def get_sequence_name(cls) -> str:
        return "Renewal"

    # =========================================================================
    # STANDARD — phone + email available
    # =========================================================================

    @classmethod
    def get_standard_sequence(cls) -> Dict:
        """
        5-step renewal sequence opening with email, backed by calls.
        Covers ~2–3 weeks of follow-up.
        """
        return {
            1: {'type': ActivityType.EMAIL, 'min_delay': 0,  'description': 'Renewal Notification Email'},
            2: {'type': ActivityType.CALL,  'min_delay': 3,  'description': 'Renewal Follow-up Call'},
            3: {'type': ActivityType.EMAIL, 'min_delay': 5,  'description': 'Renewal Benefits Email'},
            4: {'type': ActivityType.CALL,  'min_delay': 5,  'description': 'Final Renewal Call'},
            5: {'type': ActivityType.EMAIL, 'min_delay': 2,  'description': 'Last Chance Email'},
        }

    # =========================================================================
    # WITHOUT PHONE — email only
    # =========================================================================

    @classmethod
    def get_sequence_without_phone(cls) -> Dict:
        """
        4-step email-only renewal sequence.
        """
        return {
            1: {'type': ActivityType.EMAIL, 'min_delay': 0,  'description': 'Renewal Notification Email'},
            2: {'type': ActivityType.EMAIL, 'min_delay': 3,  'description': 'Renewal Follow-up Email'},
            3: {'type': ActivityType.EMAIL, 'min_delay': 5,  'description': 'Renewal Benefits Email'},
            4: {'type': ActivityType.EMAIL, 'min_delay': 7,  'description': 'Final Reminder Email'},
        }

    # =========================================================================
    # WITHOUT EMAIL — phone only
    # =========================================================================

    @classmethod
    def get_sequence_without_email(cls) -> Dict:
        """
        3-step call-only renewal sequence for contacts without email.
        """
        return {
            1: {'type': ActivityType.CALL, 'min_delay': 0,  'description': 'Renewal Notification Call'},
            2: {'type': ActivityType.CALL, 'min_delay': 5,  'description': 'Renewal Follow-up Call'},
            3: {'type': ActivityType.CALL, 'min_delay': 5,  'description': 'Final Renewal Call'},
        }

    # =========================================================================
    # PHONE ONLY — same as without_email for renewals
    # =========================================================================

    @classmethod
    def get_sequence_phone_only(cls) -> Dict:
        """
        Same as without_email — phone-only contacts get the call sequence.
        """
        return cls.get_sequence_without_email()