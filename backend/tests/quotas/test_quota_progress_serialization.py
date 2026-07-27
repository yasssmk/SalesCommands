# backend/tests/quotas/test_quota_progress_serialization.py
"""
Quota attainment in the API payload — current_value + progress_ratio.

The list and detail responses expose the computed attainment (from the progress
service, sub-step 4/4bis), NOT stored fields. The list precomputes the whole page
in one batch pass so the query count does not grow with the number of quotas.

DB: Postgres.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from app_modules.accounts.models import CompanyAccount
from app_modules.bi.metrics import MetricKey
from app_modules.decision_cycles.models import DecisionCycle
from app_modules.quotas.models import Quota
from app_modules.quotas.services import progress as P


TODAY = date.today()
URL = '/quotas/quotas/'


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


def _quota(owner, ca, *, metric=MetricKey.DECISION_CYCLES, target=Decimal('10'), name_suffix=''):
    q = Quota(owner=owner, metric=metric, target_value=target,
              period_start=TODAY - timedelta(days=15), period_end=TODAY + timedelta(days=15))
    q.save(user=owner, client_id=ca.id)
    return q


def _rows(resp):
    body = resp.json()
    return body.get('results', body) if isinstance(body, dict) else body


# ---------------------------------------------------------------------------
# Payload content
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPayloadExposesAttainment:

    def test_list_has_current_value_and_ratio_matching_service(
            self, api, authenticate, client_account_a):
        role = _role(client_account_a, 'Ind', individual=True)
        rep = _user('rep@a.test', client_account_a, role)
        acc = _account(rep, client_account_a)
        _cycles(rep, acc, client_account_a, 3)
        q = _quota(rep, client_account_a, target=Decimal('10'))

        authenticate(api, rep, client_account_a.id)
        resp = api.get(URL)
        assert resp.status_code == 200, resp.content
        row = next(r for r in _rows(resp) if str(r['id']) == str(q.id))

        expected = P.compute_progress(q)
        assert row['current_value'] == expected.current_value == 3
        assert row['progress_ratio'] == expected.ratio == 0.3
        assert row['state'] == 'CURRENT'   # period-state also exposed

    def test_detail_has_attainment(self, api, authenticate, client_account_a):
        role = _role(client_account_a, 'Ind', individual=True)
        rep = _user('rep2@a.test', client_account_a, role)
        acc = _account(rep, client_account_a)
        _cycles(rep, acc, client_account_a, 2)
        q = _quota(rep, client_account_a, target=Decimal('8'))

        authenticate(api, rep, client_account_a.id)
        resp = api.get(f'{URL}{q.id}/')
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body['current_value'] == 2
        assert body['progress_ratio'] == 0.25

    def test_overachievement_ratio_not_clamped(self, api, authenticate, client_account_a):
        role = _role(client_account_a, 'Ind', individual=True)
        rep = _user('rep3@a.test', client_account_a, role)
        acc = _account(rep, client_account_a)
        _cycles(rep, acc, client_account_a, 13)          # value 13 vs target 10
        q = _quota(rep, client_account_a, target=Decimal('10'))

        authenticate(api, rep, client_account_a.id)
        row = next(r for r in _rows(api.get(URL)) if str(r['id']) == str(q.id))
        assert row['current_value'] == 13
        assert row['progress_ratio'] == 1.3             # > 1, NOT clamped

    def test_target_zero_does_not_crash(self, api, authenticate, client_account_a):
        role = _role(client_account_a, 'Ind', individual=True)
        rep = _user('rep4@a.test', client_account_a, role)
        acc = _account(rep, client_account_a)
        _cycles(rep, acc, client_account_a, 2)
        q = _quota(rep, client_account_a, target=Decimal('0'))

        authenticate(api, rep, client_account_a.id)
        resp = api.get(URL)
        assert resp.status_code == 200
        row = next(r for r in _rows(resp) if str(r['id']) == str(q.id))
        assert row['current_value'] == 2
        assert row['progress_ratio'] is None            # undefined, not a crash


# ---------------------------------------------------------------------------
# Manager recursive subtree in the payload (consistency with 4bis)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestManagerSubtreeInPayload:

    def test_manager_quota_reflects_recursive_subtree(self, api, authenticate, client_account_a):
        role_ind = _role(client_account_a, 'Ind', individual=True)
        role_mgr = _role(client_account_a, 'Mgr', manager=True)
        world = _team(client_account_a, 'World')
        emea = _team(client_account_a, 'EMEA', parent=world)
        fr = _team(client_account_a, 'FR', parent=emea)
        manager = _user('mgr@a.test', client_account_a, role_mgr, team=world)
        rep = _user('rep@a.test', client_account_a, role_ind, team=fr)
        acc = _account(rep, client_account_a)
        _cycles(rep, acc, client_account_a, 4)           # production 2 levels below World
        q = _quota(manager, client_account_a, target=Decimal('10'))

        authenticate(api, manager, client_account_a.id)
        row = next(r for r in _rows(api.get(URL)) if str(r['id']) == str(q.id))
        assert row['current_value'] == 4                 # whole subtree, not 0


# ---------------------------------------------------------------------------
# Anti-N+1 — the list query count does not grow with the number of quotas
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAntiNPlusOne:

    def _list_query_count(self, api, authenticate, ca, rep, acc, n):
        # n quotas, same (metric, owner-perimeter, window, campaign) -> one group.
        for i in range(n):
            _quota(rep, ca, target=Decimal(str(i + 1)))
        authenticate(api, rep, ca.id)
        with CaptureQueriesContext(connection) as ctx:
            resp = api.get(URL)
        assert resp.status_code == 200
        return len(ctx.captured_queries)

    def test_query_count_constant_in_n(self, api, authenticate, client_account_a):
        role = _role(client_account_a, 'Ind', individual=True)
        rep = _user('repn@a.test', client_account_a, role)
        acc = _account(rep, client_account_a)
        _cycles(rep, acc, client_account_a, 3)

        few = self._list_query_count(api, authenticate, client_account_a, rep, acc, 2)
        # add more quotas of the same group, re-list: query count must not grow.
        many = self._list_query_count(api, authenticate, client_account_a, rep, acc, 6)
        assert few == many, f"N+1: {few} queries for 2 quotas, {many} for 8"
