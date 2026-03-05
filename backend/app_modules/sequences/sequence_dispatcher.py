# app_modules/sequences/sequence_dispatcher.py
"""
Sequence dispatcher — routes a campaign sequence_type to the correct sequence class.

Ported from apps/sequence/sequences/sequence_dispatcher.py.
No dependency on apps/.

Usage:
    sequence_dict, variant = SequenceDispatcher.get_sequence_with_variant(
        sequence_type='OUTBOUND',
        has_phone=True,
        has_email=True,
        has_linkedin=False,
    )
"""

from typing import Dict, Optional, Tuple, Type

from .base_sequence import Sequence
from .outbound_sequence import OutboundSequence
from .targeted_sequence import TargetedSequence
from .renewal_sequence import RenewalSequence


class SequenceDispatcher:
    """
    Central router for campaign sequence types.

    Sequence types:
        OUTBOUND  — cold prospecting (active)
        TARGETED  — warm / engaged contacts (active)
        RENEWAL   — contract renewal (coming soon — logic ready, UI hidden)
    """

    # =========================================================================
    # SEQUENCE TYPE CONSTANTS
    # =========================================================================

    OUTBOUND = 'OUTBOUND'
    TARGETED = 'TARGETED'
    RENEWAL  = 'RENEWAL'

    # Choices exposed to the Campaign model and serializers.
    # RENEWAL is intentionally excluded until the feature is released in the UI.
    SEQUENCE_CHOICES = [
        (OUTBOUND, 'Outbound'),
        (TARGETED, 'Targeted'),
        # (RENEWAL, 'Renewal'),  # coming soon
    ]

    # Full internal map — includes RENEWAL so services can use it programmatically.
    SEQUENCE_CLASS_MAP: Dict[str, Type[Sequence]] = {
        OUTBOUND: OutboundSequence,
        TARGETED: TargetedSequence,
        RENEWAL:  RenewalSequence,
    }

    # =========================================================================
    # PRIMARY METHOD
    # =========================================================================

    @classmethod
    def get_sequence_with_variant(
        cls,
        sequence_type: str,
        has_phone: bool,
        has_email: bool,
        has_linkedin: bool,
    ) -> Tuple[Dict, str]:
        """
        Return (sequence_dict, variant_name) for the given type and channel flags.

        Raises:
            ValueError: if sequence_type is not in SEQUENCE_CLASS_MAP.
        """
        sequence_class = cls.get_sequence_class(sequence_type)

        if sequence_class is None:
            raise ValueError(
                f"Unsupported sequence type: '{sequence_type}'. "
                f"Valid types: {list(cls.SEQUENCE_CLASS_MAP.keys())}"
            )

        return sequence_class.get_sequence_for_channels(has_phone, has_email, has_linkedin)

    # =========================================================================
    # LOOKUP HELPERS
    # =========================================================================

    @classmethod
    def get_sequence_class(cls, sequence_type: str) -> Optional[Type[Sequence]]:
        """Return the sequence class for a given type, or None if not found."""
        return cls.SEQUENCE_CLASS_MAP.get(sequence_type)

    @classmethod
    def get_sequence_display_name(cls, sequence_type: str) -> str:
        """Human-readable label for a sequence type."""
        sequence_class = cls.get_sequence_class(sequence_type)
        if sequence_class:
            return sequence_class.get_sequence_name()
        return sequence_type

    @classmethod
    def get_variant_display_name(cls, sequence_type: str, variant: str) -> str:
        """Human-readable label for a sequence variant."""
        sequence_class = cls.get_sequence_class(sequence_type)
        if sequence_class:
            return Sequence.SequenceVariant.get_display_name(variant)
        return variant

    # =========================================================================
    # LEGACY COMPATIBILITY
    # =========================================================================

    @classmethod
    def get_sequence(
        cls,
        sequence_type: str,
        has_phone: bool,
        has_email: bool,
        has_linkedin: bool,
    ) -> Dict:
        """
        Legacy method — returns sequence dict only (no variant).
        Kept for backward compatibility with existing services during migration.
        Prefer get_sequence_with_variant() for all new code.
        """
        sequence_dict, _ = cls.get_sequence_with_variant(
            sequence_type, has_phone, has_email, has_linkedin
        )
        return sequence_dict