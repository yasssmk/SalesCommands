# backend/tests/decision_cycles/test_list_mine_c6.py
"""
DecisionCycle list — `owner_scope=mine` includes C6 (account-owner inheritance).

The rep Home's "My decision cycles" block lists cycles with owner_scope=mine.
The shared OwnerScopeMixin matches owner_id ONLY, which drops cycles an SDR
posted on the caller's own account — deals the caller can already read (C6) and
that dc_cycle_state resolves. The list therefore UNDER-showed an AE's portfolio.

Fix (DC-only): for owner_scope=mine the ViewSet reuses the SAME primitive the BI
layer uses, apply_role_scope('decision_cycles','mine') = owner OR account-owner
(C6), so the list's "mine" == the KPI's "mine". team / all / absent stay on the
mixin (unchanged — zero blast radius on the 8 other ViewSets).

Proves:
- the fix: rep owns 1 cycle + 2 posted by an SDR on the rep's account -> mine
  returns all 3 (owner + C6),
- boundary: another rep's cycle on another account -> excluded,
- boundary: cross-tenant -> excluded,
- the paginated count is correct with the C6 cycles (C6 -> filter -> paginate),
- non-regression: owner_scope=team and owner_scope absent are UNCHANGED (still
  the mixin's owner_id-only / no-filter behaviour).
"""

import pytest
from rest_framework import status

from app_modules.decision_cycles.models import DecisionCycle
from app_modules.accounts.models import CompanyAccount

LIST_URL = '/decision_cycles/'


def _rows(resp):
    body = resp.json()['data']
    results = body.get('results', body)
    if isinstance(results, dict):
        results = results.get('results', [])
    return results


def _ids(resp):
    return {row['id'] for row in _rows(resp)}


# =============================================================================
# FIXTURES — AE (account owner), SDR (creator), another rep on another account
# =============================================================================

@pytest.fixture
def ae(db, client_account_a, role_individual_a):
    from end_users.models import User
    return User.objects.create(email='ae-c6@a.test', client_account=client_account_a,
                               role=role_individual_a, is_active=True)


@pytest.fixture
def sdr(db, client_account_a, role_individual_a):
    from end_users.models import User
    return User.objects.create(email='sdr-c6@a.test', client_account=client_account_a,
                               role=role_individual_a, is_active=True)


@pytest.fixture
def other_rep(db, client_account_a, role_individual_a):
    from end_users.models import User
    return User.objects.create(email='other-c6@a.test', client_account=client_account_a,
                               role=role_individual_a, is_active=True)


def _account(owner, ca, name):
    acc = CompanyAccount(company_name=name, has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _cycle(owner, ca, account, name):
    c = DecisionCycle(account=account, owner=owner, name=name)
    c.save(user=owner, client_id=ca.id)
    return c


@pytest.fixture
def ae_account(db, ae, client_account_a):
    return _account(ae, client_account_a, 'AE Portfolio Corp')


# =============================================================================
# THE FIX — mine now includes C6
# =============================================================================

@pytest.mark.django_db
class TestMineIncludesC6:

    def test_ae_sees_own_and_sdr_posted_cycles_on_their_account(
        self, api, authenticate, ae, sdr, client_account_a, ae_account
    ):
        own = _cycle(ae, client_account_a, ae_account, 'AE-owned deal')
        sdr1 = _cycle(sdr, client_account_a, ae_account, 'SDR deal 1')
        sdr2 = _cycle(sdr, client_account_a, ae_account, 'SDR deal 2')

        authenticate(api, ae, client_account_a.id)
        resp = api.get(LIST_URL, {'owner_scope': 'mine'})
        assert resp.status_code == status.HTTP_200_OK
        # all 3: 1 owned + 2 via C6 (account-owner), matching dc_cycle_state's mine
        assert _ids(resp) == {str(own.id), str(sdr1.id), str(sdr2.id)}

    def test_another_reps_cycle_on_another_account_is_excluded(
        self, api, authenticate, ae, other_rep, client_account_a, ae_account
    ):
        own = _cycle(ae, client_account_a, ae_account, 'AE-owned deal')
        other_acc = _account(other_rep, client_account_a, 'Other Rep Corp')
        _cycle(other_rep, client_account_a, other_acc, 'Other rep deal')  # not AE's

        authenticate(api, ae, client_account_a.id)
        resp = api.get(LIST_URL, {'owner_scope': 'mine'})
        assert _ids(resp) == {str(own.id)}  # C6 does not leak other accounts

    def test_cross_tenant_excluded(
        self, api, authenticate, ae, user_b, client_account_b, client_account_a, ae_account
    ):
        _cycle(ae, client_account_a, ae_account, 'Tenant A deal')
        authenticate(api, user_b, client_account_b.id)
        resp = api.get(LIST_URL, {'owner_scope': 'mine'})
        assert resp.status_code == status.HTTP_200_OK
        assert _ids(resp) == set()  # tenant B sees none of tenant A's cycles

    def test_paginated_count_is_correct_with_c6_cycles(
        self, api, authenticate, ae, sdr, client_account_a, ae_account
    ):
        # 1 owned + 4 C6 = 5 in scope; page_size=2 -> count must be 5, not 1.
        _cycle(ae, client_account_a, ae_account, 'AE deal')
        for i in range(4):
            _cycle(sdr, client_account_a, ae_account, f'SDR deal {i}')

        authenticate(api, ae, client_account_a.id)
        resp = api.get(LIST_URL, {'owner_scope': 'mine', 'page': 1, 'page_size': 2})
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()['data']
        assert body['count'] == 5           # count reflects the full C6 scope
        assert len(body['results']) == 2    # page holds page_size rows


# =============================================================================
# NON-REGRESSION — team / absent stay on the mixin, unchanged
# =============================================================================

@pytest.mark.django_db
class TestOtherScopesUnchanged:

    def test_absent_owner_scope_is_client_wide(
        self, api, authenticate, ae, sdr, client_account_a, ae_account
    ):
        """No owner_scope -> mixin no-ops -> the read=client list (whole tenant),
        exactly as before the fix. A cycle owned by the SDR is visible."""
        _cycle(ae, client_account_a, ae_account, 'AE deal')
        sdr_acc = _account(sdr, client_account_a, 'SDR Own Corp')
        sdr_only = _cycle(sdr, client_account_a, sdr_acc, 'SDR-only deal')

        authenticate(api, ae, client_account_a.id)
        resp = api.get(LIST_URL)  # no owner_scope
        # client-wide: the SDR's cycle on the SDR's own account is present too
        assert str(sdr_only.id) in _ids(resp)

    def test_team_scope_unchanged_owner_id_semantics(
        self, api, authenticate, ae, sdr, client_account_a, ae_account
    ):
        """owner_scope=team still routes through the mixin. An individual (no
        managed team) falls back to owner_id -> only the AE-owned cycle, NOT the
        SDR's C6 cycle (proving team did not silently gain C6)."""
        own = _cycle(ae, client_account_a, ae_account, 'AE deal')
        sdr_c6 = _cycle(sdr, client_account_a, ae_account, 'SDR C6 deal')

        authenticate(api, ae, client_account_a.id)
        resp = api.get(LIST_URL, {'owner_scope': 'team'})
        ids = _ids(resp)
        assert str(own.id) in ids
        assert str(sdr_c6.id) not in ids  # team != mine-with-C6
