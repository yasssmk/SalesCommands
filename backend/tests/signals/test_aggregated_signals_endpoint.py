# backend/tests/signals/test_aggregated_signals_endpoint.py
"""
B2-BE: GET /module-signals/all/ — one aggregated, paginated, sorted, mixed
list of ALL signal types for a single scope (account OR decision cycle).

Covers: mixed list + signal_type per item, created_at DESC ordering with a
stable id secondary key, page_size honoured, tenant isolation, scope
(account spans DCs / decision_cycle narrows), neither/both -> 400 business
error, polymorphic completeness across all 8 types, and a bounded query
count (not O(rows)).
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.signals.constants import (
    ImpactType,
    PeopleRole,
    Rigidity,
    ScopeLevel,
    SignalDimension,
    SignalSource,
    SignalWhat,
)
from app_modules.signals.models import (
    BlockerSignal,
    ConstraintSignal,
    ImpactSignal,
    NextStepSignal,
    ObjectiveSignal,
    PainSignal,
    PeopleSignal,
    TechStackSignal,
)


pytestmark = pytest.mark.django_db(transaction=True)


def _url():
    return reverse('module_signals:signal-all')


def _results(response):
    body = response.json()
    return body.get('results', body)


# --------------------------------------------------------------------------
# Builders — minimal valid instances per type, saved to a given scope.
# --------------------------------------------------------------------------

def _mk_pain(account, activity, user, dc=None):
    p = PainSignal(
        account=account, source_activity=activity, decision_cycle=dc,
        source=SignalSource.MANUAL,
        what=SignalWhat.DATA, dimension=SignalDimension.QUALITY,
        scope_level=ScopeLevel.BUSINESS, summary='pain here',
        source_quote='we lose data',
    )
    p.save(user=user, client_id=account.client_id)
    return p


def _mk_impact(account, activity, user, dc=None):
    i = ImpactSignal(
        account=account, source_activity=activity, decision_cycle=dc,
        source=SignalSource.MANUAL,
        what=SignalWhat.DATA, dimension=SignalDimension.QUALITY,
        impact_type=ImpactType.PRODUCTIVITY, scope_level=ScopeLevel.BUSINESS,
        summary='impact here', metric_text='5h/week',
    )
    i.save(user=user, client_id=account.client_id)
    return i


def _mk_tech(account, activity, user, dc=None):
    t = TechStackSignal(
        account=account, source_activity=activity, decision_cycle=dc,
        source=SignalSource.MANUAL, tech_name='Salesforce',
    )
    t.save(user=user, client_id=account.client_id)
    return t


def _mk_blocker(account, activity, user, dc=None):
    b = BlockerSignal(
        account=account, source_activity=activity, decision_cycle=dc,
        source=SignalSource.MANUAL, summary='blocked on budget',
    )
    b.save(user=user, client_id=account.client_id)
    return b


def _mk_objective(account, activity, user, dc=None):
    o = ObjectiveSignal(
        account=account, source_activity=activity, decision_cycle=dc,
        source=SignalSource.MANUAL,
        what=SignalWhat.DATA, dimension=SignalDimension.QUALITY,
        scope_level=ScopeLevel.BUSINESS, summary='improve data',
    )
    o.save(user=user, client_id=account.client_id)
    return o


def _mk_nextstep(account, activity, user, dc=None):
    n = NextStepSignal(
        account=account, source_activity=activity, decision_cycle=dc,
        source=SignalSource.MANUAL,
        suggested_title='Follow up', suggested_activity_type='CALL',
    )
    n.save(user=user, client_id=account.client_id)
    return n


def _mk_people(account, activity, user, dc=None):
    pe = PeopleSignal(
        account=account, source_activity=activity, decision_cycle=dc,
        source=SignalSource.MANUAL, role=PeopleRole.CHAMPION,
    )
    pe.save(user=user, client_id=account.client_id)
    return pe


def _mk_constraint(account, activity, user, dc=None):
    c = ConstraintSignal(
        account=account, source_activity=activity, decision_cycle=dc,
        source=SignalSource.MANUAL,
        what=SignalWhat.OPS, dimension=SignalDimension.COST,
        summary='must stay on-prem', rigidity=Rigidity.FIRM,
    )
    c.save(user=user, client_id=account.client_id)
    return c


class TestAggregatedSignalsEndpoint:

    def test_returns_paginated_mixed_list_with_signal_type(
        self, authed_api_a, account, activity, user_a,
    ):
        _mk_pain(account, activity, user_a)
        _mk_impact(account, activity, user_a)
        _mk_tech(account, activity, user_a)
        _mk_blocker(account, activity, user_a)

        resp = authed_api_a.get(_url(), {'account_id': str(account.id)})
        assert resp.status_code == status.HTTP_200_OK

        body = resp.json()
        assert body['count'] == 4
        rows = body['results']
        types = {r['signal_type'] for r in rows}
        assert types == {'pain', 'impact', 'tech-stack', 'blockers'}
        # Every row carries signal_type + the shared created_at.
        for r in rows:
            assert 'signal_type' in r
            assert 'created_at' in r

    def test_ordered_created_at_desc_with_stable_id_secondary(
        self, authed_api_a, account, activity, user_a,
    ):
        p = _mk_pain(account, activity, user_a)
        i = _mk_impact(account, activity, user_a)
        b = _mk_blocker(account, activity, user_a)

        # Force distinct, known created_at (auto_now_add would collide).
        from django.utils import timezone
        import datetime
        base = timezone.now()
        PainSignal.objects.filter(id=p.id).update(created_at=base - datetime.timedelta(minutes=1))
        ImpactSignal.objects.filter(id=i.id).update(created_at=base - datetime.timedelta(minutes=2))
        BlockerSignal.objects.filter(id=b.id).update(created_at=base - datetime.timedelta(minutes=3))

        resp = authed_api_a.get(_url(), {'account_id': str(account.id)})
        rows = resp.json()['results']
        ids = [r['id'] for r in rows]
        # Newest (pain) first, oldest (blocker) last.
        assert ids == [str(p.id), str(i.id), str(b.id)]

    def test_page_size_honoured_and_count_total(
        self, authed_api_a, account, activity, user_a,
    ):
        for _ in range(3):
            _mk_pain(account, activity, user_a)
        _mk_impact(account, activity, user_a)

        resp = authed_api_a.get(_url(), {'account_id': str(account.id), 'page_size': 2})
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body['count'] == 4
        assert len(body['results']) == 2
        assert body['next'] is not None

    def test_tenant_isolation(
        self, authed_api_a, account, other_tenant_account, other_tenant_activity,
        activity, user_a, user_b,
    ):
        # Tenant B owns a pain on B's account.
        _mk_pain(other_tenant_account, other_tenant_activity, user_b)
        # Tenant A owns one on A's account.
        _mk_pain(account, activity, user_a)

        # A queries B's account_id → must see nothing (client scoping).
        resp = authed_api_a.get(_url(), {'account_id': str(other_tenant_account.id)})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['count'] == 0

        # A queries A's account → sees only A's.
        resp2 = authed_api_a.get(_url(), {'account_id': str(account.id)})
        assert resp2.json()['count'] == 1

    def test_scope_account_spans_dcs(
        self, authed_api_a, account, activity, user_a, decision_cycle,
    ):
        _mk_pain(account, activity, user_a, dc=decision_cycle)  # in a DC
        _mk_impact(account, activity, user_a, dc=None)          # no DC

        resp = authed_api_a.get(_url(), {'account_id': str(account.id)})
        assert resp.json()['count'] == 2  # account scope spans both

    def test_scope_decision_cycle_narrows(
        self, authed_api_a, account, activity, user_a, decision_cycle,
    ):
        in_dc = _mk_pain(account, activity, user_a, dc=decision_cycle)
        _mk_impact(account, activity, user_a, dc=None)  # not in the DC

        resp = authed_api_a.get(_url(), {'decision_cycle_id': str(decision_cycle.id)})
        body = resp.json()
        assert body['count'] == 1
        assert body['results'][0]['id'] == str(in_dc.id)

    def test_neither_scope_returns_400(self, authed_api_a):
        resp = authed_api_a.get(_url())
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_both_scopes_returns_400(self, authed_api_a, account, decision_cycle):
        resp = authed_api_a.get(
            _url(),
            {'account_id': str(account.id), 'decision_cycle_id': str(decision_cycle.id)},
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_scope_activity(self, authed_api_a, account, activity, user_a):
        # Signal on this activity + one on a different activity (same account).
        from app_modules.activities.models import Activity
        from app_modules.activities.constants import ActivityType, ActivityStatus
        other = Activity(
            title='Other call', activity_type=ActivityType.MEETING,
            status=ActivityStatus.COMPLETED, account=account, owner=user_a,
        )
        other.save(user=user_a, client_id=account.client_id)

        on_activity = _mk_pain(account, activity, user_a)
        _mk_impact(account, other, user_a)  # different activity

        resp = authed_api_a.get(_url(), {'activity_id': str(activity.id)})
        body = resp.json()
        assert body['count'] == 1
        assert body['results'][0]['id'] == str(on_activity.id)

    def test_signal_type_filter(self, authed_api_a, account, activity, user_a):
        _mk_pain(account, activity, user_a)
        _mk_impact(account, activity, user_a)
        _mk_tech(account, activity, user_a)

        resp = authed_api_a.get(
            _url(),
            # requests library serializes a list as repeated params
            {'account_id': str(account.id), 'signal_type': ['pain', 'impact']},
        )
        body = resp.json()
        assert body['count'] == 2
        assert {r['signal_type'] for r in body['results']} == {'pain', 'impact'}

    def test_multi_status_filter(self, authed_api_a, account, activity, user_a):
        from app_modules.signals.constants import SignalStatus
        p = _mk_pain(account, activity, user_a)      # will be PENDING
        v = _mk_impact(account, activity, user_a)    # will be VALIDATED
        r = _mk_blocker(account, activity, user_a)   # will be REJECTED
        PainSignal.objects.filter(id=p.id).update(status=SignalStatus.PENDING)
        ImpactSignal.objects.filter(id=v.id).update(status=SignalStatus.VALIDATED)
        BlockerSignal.objects.filter(id=r.id).update(status=SignalStatus.REJECTED)

        resp = authed_api_a.get(
            _url(),
            {'account_id': str(account.id), 'status': ['PENDING', 'VALIDATED']},
        )
        body = resp.json()
        assert body['count'] == 2
        assert {row['id'] for row in body['results']} == {str(p.id), str(v.id)}

    def test_ordering_status(self, authed_api_a, account, activity, user_a):
        # A VALIDATED pain (created newest) and a PENDING blocker (older).
        from app_modules.signals.constants import SignalStatus
        pending = _mk_blocker(account, activity, user_a)
        validated = _mk_pain(account, activity, user_a)
        BlockerSignal.objects.filter(id=pending.id).update(status=SignalStatus.PENDING)
        PainSignal.objects.filter(id=validated.id).update(status=SignalStatus.VALIDATED)

        resp = authed_api_a.get(
            _url(), {'account_id': str(account.id), 'ordering': 'status'},
        )
        rows = resp.json()['results']
        # PENDING (order 0) before VALIDATED (order 1), regardless of created_at.
        assert rows[0]['id'] == str(pending.id)
        assert rows[1]['id'] == str(validated.id)

    def test_polymorphic_completeness_all_eight_types(
        self, authed_api_a, account, activity, user_a,
    ):
        _mk_pain(account, activity, user_a)
        _mk_objective(account, activity, user_a)
        _mk_impact(account, activity, user_a)
        _mk_tech(account, activity, user_a)
        _mk_blocker(account, activity, user_a)
        _mk_nextstep(account, activity, user_a)
        _mk_people(account, activity, user_a)
        _mk_constraint(account, activity, user_a)

        resp = authed_api_a.get(_url(), {'account_id': str(account.id), 'page_size': 100})
        rows = resp.json()['results']
        by_type = {r['signal_type']: r for r in rows}
        assert set(by_type) == {
            'pain', 'objective', 'impact', 'tech-stack',
            'blockers', 'next-steps', 'people', 'constraints',
        }
        # Spot-check a few type-specific fields serialize via the endpoint.
        assert by_type['impact']['impact_type_display']
        assert by_type['tech-stack']['tech_name'] == 'Salesforce'
        assert by_type['next-steps']['suggested_title'] == 'Follow up'
        assert by_type['people']['role_display']
        assert by_type['constraints']['rigidity_display']

    def test_bounded_query_count(
        self, authed_api_a, account, activity, user_a, django_assert_max_num_queries,
    ):
        # Many rows of one type + a few others — the query count must stay
        # bounded (one queryset per type + pagination), NOT O(rows).
        for _ in range(25):
            _mk_pain(account, activity, user_a)
        _mk_impact(account, activity, user_a)
        _mk_tech(account, activity, user_a)

        with django_assert_max_num_queries(40):
            resp = authed_api_a.get(_url(), {'account_id': str(account.id), 'page_size': 20})
        assert resp.status_code == status.HTTP_200_OK
