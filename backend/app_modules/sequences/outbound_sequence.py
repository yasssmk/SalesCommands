# app_modules/sequences/outbound_sequence.py
"""
Outbound sequence — cold prospecting / new business.

Formerly known as ChasingSequence in apps/sequence/sequences/chasing_sequence.py.
Ported to app_modules with no dependency on apps/.

Use case: reaching out to prospects who have not yet engaged.
Aggressive multi-channel cadence (call + email ± LinkedIn).
"""

from typing import Dict
from app_modules.activities.constants import ActivityType
from .base_sequence import Sequence


class OutboundSequence(Sequence):
    """
    Outbound prospecting sequence.

    Standard variant: 10 steps, alternating calls and emails over ~4 weeks.
    """

    @classmethod
    def get_sequence_name(cls) -> str:
        return "Outbound"

    # =========================================================================
    # STANDARD — phone + email available
    # =========================================================================

    @classmethod
    def get_standard_sequence(cls) -> Dict:
        """
        10-step sequence alternating calls and emails.
        Covers ~4 weeks of outreach with escalating urgency.
        """
        # return {
        #     1:  {'type': ActivityType.CALL,  'min_delay': 0,  'description': 'Initial Outreach Call'},
        #     2:  {'type': ActivityType.EMAIL, 'min_delay': 1,  'description': 'Follow-up Email'},
        #     3:  {'type': ActivityType.CALL,  'min_delay': 2,  'description': 'Second Call Attempt'},
        #     4:  {'type': ActivityType.EMAIL, 'min_delay': 3,  'description': 'Value Proposition Email'},
        #     5:  {'type': ActivityType.CALL,  'min_delay': 2,  'description': 'Third Call Attempt'},
        #     6:  {'type': ActivityType.EMAIL, 'min_delay': 4,  'description': 'Case Study Email'},
        #     7:  {'type': ActivityType.CALL,  'min_delay': 3,  'description': 'Fourth Call Attempt'},
        #     8:  {'type': ActivityType.EMAIL, 'min_delay': 7,  'description': 'Last Opportunity Email'},
        #     9:  {'type': ActivityType.CALL,  'min_delay': 3,  'description': 'Final Call'},
        #     10: {'type': ActivityType.EMAIL, 'min_delay': 7,  'description': 'Breakup Email'},
        # }

        #Sequence TEST

        return {
            1: {'type': ActivityType.CALL,    'min_delay': 0, 'description': '[TEST] Step 1 - Initial Call'},
            2: {'type': ActivityType.EMAIL,   'min_delay': 1, 'description': '[TEST] Step 2 - Follow-up Email'},
            3: {'type': ActivityType.CALL,    'min_delay': 1, 'description': '[TEST] Step 3 - Second Call'},
            4: {'type': ActivityType.EMAIL, 'min_delay': 1, 'description': '[TEST] Step 4 - Last Email'},
}

    # =========================================================================
    # WITHOUT PHONE — email only
    # =========================================================================

    @classmethod
    def get_sequence_without_phone(cls) -> Dict:
        """
        5-step email-only sequence for contacts without a valid phone number.
        """
        # return {
        #     1: {'type': ActivityType.EMAIL, 'min_delay': 0,  'description': 'Initial Email Outreach'},
        #     2: {'type': ActivityType.EMAIL, 'min_delay': 2,  'description': 'Follow-up Email'},
        #     3: {'type': ActivityType.EMAIL, 'min_delay': 4,  'description': 'Value Proposition Email'},
        #     4: {'type': ActivityType.EMAIL, 'min_delay': 7,  'description': 'Case Study Email'},
        #     5: {'type': ActivityType.EMAIL, 'min_delay': 10, 'description': 'Final Email Attempt'},
        # }
    
    # Test

        return {
            1: {'type': ActivityType.EMAIL, 'min_delay': 0,  'description': 'Initial Email Outreach'},
            2: {'type': ActivityType.EMAIL, 'min_delay': 1,  'description': 'Follow-up Email'},
            3: {'type': ActivityType.EMAIL, 'min_delay': 1,  'description': 'Value Proposition Email'},
        }

    # =========================================================================
    # WITHOUT EMAIL — phone + LinkedIn
    # =========================================================================

    @classmethod
    def get_sequence_without_email(cls) -> Dict:
        """
        10-step sequence replacing emails with LinkedIn messages.
        For contacts with phone and LinkedIn but no email address.
        """
        return {
            1:  {'type': ActivityType.CALL,     'min_delay': 0,  'description': 'Initial Outreach Call'},
            2:  {'type': ActivityType.LINKEDIN,  'min_delay': 1,  'description': 'LinkedIn Connection Request'},
            3:  {'type': ActivityType.CALL,     'min_delay': 2,  'description': 'Second Call Attempt'},
            4:  {'type': ActivityType.LINKEDIN,  'min_delay': 3,  'description': 'LinkedIn Value Proposition'},
            5:  {'type': ActivityType.CALL,     'min_delay': 2,  'description': 'Third Call Attempt'},
            6:  {'type': ActivityType.LINKEDIN,  'min_delay': 4,  'description': 'LinkedIn Case Study'},
            7:  {'type': ActivityType.CALL,     'min_delay': 3,  'description': 'Fourth Call Attempt'},
            8:  {'type': ActivityType.LINKEDIN,  'min_delay': 7,  'description': 'LinkedIn Final Message'},
            9:  {'type': ActivityType.CALL,     'min_delay': 3,  'description': 'Final Call'},
            10: {'type': ActivityType.LINKEDIN,  'min_delay': 7,  'description': 'LinkedIn Farewell Message'},
        }

    # =========================================================================
    # PHONE ONLY — no email, no LinkedIn
    # =========================================================================

    @classmethod
    def get_sequence_phone_only(cls) -> Dict:
        """
        5-step call-only sequence for contacts with phone only.
        """
        # return {
        #     1: {'type': ActivityType.CALL, 'min_delay': 0,  'description': 'Initial Outreach Call'},
        #     2: {'type': ActivityType.CALL, 'min_delay': 2,  'description': 'Follow-up Call'},
        #     3: {'type': ActivityType.CALL, 'min_delay': 4,  'description': 'Third Call Attempt'},
        #     4: {'type': ActivityType.CALL, 'min_delay': 7,  'description': 'Fourth Call Attempt'},
        #     5: {'type': ActivityType.CALL, 'min_delay': 10, 'description': 'Final Call Attempt'},
        # }
    
        # Test
        return {
            1: {'type': ActivityType.CALL,    'min_delay': 0, 'description': '[TEST] Step 1 - Initial Call'},
            2: {'type': ActivityType.CALL,   'min_delay': 1, 'description': '[TEST] Step 2 - Follow-up Email'},
            3: {'type': ActivityType.CALL,    'min_delay': 1, 'description': '[TEST] Step 3 - Second Call'},
            4: {'type': ActivityType.CALL, 'min_delay': 1, 'description': '[TEST] Step 4 - Last Email'},
        }