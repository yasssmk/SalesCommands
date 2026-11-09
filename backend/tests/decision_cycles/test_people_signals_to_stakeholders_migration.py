# backend/tests/decision_cycles/test_people_signals_to_stakeholders_migration.py
"""
Sprint « Cycle de vie des contacts », étape 3 -- the data migration
decision_cycles/0025_people_signals_to_stakeholders: the VALIDATED People
signals of a decision cycle become its Stakeholders.

Grouping EXACT: (dc, contact) / (dc, normalised name, department) /
(dc, department); current_signal = the MOST RECENT; PENDING / REJECTED and
signals without a cycle not migrated; reverse lossless.

forwards() / reverse() run on the CURRENT app registry: its state is the one
after the schema migrations (0024 + module_signals 0051), and the data
migration only creates / clears rows.
"""

import datetime
import importlib

import pytest
from django.apps import apps as django_apps
from django.utils import timezone

from app_modules.signals.constants import PeopleRole, SignalSource, SignalStatus


pytestmark = pytest.mark.django_db

MIGRATION = 'app_modules.decision_cycles.migrations.0025_people_signals_to_stakeholders'


def _migration():
    return importlib.import_module(MIGRATION)


def _cycle(account, user, name):
    from app_modules.decision_cycles.models import DecisionCycle
    dc = DecisionCycle(account=account, owner=user, name=name)
    dc.save(user=user, client_id=account.client_id)
    return dc


def _dept(name):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name=name)
    return d


def _ps(activity, user, *, cycle, role=PeopleRole.CHAMPION, status=SignalStatus.VALIDATED,
        contact=None, name='', dept=None, days_ago=1):
    from app_modules.signals.models import PeopleSignal
    p = PeopleSignal(account=activity.account, source_activity=activity, decision_cycle=cycle,
                     source=SignalSource.LLM_EXTRACTED, role=role, full_name=name,
                     target_contact=contact, target_department=dept,
                     source_quote='q', confidence=0.8)
    p.save(user=user, client_id=activity.client_id)
    PeopleSignal.objects.filter(pk=p.pk).update(
        status=status,
        created_at=timezone.now() - datetime.timedelta(days=days_ago),
    )
    p.refresh_from_db()
    return p


@pytest.fixture
def seeded(account, activity, user_a, contact):
    from app_modules.contacts.models import Contact
    other_contact = Contact(account=account, first_name='Dana', last_name='Pending')
    other_contact.save(user=user_a, client_id=account.client_id)
    a = _cycle(account, user_a, 'A')
    b = _cycle(account, user_a, 'B')
    sales, marketing = _dept('Sales'), _dept('Marketing')
    rows = {
        # stacked on a contact: CHAMPION then DECISION_MAKER
        'c_champion': _ps(activity, user_a, cycle=a, contact=contact,
                          role=PeopleRole.CHAMPION, days_ago=3),
        'c_dm': _ps(activity, user_a, cycle=a, contact=contact,
                    role=PeopleRole.DECISION_MAKER, days_ago=1),
        # a name only (two spellings, same normalised name, same department)
        'marc_old': _ps(activity, user_a, cycle=a, name='Marc Dupont', dept=sales, days_ago=2),
        'marc_new': _ps(activity, user_a, cycle=a, name='marc  dupont', dept=sales, days_ago=1),
        # exact grouping: a first name alone is another stakeholder
        'marc_short': _ps(activity, user_a, cycle=a, name='Marc', dept=sales),
        # a department only
        'dept_only': _ps(activity, user_a, cycle=a, dept=marketing),
        # NOT migrated
        'pending': _ps(activity, user_a, cycle=a, contact=other_contact,
                       status=SignalStatus.PENDING),
        'rejected': _ps(activity, user_a, cycle=a, name='Zoe', status=SignalStatus.REJECTED),
        'no_cycle': _ps(activity, user_a, cycle=None, name='Nobody'),
        # the same contact on ANOTHER cycle: another stakeholder
        'c_on_b': _ps(activity, user_a, cycle=b, contact=contact),
    }
    return {'a': a, 'b': b, 'contact': contact, 'sales': sales, 'marketing': marketing, **rows}


def _stakeholder_of(ps):
    ps.refresh_from_db()
    return ps.stakeholder


def test_forwards_one_stakeholder_per_exact_group(seeded):
    from app_modules.decision_cycles.models import Stakeholder
    _migration().forwards(django_apps, None)

    assert Stakeholder.objects.count() == 5

    on_contact = _stakeholder_of(seeded['c_dm'])
    assert _stakeholder_of(seeded['c_champion']) == on_contact
    assert on_contact.contact == seeded['contact']
    assert on_contact.decision_cycle == seeded['a']
    assert on_contact.current_signal_id == seeded['c_dm'].id          # the most recent

    marc = _stakeholder_of(seeded['marc_new'])
    assert _stakeholder_of(seeded['marc_old']) == marc
    assert marc.contact is None
    assert marc.full_name_normalized == 'marc dupont'
    assert marc.department == seeded['sales']
    assert marc.current_signal_id == seeded['marc_new'].id

    assert _stakeholder_of(seeded['marc_short']) not in (None, marc)
    dept = _stakeholder_of(seeded['dept_only'])
    assert dept.full_name == '' and dept.department == seeded['marketing']

    on_b = _stakeholder_of(seeded['c_on_b'])
    assert on_b not in (None, on_contact) and on_b.decision_cycle == seeded['b']

    for key in ('pending', 'rejected', 'no_cycle'):
        assert _stakeholder_of(seeded[key]) is None


def test_reverse_is_lossless(seeded):
    from app_modules.decision_cycles.models import Stakeholder
    from app_modules.signals.models import PeopleSignal
    before = list(PeopleSignal.objects.order_by('id').values(
        'id', 'role', 'status', 'full_name', 'target_contact_id', 'decision_cycle_id',
    ))
    _migration().forwards(django_apps, None)
    _migration().reverse(django_apps, None)

    assert Stakeholder.objects.count() == 0
    assert not PeopleSignal.objects.filter(stakeholder__isnull=False).exists()
    after = list(PeopleSignal.objects.order_by('id').values(
        'id', 'role', 'status', 'full_name', 'target_contact_id', 'decision_cycle_id',
    ))
    assert after == before
