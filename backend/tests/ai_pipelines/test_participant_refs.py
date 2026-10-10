# backend/tests/ai_pipelines/test_participant_refs.py
"""
Unit tests for services/participant_refs.py (Objection S3) and for the
participant references rendered in the transcript_signals context layer.

  * ordered_participants(activity): activity.contacts filtered on the
    activity's tenant AND account, ordered last_name, first_name, id --
    the SINGLE source of the P<n> numbering.
  * resolve_participant_ref(ref, activity): only a valid "P<n>" within
    that list resolves; anything else -> None (never guessed).
  * The context block prefixes each participant line with its reference.
"""

import pytest

from app_modules.ai_pipelines.prompts.transcript_signals.context import (
    build_context_layer,
)
from app_modules.ai_pipelines.services.participant_refs import (
    ordered_participants,
    resolve_participant_ref,
)

# Cross-account fixtures (tenant A, second account) -- re-used from the
# signals conftest, same re-export pattern as tests/ai_pipelines/conftest.py.
from tests.signals.conftest import (  # noqa: F401
    other_account,
    other_account_contact,
)


pytestmark = pytest.mark.django_db


# =============================================================================
# ordered_participants
# =============================================================================

class TestOrderedParticipants:

    def test_ordered_by_last_name(self, activity, contact, contact_extra):
        # contact = Jane Doe, contact_extra = John Smith -> Doe before Smith.
        activity.contacts.add(contact_extra, contact)
        assert ordered_participants(activity) == [contact, contact_extra]

    def test_other_account_participant_is_excluded(
        self, activity, contact, other_account_contact,
    ):
        activity.contacts.add(contact, other_account_contact)
        assert ordered_participants(activity) == [contact]

    def test_order_is_stable_on_homonyms(self, activity, account, user_a):
        from app_modules.contacts.models import Contact
        twins = []
        for _ in range(2):
            c = Contact(account=account, first_name='Sam', last_name='Lee')
            c.save(user=user_a, client_id=account.client_id)
            twins.append(c)
        activity.contacts.add(*twins)
        expected = sorted(twins, key=lambda c: c.id)
        assert ordered_participants(activity) == expected
        assert ordered_participants(activity) == expected

    def test_no_participant_is_empty(self, activity):
        assert ordered_participants(activity) == []


# =============================================================================
# resolve_participant_ref
# =============================================================================

class TestResolveParticipantRef:

    def test_valid_ref_resolves_to_contact(self, activity, contact, contact_extra):
        activity.contacts.add(contact, contact_extra)
        assert resolve_participant_ref('P1', activity) == contact
        assert resolve_participant_ref('P2', activity) == contact_extra

    @pytest.mark.parametrize('ref', ['P9', 'P0', 'Jane', 123, None, 'p 1', '', 'P-1', 'P1x'])
    def test_invalid_ref_is_none(self, activity, contact, contact_extra, ref):
        activity.contacts.add(contact, contact_extra)
        assert resolve_participant_ref(ref, activity) is None

    def test_other_account_participant_never_resolves(
        self, activity, contact, other_account_contact,
    ):
        # Unfiltered, Lumbergh would be P2 (Doe, Lumbergh). Filtered, the
        # list is [Doe] only, so P2 does not exist.
        activity.contacts.add(contact, other_account_contact)
        assert resolve_participant_ref('P2', activity) is None
        assert resolve_participant_ref('P1', activity) == contact

    def test_no_participant_resolves_nothing(self, activity):
        assert resolve_participant_ref('P1', activity) is None


# =============================================================================
# Context layer -- participant references
# =============================================================================

class TestContextParticipantRefs:

    def test_blocker_context_prefixes_each_participant_with_its_ref(
        self, activity, contact, contact_extra,
    ):
        activity.contacts.add(contact_extra, contact)
        ctx = build_context_layer(activity, target_stage='blocker')
        assert '* P1 — Jane (VP Engineering)' in ctx
        assert '* P2 — John (CTO)' in ctx

    def test_other_account_participant_not_listed(
        self, activity, contact, other_account_contact,
    ):
        activity.contacts.add(contact, other_account_contact)
        ctx = build_context_layer(activity, target_stage='blocker')
        assert '* P1 — Jane (VP Engineering)' in ctx
        assert 'Bill' not in ctx
        assert 'P2' not in ctx

    def test_no_participant_no_block(self, activity):
        ctx = build_context_layer(activity, target_stage='blocker')
        assert 'Prospect contacts in this conversation' not in ctx
        assert 'P1' not in ctx
