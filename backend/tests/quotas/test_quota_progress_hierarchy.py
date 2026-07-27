# backend/tests/quotas/test_quota_progress_hierarchy.py
"""
Manager perimeter — the aggregate is the WHOLE team subtree (recursive).

Team is a self-FK hierarchy (World -> region -> country). A manager attached to
a high node must measure the real production of every descendant, not only their
(often empty) direct members. The descent is one query, cycle-safe, and works
for an arbitrary node (reused by sub-step 5).

DB: Postgres.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app_modules.accounts.models import CompanyAccount
from app_modules.bi.metrics import MetricKey
from app_modules.decision_cycles.models import DecisionCycle
from app_modules.quotas.models import Quota
from app_modules.quotas.services import progress as P


TODAY = date.today()


# ---------------------------------------------------------------------------
# factories
# ---------------------------------------------------------------------------

def _role(ca, name, *, admin=False, manager=False, individual=False):
    from end_users.models import UserRole
    return UserRole.objects.create(
        client_account=ca, name=name, is_admin=admin, is_manager=manager,
        is_individual=individual, read=True, write=True, modify=True, can_delete=True,
    )


def _user(email, ca, role, team=None):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role,
                               is_active=True, team=team)


def _team(ca, name, *, parent=None, manager=None):
    from end_users.models import Team
    return Team.objects.create(name=name, client_account=ca, parent_team=parent,
                               manager=manager)


def _account(owner, ca):
    acc = CompanyAccount(company_name='Acc', has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _cycles(owner, account, ca, n):
    for i in range(n):
        dc = DecisionCycle(account=account, owner=owner, name=f'{owner.email}-{i}')
        dc.save(user=owner, client_id=ca.id)


def _quota(owner, ca, target=Decimal('10')):
    q = Quota(owner=owner, metric=MetricKey.DECISION_CYCLES, target_value=target,
              period_start=TODAY - timedelta(days=15), period_end=TODAY + timedelta(days=15))
    q.save(user=owner, client_id=ca.id)
    return q


# ---------------------------------------------------------------------------
# The repro + recursion
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestManagerSubtreeAggregate:

    def test_manager_on_high_node_aggregates_whole_subtree(self, client_account_a):
        """REPRO: manager on 'World' has NO direct members; all production is in
        the leaf 'FR'. The direct-members calc returns ~0; the correct subtree
        aggregate returns the real production."""
        role_ind = _role(client_account_a, 'Ind', individual=True)
        role_mgr = _role(client_account_a, 'Mgr', manager=True)

        world = _team(client_account_a, 'World')
        emea = _team(client_account_a, 'EMEA', parent=world)
        fr = _team(client_account_a, 'FR', parent=emea)

        manager = _user('mgr@a.test', client_account_a, role_mgr, team=world)
        rep = _user('rep@a.test', client_account_a, role_ind, team=fr)
        acc = _account(rep, client_account_a)
        _cycles(rep, acc, client_account_a, 3)   # production 2 levels below World

        q = _quota(manager, client_account_a, target=Decimal('10'))
        prog = P.compute_progress(q)
        assert prog.current_value == 3           # whole subtree, NOT 0
        assert prog.ratio == 0.3

    def test_recursion_counts_descendants_not_siblings(self, client_account_a):
        role_ind = _role(client_account_a, 'Ind', individual=True)
        role_mgr = _role(client_account_a, 'Mgr', manager=True)

        world = _team(client_account_a, 'World')
        emea = _team(client_account_a, 'EMEA', parent=world)
        fr = _team(client_account_a, 'FR', parent=emea)
        apac = _team(client_account_a, 'APAC', parent=world)   # sibling of EMEA

        manager_emea = _user('mgr-emea@a.test', client_account_a, role_mgr, team=emea)
        rep_fr = _user('rep-fr@a.test', client_account_a, role_ind, team=fr)      # under EMEA
        rep_apac = _user('rep-apac@a.test', client_account_a, role_ind, team=apac)  # sibling
        rep_world = _user('rep-world@a.test', client_account_a, role_ind, team=world)  # ancestor

        acc = _account(manager_emea, client_account_a)
        _cycles(rep_fr, acc, client_account_a, 2)     # counted (descendant)
        _cycles(rep_apac, acc, client_account_a, 5)   # NOT counted (sibling)
        _cycles(rep_world, acc, client_account_a, 7)  # NOT counted (ancestor)

        q = _quota(manager_emea, client_account_a, target=Decimal('10'))
        assert P.compute_progress(q).current_value == 2

    def test_direct_members_of_manager_node_still_counted(self, client_account_a):
        role_ind = _role(client_account_a, 'Ind', individual=True)
        role_mgr = _role(client_account_a, 'Mgr', manager=True)
        emea = _team(client_account_a, 'EMEA')
        fr = _team(client_account_a, 'FR', parent=emea)
        manager = _user('mgr@a.test', client_account_a, role_mgr, team=emea)
        direct = _user('direct@a.test', client_account_a, role_ind, team=emea)  # direct member
        leaf = _user('leaf@a.test', client_account_a, role_ind, team=fr)
        acc = _account(manager, client_account_a)
        _cycles(direct, acc, client_account_a, 1)
        _cycles(leaf, acc, client_account_a, 1)
        q = _quota(manager, client_account_a, target=Decimal('10'))
        assert P.compute_progress(q).current_value == 2  # direct + descendant


# ---------------------------------------------------------------------------
# Arbitrary node (reused by sub-step 5)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestArbitraryNode:

    def test_node_counts_only_its_own_subtree(self, client_account_a):
        role_ind = _role(client_account_a, 'Ind', individual=True)
        world = _team(client_account_a, 'World')
        emea = _team(client_account_a, 'EMEA', parent=world)
        fr = _team(client_account_a, 'FR', parent=emea)
        apac = _team(client_account_a, 'APAC', parent=world)
        rep_fr = _user('rep-fr@a.test', client_account_a, role_ind, team=fr)
        rep_apac = _user('rep-apac@a.test', client_account_a, role_ind, team=apac)
        acc = _account(rep_fr, client_account_a)
        _cycles(rep_fr, acc, client_account_a, 4)
        _cycles(rep_apac, acc, client_account_a, 9)

        # EMEA node: only its subtree (FR) -> 4, not APAC.
        v_emea = P.compute_metric_for_team_node(
            MetricKey.DECISION_CYCLES, emea.id, client_account_a.id)
        assert v_emea == 4
        # World node: the whole tree -> 4 + 9 = 13.
        v_world = P.compute_metric_for_team_node(
            MetricKey.DECISION_CYCLES, world.id, client_account_a.id)
        assert v_world == 13


# ---------------------------------------------------------------------------
# Anti-cycle + anti-N+1
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCycleAndQueries:

    def test_cycle_does_not_recurse_forever(self, client_account_a):
        role_ind = _role(client_account_a, 'Ind', individual=True)
        a = _team(client_account_a, 'A')
        b = _team(client_account_a, 'B', parent=a)
        # Introduce a cycle: A's parent becomes B (A -> B -> A). No DB constraint
        # forbids it (proven in the audit), so the descent must self-terminate.
        a.parent_team = b
        a.save()
        rep_a = _user('rep-a@a.test', client_account_a, role_ind, team=a)
        rep_b = _user('rep-b@a.test', client_account_a, role_ind, team=b)
        acc = _account(rep_a, client_account_a)
        _cycles(rep_a, acc, client_account_a, 1)
        _cycles(rep_b, acc, client_account_a, 1)
        # Must return (not hang) and count both nodes of the cycle.
        v = P.compute_metric_for_team_node(
            MetricKey.DECISION_CYCLES, a.id, client_account_a.id)
        assert v == 2
        assert P.team_subtree_ids(a.id, client_account_a.id) == {a.id, b.id}

    def test_query_count_constant_regardless_of_depth(
            self, django_assert_num_queries, client_account_a):
        role_ind = _role(client_account_a, 'Ind', individual=True)
        # A deep chain: t0 -> t1 -> ... -> t5, production at the leaf.
        parent = None
        nodes = []
        for i in range(6):
            parent = _team(client_account_a, f't{i}', parent=parent)
            nodes.append(parent)
        rep = _user('rep@a.test', client_account_a, role_ind, team=nodes[-1])
        acc = _account(rep, client_account_a)
        _cycles(rep, acc, client_account_a, 3)

        # One query for the subtree ids + one for the metric = 2, independent of
        # the 6-level depth.
        with django_assert_num_queries(2):
            v = P.compute_metric_for_team_node(
                MetricKey.DECISION_CYCLES, nodes[0].id, client_account_a.id)
        assert v == 3
