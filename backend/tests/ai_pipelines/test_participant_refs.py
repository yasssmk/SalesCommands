# backend/tests/ai_pipelines/test_participant_refs.py
"""
Unit tests for services/participant_refs.py.

  * ordered_participants(activity): activity.contacts filtered on the
    activity's tenant AND account, ordered last_name, first_name, id -- the
    scope resolve_participant_by_name links names in (TD-279; the "P<n>"
    references and their context lines are gone since B4b, the name link is
    tested in test_attribution_by_name.py).
"""

import pytest

from app_modules.ai_pipelines.services.participant_refs import ordered_participants

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
