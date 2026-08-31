# backend/tests/signals/test_cluster_service_people.py
"""
People clustering (SignalClusterService) — two-level key.

People clusters PER PERSON, DC-scoped (like Constraint / Competitor), with a
two-level grouping key (in priority order):
  1. target_contact_id when a contact is linked (most reliable identity);
  2. else (full_name_normalized, target_department_id).

Cloned on the Competitor cluster tests. Covers the four key scenarios:
  (a) two People on the SAME contact (different names) → ONE cluster;
  (b) two People WITHOUT contact, same full_name_normalized + same department
      → ONE cluster;
  (c) same name but DIFFERENT department → TWO clusters;
  (d) one People with a contact and one without (same name) → they do NOT merge.
"""
import pytest

from app_modules.signals.constants import PeopleRole, SignalSource
from app_modules.signals.models import PeopleSignal
from app_modules.signals.services import SignalClusterService


pytestmark = pytest.mark.django_db


@pytest.fixture
def dept_sales(db):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name='Sales')
    return d


@pytest.fixture
def dept_marketing(db):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name='Marketing')
    return d


def _mk_people(account, activity, decision_cycle, user_a, *,
               role=PeopleRole.CHAMPION, full_name='', target_contact=None,
               target_department=None):
    sig = PeopleSignal(
        account=account,
        source_activity=activity,
        decision_cycle=decision_cycle,
        role=role,
        full_name=full_name,
        target_contact=target_contact,
        target_department=target_department,
        source=SignalSource.MANUAL,
    )
    sig.save(user=user_a, client_id=account.client_id)
    return sig


def _list_people(account, decision_cycle=None, **kwargs):
    return SignalClusterService.list_clusters_for_account(
        account_id=account.id,
        signal_type='people',
        decision_cycle_id=(decision_cycle.id if decision_cycle else None),
        **kwargs,
    )


class TestPeopleClusterKey:

    def test_a_same_contact_groups_into_one_cluster(
        self, account, activity, decision_cycle, user_a, contact,
    ):
        # Two mentions of the SAME contact, with DIFFERENT free-text names:
        # the contact_id branch must win over the name → ONE cluster.
        _mk_people(account, activity, decision_cycle, user_a,
                   full_name='Marc Dubois', target_contact=contact)
        _mk_people(account, activity, decision_cycle, user_a,
                   full_name='M. Dubois', target_contact=contact)

        clusters = _list_people(account, decision_cycle)
        assert len(clusters) == 1
        assert clusters[0]['signal_count'] == 2

    def test_b_same_name_and_department_group_into_one_cluster(
        self, account, activity, decision_cycle, user_a, dept_sales,
    ):
        _mk_people(account, activity, decision_cycle, user_a,
                   full_name='Marc   Dubois', target_department=dept_sales)
        _mk_people(account, activity, decision_cycle, user_a,
                   full_name='marc dubois', target_department=dept_sales)

        clusters = _list_people(account, decision_cycle)
        assert len(clusters) == 1
        assert clusters[0]['signal_count'] == 2

    def test_c_same_name_different_department_are_two_clusters(
        self, account, activity, decision_cycle, user_a,
        dept_sales, dept_marketing,
    ):
        _mk_people(account, activity, decision_cycle, user_a,
                   full_name='Marc Dubois', target_department=dept_sales)
        _mk_people(account, activity, decision_cycle, user_a,
                   full_name='Marc Dubois', target_department=dept_marketing)

        clusters = _list_people(account, decision_cycle)
        assert len(clusters) == 2

    def test_e_nameless_people_never_merge_on_department_alone(
        self, account, activity, decision_cycle, user_a, dept_sales,
    ):
        # Two People with NO name and NO contact, on the SAME department: they
        # are two DISTINCT unidentified stakeholders — they must each form their
        # own "to identify" entry, NOT collapse into one department cluster.
        _mk_people(account, activity, decision_cycle, user_a,
                   full_name='', target_department=dept_sales)
        _mk_people(account, activity, decision_cycle, user_a,
                   full_name='', target_department=dept_sales)

        clusters = _list_people(account, decision_cycle)
        assert len(clusters) == 2

    def test_d_contact_and_nameonly_do_not_merge(
        self, account, activity, decision_cycle, user_a, contact, dept_sales,
    ):
        # Same display name, but one is contact-linked and the other is only
        # name+department → they must NOT collapse into one cluster.
        _mk_people(account, activity, decision_cycle, user_a,
                   full_name='Marc Dubois', target_contact=contact)
        _mk_people(account, activity, decision_cycle, user_a,
                   full_name='Marc Dubois', target_department=dept_sales)

        clusters = _list_people(account, decision_cycle)
        assert len(clusters) == 2
