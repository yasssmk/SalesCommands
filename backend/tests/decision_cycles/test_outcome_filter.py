# backend/tests/decision_cycles/test_outcome_filter.py
"""
`outcome` list filter on DecisionCycleViewSet.

"Open" has exactly one definition — outcome IS NULL (the same one used by the
dc_pipeline_value KPI). is_active is NOT a proxy: it flags the single displayed
cycle per account, orthogonal to outcome. This is the filter the rep Home's
"My Decision Cycles" block relies on to avoid the tenant-wide read=client trap
(?owner_scope=mine&outcome__isnull=true).

Proves:
- ?outcome__isnull=true returns only OPEN cycles (drops closed ones),
- ?outcome__isnull=false / ?outcome=WON return only the matching closed cycles,
- the filter is ADDITIVE to scope — combined with owner_scope=mine it narrows
  to the caller's OPEN cycles and never surfaces another rep's,
- outcome__isnull=true does NOT bypass tenant isolation (a cross-tenant open
  cycle stays invisible).
"""

import pytest
from rest_framework import status

from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle
from app_modules.accounts.models import CompanyAccount


LIST_URL = '/decision_cycles/'


def _ids(resp):
    """Extract the set of cycle ids from a list response, envelope-agnostic."""
    body = resp.json()['data']
    results = body.get('results', body)
    if isinstance(results, dict):
        results = results.get('results', [])
    return {row['id'] for row in results}


# =============================================================================
# FIXTURES — a rep with one OPEN + one CLOSED cycle, plus a second rep's OPEN
# =============================================================================

@pytest.fixture
def rep_user(db, client_account_a, role_individual_a):
    from end_users.models import User
    return User.objects.create(
        email='rep-outcome@tenant-a.test',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
    )


@pytest.fixture
def other_rep(db, client_account_a, role_individual_a):
    from end_users.models import User
    return User.objects.create(
        email='other-rep-outcome@tenant-a.test',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
    )


def _account(owner, client_account, name):
    acc = CompanyAccount(company_name=name, has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=client_account.id)
    return acc


def _cycle(owner, client_account, account, name, outcome=None, is_active=True):
    c = DecisionCycle(account=account, owner=owner, name=name, is_active=is_active)
    if outcome is not None:
        c.outcome = outcome
    c.save(user=owner, client_id=client_account.id)
    return c


@pytest.fixture
def open_cycle(db, rep_user, client_account_a):
    acc = _account(rep_user, client_account_a, 'Open Corp')
    return _cycle(rep_user, client_account_a, acc, 'Open cycle', outcome=None)


@pytest.fixture
def closed_cycle(db, rep_user, client_account_a):
    # is_active=True even though closed — proves is_active is NOT "open".
    acc = _account(rep_user, client_account_a, 'Closed Corp')
    return _cycle(rep_user, client_account_a, acc, 'Won cycle',
                  outcome=CycleOutcome.WON, is_active=True)


@pytest.fixture
def other_rep_open_cycle(db, other_rep, client_account_a):
    acc = _account(other_rep, client_account_a, 'Other Rep Corp')
    return _cycle(other_rep, client_account_a, acc, 'Other open cycle', outcome=None)


# =============================================================================
# FILTER SEMANTICS
# =============================================================================

@pytest.mark.django_db
class TestOutcomeFilter:

    def test_isnull_true_returns_only_open(
        self, api, authenticate, rep_user, client_account_a, open_cycle, closed_cycle
    ):
        authenticate(api, rep_user, client_account_a.id)
        resp = api.get(LIST_URL, {'outcome__isnull': 'true'})
        assert resp.status_code == status.HTTP_200_OK
        ids = _ids(resp)
        assert str(open_cycle.id) in ids
        assert str(closed_cycle.id) not in ids  # closed dropped despite is_active=True

    def test_isnull_false_returns_only_closed(
        self, api, authenticate, rep_user, client_account_a, open_cycle, closed_cycle
    ):
        authenticate(api, rep_user, client_account_a.id)
        resp = api.get(LIST_URL, {'outcome__isnull': 'false'})
        assert resp.status_code == status.HTTP_200_OK
        ids = _ids(resp)
        assert str(closed_cycle.id) in ids
        assert str(open_cycle.id) not in ids

    def test_exact_outcome_matches(
        self, api, authenticate, rep_user, client_account_a, open_cycle, closed_cycle
    ):
        authenticate(api, rep_user, client_account_a.id)
        resp = api.get(LIST_URL, {'outcome': CycleOutcome.WON})
        assert resp.status_code == status.HTTP_200_OK
        ids = _ids(resp)
        assert ids == {str(closed_cycle.id)}


# =============================================================================
# ADDITIVE TO SCOPE — the filter narrows, it never widens
# =============================================================================

@pytest.mark.django_db
class TestOutcomeFilterRespectsScope:

    def test_open_plus_mine_excludes_other_reps_open(
        self, api, authenticate, rep_user, client_account_a,
        open_cycle, other_rep_open_cycle
    ):
        """owner_scope=mine + outcome__isnull=true = my open cycles only."""
        authenticate(api, rep_user, client_account_a.id)
        resp = api.get(LIST_URL, {'owner_scope': 'mine', 'outcome__isnull': 'true'})
        assert resp.status_code == status.HTTP_200_OK
        ids = _ids(resp)
        assert str(open_cycle.id) in ids
        assert str(other_rep_open_cycle.id) not in ids  # scope still binds

    def test_open_filter_does_not_bypass_tenant_isolation(
        self, api, authenticate, user_b, client_account_b, open_cycle
    ):
        """A cross-tenant caller asking for open cycles sees none of tenant A's."""
        authenticate(api, user_b, client_account_b.id)
        resp = api.get(LIST_URL, {'outcome__isnull': 'true'})
        assert resp.status_code == status.HTTP_200_OK
        assert str(open_cycle.id) not in _ids(resp)
