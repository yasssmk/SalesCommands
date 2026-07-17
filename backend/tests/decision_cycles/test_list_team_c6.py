# backend/tests/decision_cycles/test_list_team_c6.py
"""
DecisionCycle `owner_scope=team` includes C6 (account-owner inheritance) — the
manager DC block fix.

The pendant of the rep bug C, one level up. The manager DC block reads
owner_scope=team. Team scope used to match the OWNER only (team members), so a
cycle a non-member SDR posted on a MEMBER's account (owner = SDR, account owner =
a managed AE) was dropped — the manager saw ~2 of an AE's 7 open deals.

Fix: `_apply_team_scope` gained the C6 term (account_owner_user IN team members),
and the DC list diverts owner_scope=team to apply_role_scope('team') so the list
== the KPI. This test proves the manager now sees owned + C6, and that the
hierarchy boundary still holds (an out-of-hierarchy account never enters).
"""

import pytest
from rest_framework import status

from app_modules.accounts.models import CompanyAccount
from app_modules.decision_cycles.models import DecisionCycle
from permissions.compat import AuthContext
from permissions.scope_filter import apply_role_scope

LIST_URL = '/decision_cycles/'


def _rows(resp):
    body = resp.json()['data']
    results = body.get('results', body)
    if isinstance(results, dict):
        results = results.get('results', [])
    return results


def _ids(resp):
    return {row['id'] for row in _rows(resp)}


def _ctx(user, ca):
    return AuthContext(user_id=str(user.id), client_id=str(ca.id), is_authenticated=True)


def _mk_user(email, ca, role, **extra):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role, is_active=True, **extra)


def _mk_team(name, ca, manager=None):
    from end_users.models import Team
    return Team.objects.create(name=name, client_account=ca, manager=manager)


def _account(owner, ca, name):
    acc = CompanyAccount(company_name=name, has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _cycle(owner, ca, account, name):
    c = DecisionCycle(account=account, owner=owner, name=name)
    c.save(user=owner, client_id=ca.id)
    return c


@pytest.fixture
def org(db, client_account_a, role_individual_a):
    """mgr manages EMEA. ae is a member of EMEA. sdr is NOT a member."""
    ca = client_account_a
    mgr = _mk_user('mgr-team-c6@a.test', ca, role_individual_a)
    emea = _mk_team('EMEA', ca, manager=mgr)
    ae = _mk_user('ae-team-c6@a.test', ca, role_individual_a, team=emea)
    sdr = _mk_user('sdr-team-c6@a.test', ca, role_individual_a)
    return {'ca': ca, 'mgr': mgr, 'emea': emea, 'ae': ae, 'sdr': sdr}


# =============================================================================
# PRIMITIVE — apply_role_scope('team') now carries C6, bounded to members
# =============================================================================

@pytest.mark.django_db
def test_primitive_team_scope_includes_owned_and_c6(org):
    ca = org['ca']
    ae_acc = _account(org['ae'], ca, 'AE Portfolio')
    owned = _cycle(org['ae'], ca, ae_acc, 'AE-owned deal')             # owner = member
    sdr1 = _cycle(org['sdr'], ca, ae_acc, 'SDR deal 1 on AE account')  # C6: owner=SDR, acct owner=AE
    sdr2 = _cycle(org['sdr'], ca, ae_acc, 'SDR deal 2 on AE account')

    base = DecisionCycle.objects.filter(client_id=ca.id)
    team_ids = {str(i) for i in apply_role_scope(
        base, module='decision_cycles', scope='team', auth_ctx=_ctx(org['mgr'], ca)
    ).values_list('id', flat=True)}

    # owned by a member AND SDR-posted on the member's account — all three now.
    assert team_ids == {str(owned.id), str(sdr1.id), str(sdr2.id)}


@pytest.mark.django_db
def test_primitive_team_boundary_holds_out_of_hierarchy_account_excluded(org):
    """C6 is bounded to team members as the account owner: a cycle on an account
    owned OUTSIDE the manager's hierarchy never enters team scope."""
    ca = org['ca']
    outsider = _mk_user('outsider-team-c6@a.test', ca, org['ae'].role)  # no managed team, not a member
    out_acc = _account(outsider, ca, 'Outsider Corp')
    out_cycle = _cycle(org['sdr'], ca, out_acc, 'SDR deal on OUTSIDER account')  # acct owner = outsider

    base = DecisionCycle.objects.filter(client_id=ca.id)
    team_ids = {str(i) for i in apply_role_scope(
        base, module='decision_cycles', scope='team', auth_ctx=_ctx(org['mgr'], ca)
    ).values_list('id', flat=True)}

    assert str(out_cycle.id) not in team_ids  # boundary holds — not a member's account


# =============================================================================
# LIST — the manager DC block sees owned + C6 via owner_scope=team
# =============================================================================

@pytest.mark.django_db
def test_manager_list_team_sees_owned_and_sdr_posted_deals(org, api, authenticate):
    """The reported bug: an AE with 2 owned + 5 SDR-posted deals on their account
    -> the manager block must show all 7, not just the 2 owned."""
    ca = org['ca']
    ae_acc = _account(org['ae'], ca, 'AE Portfolio')
    expected = set()
    for i in range(2):
        expected.add(str(_cycle(org['ae'], ca, ae_acc, f'AE-owned {i}').id))
    for i in range(5):
        expected.add(str(_cycle(org['sdr'], ca, ae_acc, f'SDR-posted {i}').id))

    authenticate(api, org['mgr'], ca.id)
    resp = api.get(LIST_URL, {'owner_scope': 'team'})
    assert resp.status_code == status.HTTP_200_OK
    assert expected <= _ids(resp)          # all 7 present (was: only the 2 owned)
    assert len(expected) == 7


@pytest.mark.django_db
def test_manager_list_team_excludes_out_of_hierarchy(org, api, authenticate):
    ca = org['ca']
    ae_acc = _account(org['ae'], ca, 'AE Portfolio')
    mine = _cycle(org['ae'], ca, ae_acc, 'AE deal')

    outsider = _mk_user('outsider-list@a.test', ca, org['ae'].role)
    out_acc = _account(outsider, ca, 'Outsider Corp')
    out_cycle = _cycle(outsider, ca, out_acc, 'Outsider deal')

    authenticate(api, org['mgr'], ca.id)
    resp = api.get(LIST_URL, {'owner_scope': 'team'})
    ids = _ids(resp)
    assert str(mine.id) in ids
    assert str(out_cycle.id) not in ids  # out-of-hierarchy account never enters
