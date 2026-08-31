# backend/tests/signals/test_competitor_backend_surfaces.py
"""
Backend surfaces for CompetitorSignal (sub-step 6.1): the aggregated
signals endpoint (GET /module-signals/all/) and the DC-only competitor
cluster (SignalClusterService), cloned on the ConstraintSignal tests.

Competitor is simpler than Constraint: no nature/rigidity/target_department/
scope. Its cluster groups on competitor_name_normalized (like TechStack),
DC-only (like Constraint).
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import CompetitorSignal
from app_modules.signals.serializers import (
    SignalClusterDetailSerializer,
    SignalClusterListSerializer,
)
from app_modules.signals.services import SignalClusterService


pytestmark = pytest.mark.django_db(transaction=True)


# =============================================================================
# HELPERS
# =============================================================================

def _mk_competitor(account, activity, decision_cycle, user_a, *,
                   competitor_name='Intercom', summary='Weighing Intercom',
                   source=SignalSource.MANUAL, source_quote='we also look at it'):
    sig = CompetitorSignal(
        account=account,
        source_activity=activity,
        decision_cycle=decision_cycle,
        competitor_name=competitor_name,
        summary=summary,
        source_quote=source_quote,
        source=source,
    )
    sig.save(user=user_a, client_id=account.client_id)
    return sig


def _list_competitor(account, decision_cycle=None, **kwargs):
    return SignalClusterService.list_clusters_for_account(
        account_id=account.id,
        signal_type='competitor',
        decision_cycle_id=(decision_cycle.id if decision_cycle else None),
        **kwargs,
    )


# =============================================================================
# AGGREGATED ENDPOINT — competitor appears in /all/
# =============================================================================

class TestCompetitorInAggregatedEndpoint:

    def _url(self):
        return reverse('module_signals:signal-all')

    def test_competitor_appears_in_aggregated_list(
        self, authed_api_a, account, activity, decision_cycle, user_a,
    ):
        _mk_competitor(
            account, activity, decision_cycle, user_a,
            competitor_name='Intercom', summary='Prospect evaluating Intercom',
            source_quote='we also look at Intercom instead of you',
        )

        resp = authed_api_a.get(self._url(), {
            'decision_cycle_id': str(decision_cycle.id),
        })
        assert resp.status_code == status.HTTP_200_OK

        rows = resp.json()['results']
        comp_rows = [r for r in rows if r['signal_type'] == 'competitor']
        assert len(comp_rows) == 1
        row = comp_rows[0]
        assert row['competitor_name'] == 'Intercom'
        assert row['summary'] == 'Prospect evaluating Intercom'
        assert row['source_quote'] == 'we also look at Intercom instead of you'
        assert row['status'] == SignalStatus.VALIDATED

    def test_rejected_competitor_excluded_by_default(
        self, authed_api_a, account, activity, decision_cycle, user_a,
    ):
        sig = _mk_competitor(account, activity, decision_cycle, user_a)
        # Move it to REJECTED (bypass save() lifecycle rules with a raw update).
        CompetitorSignal.objects.filter(id=sig.id).update(
            status=SignalStatus.REJECTED,
        )

        resp = authed_api_a.get(self._url(), {
            'decision_cycle_id': str(decision_cycle.id),
        })
        rows = resp.json()['results']
        assert [r for r in rows if r['signal_type'] == 'competitor'] == []

        # Explicit ?status=REJECTED surfaces it.
        resp2 = authed_api_a.get(self._url(), {
            'decision_cycle_id': str(decision_cycle.id),
            'status': 'REJECTED',
        })
        rows2 = resp2.json()['results']
        assert len([r for r in rows2 if r['signal_type'] == 'competitor']) == 1


# =============================================================================
# CLUSTER — group-by competitor_name_normalized, DC-only
# =============================================================================

class TestCompetitorCluster:

    def test_same_name_forms_one_cluster(
        self, account, activity, decision_cycle, user_a,
    ):
        # Same normalised key, different raw casing. The reference (headline)
        # is the most-recent-validated member — the second one created here.
        _mk_competitor(account, activity, decision_cycle, user_a,
                       competitor_name='intercom')
        _mk_competitor(account, activity, decision_cycle, user_a,
                       competitor_name='Intercom')  # newest -> the headline

        clusters = _list_competitor(account, decision_cycle)

        assert len(clusters) == 1
        cluster = clusters[0]
        assert cluster['canonical_key'] == 'intercom'
        assert cluster['signal_type'] == 'competitor'
        assert cluster['signal_count'] == 2
        # Title = the raw competitor_name of the reference (most-recent-validated).
        assert cluster['summary'] == 'Intercom'

    def test_different_names_form_distinct_clusters(
        self, account, activity, decision_cycle, user_a,
    ):
        _mk_competitor(account, activity, decision_cycle, user_a,
                       competitor_name='Intercom')
        _mk_competitor(account, activity, decision_cycle, user_a,
                       competitor_name='Zendesk')

        clusters = _list_competitor(account, decision_cycle)
        assert sorted(c['canonical_key'] for c in clusters) == [
            'intercom', 'zendesk',
        ]

    def test_dc_only_no_cycle_returns_empty(
        self, account, activity, decision_cycle, user_a,
    ):
        _mk_competitor(account, activity, decision_cycle, user_a)
        # Account-level (no decision_cycle_id) -> DC-only -> [].
        assert _list_competitor(account, None) == []
        # Scoped to the DC it appears.
        assert len(_list_competitor(account, decision_cycle)) == 1

    def test_cluster_list_serializer_renders_competitor_cluster(
        self, account, activity, decision_cycle, user_a,
    ):
        _mk_competitor(account, activity, decision_cycle, user_a,
                       competitor_name='Intercom')
        cluster = _list_competitor(account, decision_cycle)[0]

        data = SignalClusterListSerializer(cluster).data
        assert data['signal_type'] == 'competitor'
        assert data['canonical_key'] == 'intercom'

    def test_detail_returns_members(
        self, account, activity, decision_cycle, user_a,
    ):
        _mk_competitor(account, activity, decision_cycle, user_a,
                       competitor_name='Intercom', summary='first')
        _mk_competitor(account, activity, decision_cycle, user_a,
                       competitor_name='Intercom', summary='second')

        detail = SignalClusterService.get_cluster_detail(
            account_id=account.id,
            canonical_key='intercom',
            signal_type='competitor',
            decision_cycle_id=decision_cycle.id,
        )
        data = SignalClusterDetailSerializer(detail).data
        assert len(data['members']) == 2
        assert all(m['competitor_name'] == 'Intercom' for m in data['members'])
