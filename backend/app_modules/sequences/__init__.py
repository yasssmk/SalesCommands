# app_modules/sequences/__init__.py
"""
Sequences module — campaign activity sequence engine.

Public API:
    SequenceDispatcher   — route sequence_type + channels → (dict, variant)
    OutboundSequence     — cold prospecting (OUTBOUND)
    TargetedSequence     — warm follow-up (TARGETED)
    RenewalSequence      — contract renewal (RENEWAL — coming soon)
    Sequence             — abstract base class for custom sequences
"""

from .base_sequence import Sequence
from .outbound_sequence import OutboundSequence
from .targeted_sequence import TargetedSequence
from .renewal_sequence import RenewalSequence
from .sequence_dispatcher import SequenceDispatcher

__all__ = [
    'Sequence',
    'OutboundSequence',
    'TargetedSequence',
    'RenewalSequence',
    'SequenceDispatcher',
]