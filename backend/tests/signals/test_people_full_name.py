# backend/tests/signals/test_people_full_name.py
"""
PeopleSignal.full_name / full_name_normalized (People sub-step 1).

full_name is a THIRD identity path (alongside target_contact / target_department),
nullable/blank — it does NOT change the clean() invariant (at least one of
target_contact / target_department stays required). full_name_normalized is
derived in save(), with the SAME normalisation as
TechStackSignal.tech_name_normalized / CompetitorSignal.competitor_name_normalized
(lower + strip + collapse internal whitespace ; blank -> '').
"""
import pytest

from app_modules.signals.constants import PeopleRole, SignalSource
from app_modules.signals.models import PeopleSignal


pytestmark = pytest.mark.django_db


class TestPeopleSignalFullName:

    def test_full_name_is_stored_raw_and_normalized_in_save(
        self, account, activity, contact, user_a,
    ):
        s = PeopleSignal(
            account=account,
            source_activity=activity,
            role=PeopleRole.CHAMPION,
            target_contact=contact,
            full_name='  Marc   Dubois ',
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()

        # Raw value preserved verbatim (like tech_name / competitor_name).
        assert s.full_name == '  Marc   Dubois '
        # Derived key: lower + strip + collapse.
        assert s.full_name_normalized == 'marc dubois'

    def test_blank_full_name_normalizes_to_empty_string(
        self, account, activity, contact, user_a,
    ):
        s = PeopleSignal(
            account=account,
            source_activity=activity,
            role=PeopleRole.CHAMPION,
            target_contact=contact,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()

        assert s.full_name_normalized == ''
