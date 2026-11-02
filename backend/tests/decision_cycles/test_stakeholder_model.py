# backend/tests/decision_cycles/test_stakeholder_model.py
"""
Sprint « Cycle de vie des contacts », étape 3 -- the Stakeholder model (the
PERSON at the DC level), PeopleSignal.stakeholder (affiliation of an
observation), Activity.stakeholders (non-converted stakeholders) and
stakeholder_service.attach_signal (the FIRST role becomes current_signal).
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from app_modules.signals.constants import PeopleRole, SignalSource


pytestmark = pytest.mark.django_db


def _cycle(account, user, name='Deal'):
    from app_modules.decision_cycles.models import DecisionCycle
    dc = DecisionCycle(account=account, owner=user, name=name)
    dc.save(user=user, client_id=account.client_id)
    return dc


def _stakeholder(cycle, user, **fields):
    from app_modules.decision_cycles.models import Stakeholder
    s = Stakeholder(decision_cycle=cycle, **fields)
    s.save(user=user, client_id=cycle.client_id)
    return s


def _people(activity, cycle, user, role, name='Marc Dupont'):
    from app_modules.signals.models import PeopleSignal
    p = PeopleSignal(account=activity.account, source_activity=activity, decision_cycle=cycle,
                     source=SignalSource.LLM_EXTRACTED, role=role, full_name=name,
                     source_quote=f'{name} said so', confidence=0.8)
    p.save(user=user, client_id=activity.client_id)
    return p


# =============================================================================
# MODEL
# =============================================================================

def test_full_name_normalized_is_derived_like_people_signal(account, user_a):
    from app_modules.signals.models import PeopleSignal
    s = _stakeholder(_cycle(account, user_a), user_a, full_name='  Marc   DUPONT ')
    s.refresh_from_db()
    assert s.full_name_normalized == 'marc dupont'
    assert s.full_name_normalized == PeopleSignal._normalize_full_name('  Marc   DUPONT ')


def test_clean_requires_a_contact_a_name_or_a_department(account, user_a):
    from app_modules.decision_cycles.models import Stakeholder
    with pytest.raises(ValidationError):
        Stakeholder(decision_cycle=_cycle(account, user_a)).clean()


def test_a_first_name_alone_is_enough(account, user_a):
    from app_modules.decision_cycles.models import Stakeholder
    Stakeholder(decision_cycle=_cycle(account, user_a), full_name='Marc').clean()


def test_one_stakeholder_per_cycle_and_contact(account, user_a, contact):
    cycle = _cycle(account, user_a)
    _stakeholder(cycle, user_a, contact=contact)
    with pytest.raises(IntegrityError), transaction.atomic():
        _stakeholder(cycle, user_a, contact=contact)


def test_the_same_contact_in_another_cycle_is_another_stakeholder(account, user_a, contact):
    _stakeholder(_cycle(account, user_a, 'A'), user_a, contact=contact)
    _stakeholder(_cycle(account, user_a, 'B'), user_a, contact=contact)


def test_no_uniqueness_on_the_name_nor_on_not_linked(account, user_a):
    cycle = _cycle(account, user_a)
    _stakeholder(cycle, user_a, full_name='Marc')
    _stakeholder(cycle, user_a, full_name='Marc')


def test_activity_references_non_converted_stakeholders(account, activity, user_a):
    s = _stakeholder(_cycle(account, user_a), user_a, full_name='Marc')
    activity.stakeholders.add(s)
    assert list(s.activities.all()) == [activity]


# =============================================================================
# SERVICE attach_signal
# =============================================================================

def test_the_first_role_becomes_current_a_later_one_does_not(account, activity, user_a):
    from app_modules.decision_cycles.services.stakeholder_service import attach_signal
    cycle = _cycle(account, user_a)
    s = _stakeholder(cycle, user_a, full_name='Marc Dupont')
    champion = _people(activity, cycle, user_a, PeopleRole.CHAMPION)
    decision_maker = _people(activity, cycle, user_a, PeopleRole.DECISION_MAKER)

    attach_signal(champion, s)
    attach_signal(decision_maker, s)

    s.refresh_from_db()
    champion.refresh_from_db()
    decision_maker.refresh_from_db()
    assert s.current_signal_id == champion.id
    assert champion.stakeholder_id == s.id
    assert decision_maker.stakeholder_id == s.id
    assert set(s.signals.values_list('id', flat=True)) == {champion.id, decision_maker.id}


def test_a_signal_of_another_cycle_is_refused(account, activity, user_a):
    from app_modules.decision_cycles.services.stakeholder_service import attach_signal
    s = _stakeholder(_cycle(account, user_a, 'A'), user_a, full_name='Marc')
    other = _people(activity, _cycle(account, user_a, 'B'), user_a, PeopleRole.CHAMPION)
    with pytest.raises(ValidationError):
        attach_signal(other, s)
    other.refresh_from_db()
    assert other.stakeholder_id is None
