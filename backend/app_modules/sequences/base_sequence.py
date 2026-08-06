# app_modules/sequences/base_sequence.py
"""
Abstract base class for all campaign sequence types.

A sequence defines the ordered set of activities to generate for a given
contact/account when a campaign is started. Each subclass implements the
4 channel variants required by the dispatcher.

Ported from apps/sequence/sequences/base_sequence.py.
No dependency on apps/ — uses app_modules.activities.constants directly.
"""

from abc import ABC, abstractmethod
from typing import Dict, Tuple


class Sequence(ABC):
    """
    Abstract base class for all sequence types.

    Subclasses must implement the four channel variants:
        - get_standard_sequence()       → phone + email available
        - get_sequence_without_phone()  → email only
        - get_sequence_without_email()  → phone (+ optional LinkedIn)
        - get_sequence_phone_only()     → phone only, no email/LinkedIn

    Each sequence step dict has the shape:
        {
            step_number (int): {
                'type': ActivityType value (str),
                'min_delay': int (days since previous step completion),
                'description': str,
            }
        }
    """

    # =========================================================================
    # TITLE PREFIX — short, distinctive code for this sequence's activities
    # =========================================================================

    # Each concrete sequence declares its own prefix (e.g. "OUT", "TGT"). The
    # base default is empty so the dispatch and coming-soon sequences that have
    # not declared one keep working.
    PREFIX: str = ""

    @classmethod
    def get_prefix(cls) -> str:
        """Short code prepended to this sequence's activity titles."""
        return cls.PREFIX

    # Whether the campaign name belongs in this sequence's activity titles.
    # True when an account can be in several campaigns of this kind (the name
    # disambiguates); False when the account is in at most one (name redundant).
    INCLUDE_CAMPAIGN_NAME: bool = True

    @classmethod
    def get_include_campaign_name(cls) -> bool:
        """Whether to include the campaign name in this sequence's titles."""
        return cls.INCLUDE_CAMPAIGN_NAME

    # =========================================================================
    # SEQUENCE VARIANT CONSTANTS
    # =========================================================================

    class SequenceVariant:
        """Standardized variant identifiers — shared across all sequence types."""

        STANDARD = 'STANDARD'
        WITHOUT_PHONE = 'WITHOUT_PHONE'
        WITHOUT_EMAIL = 'WITHOUT_EMAIL'
        PHONE_ONLY = 'PHONE_ONLY'
        LINKEDIN_ONLY = 'LINKEDIN_ONLY'

        @classmethod
        def get_choices(cls):
            """Return Django-compatible choices list."""
            return [
                (cls.STANDARD, 'Standard (All Channels)'),
                (cls.WITHOUT_PHONE, 'Without Phone'),
                (cls.WITHOUT_EMAIL, 'Without Email'),
                (cls.PHONE_ONLY, 'Phone Only'),
                (cls.LINKEDIN_ONLY, 'LinkedIn Only'),
            ]

        @classmethod
        def get_display_name(cls, variant: str) -> str:
            """Human-readable label for a given variant constant."""
            names = {
                cls.STANDARD: 'Standard (All Channels)',
                cls.WITHOUT_PHONE: 'Without Phone',
                cls.WITHOUT_EMAIL: 'Without Email',
                cls.PHONE_ONLY: 'Phone Only',
                cls.LINKEDIN_ONLY: 'LinkedIn Only',
            }
            return names.get(variant, variant)

    # =========================================================================
    # ABSTRACT INTERFACE — must be implemented by subclasses
    # =========================================================================

    @classmethod
    @abstractmethod
    def get_standard_sequence(cls) -> Dict:
        """Returns sequence when both phone and email are available."""
        pass

    @classmethod
    @abstractmethod
    def get_sequence_without_phone(cls) -> Dict:
        """Returns sequence when phone is unavailable (email only)."""
        pass

    @classmethod
    @abstractmethod
    def get_sequence_without_email(cls) -> Dict:
        """Returns sequence when email is unavailable (phone/LinkedIn)."""
        pass

    @classmethod
    @abstractmethod
    def get_sequence_phone_only(cls) -> Dict:
        """Returns sequence when only phone is available."""
        pass

    @classmethod
    @abstractmethod
    def get_sequence_linkedin_only(cls) -> Dict:
        """Returns sequence when only LinkedIn is available (no phone/email)."""
        pass

    @classmethod
    @abstractmethod
    def get_sequence_name(cls) -> str:
        """Human-readable display name for this sequence type."""
        pass

    # =========================================================================
    # CHANNEL ROUTING — shared logic, no override needed
    # =========================================================================

    @classmethod
    def get_sequence_for_channels(
        cls,
        has_phone: bool,
        has_email: bool,
        has_linkedin: bool,
    ) -> Tuple[Dict, str]:
        """
        Select the appropriate variant based on available contact channels.

        Returns:
            (sequence_dict, variant_name) tuple
        """
        if has_phone and has_email:
            return cls.get_standard_sequence(), cls.SequenceVariant.STANDARD

        if not has_phone and has_email:
            return cls.get_sequence_without_phone(), cls.SequenceVariant.WITHOUT_PHONE

        if has_phone and not has_email and has_linkedin:
            return cls.get_sequence_without_email(), cls.SequenceVariant.WITHOUT_EMAIL

        if has_phone and not has_email and not has_linkedin:
            return cls.get_sequence_phone_only(), cls.SequenceVariant.PHONE_ONLY

        if not has_phone and not has_email and has_linkedin:
            return cls.get_sequence_linkedin_only(), cls.SequenceVariant.LINKEDIN_ONLY

        # Fallback: email available → without_phone; otherwise standard
        if has_email:
            return cls.get_sequence_without_phone(), cls.SequenceVariant.WITHOUT_PHONE

        return cls.get_standard_sequence(), cls.SequenceVariant.STANDARD

    @classmethod
    def get_sequence_by_variant(cls, variant: str) -> Dict:
        """
        Retrieve a sequence dict directly by variant constant.
        Useful for reconstruction, testing, or admin preview.
        """
        variant_map = {
            cls.SequenceVariant.STANDARD: cls.get_standard_sequence,
            cls.SequenceVariant.WITHOUT_PHONE: cls.get_sequence_without_phone,
            cls.SequenceVariant.WITHOUT_EMAIL: cls.get_sequence_without_email,
            cls.SequenceVariant.PHONE_ONLY: cls.get_sequence_phone_only,
            cls.SequenceVariant.LINKEDIN_ONLY: cls.get_sequence_linkedin_only,
        }
        method = variant_map.get(variant, cls.get_standard_sequence)
        return method()

    # =========================================================================
    # VALIDATION UTILITY
    # =========================================================================

    @classmethod
    def validate_sequence(cls, sequence_dict: Dict) -> bool:
        """
        Validate that a sequence dict is well-formed.
        Each step must have: type (str), min_delay (int >= 0), description (str).
        """
        if not sequence_dict:
            return False

        from app_modules.activities.constants import ActivityType
        valid_types = [choice[0] for choice in ActivityType.choices]

        for step_num, step_config in sequence_dict.items():
            if not isinstance(step_num, int) or step_num < 1:
                return False

            required = {'type', 'min_delay', 'description'}
            if not required.issubset(step_config):
                return False

            if step_config['type'] not in valid_types:
                return False

            if not isinstance(step_config['min_delay'], int) or step_config['min_delay'] < 0:
                return False

        return True