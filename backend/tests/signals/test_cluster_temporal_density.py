# backend/tests/signals/test_cluster_temporal_density.py
"""
Tests for the FACTUAL temporal density fields on a signal cluster (C1).

The cluster payload exposes raw facts about how many signals it holds and
the period they cover — NOT a composite score:

  signal_count  — number of member signals (VALIDATED + PENDING)
  period_start  — first_observed_at (earliest member observation)
  period_end    — last_confirmed_at (latest member observation)
  span_days     — integer days between period_start and period_end
                  (0 for a single signal / same-day cluster)

These are pure facts (end - start), deliberately distinct from the
corroboration priority_score which is untouched here.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.signals.constants import (
    SignalDimension,
    SignalSource,
    SignalWhat,
)
from app_modules.signals.models import PainSignal
from app_modules.signals.serializers import SignalClusterListSerializer
from app_modules.signals.services import SignalClusterService


pytestmark = pytest.mark.django_db


# =============================================================================
# HELPERS
# =============================================================================

def _make_pain(account, activity, user_a, *, dimension, created_at=None):
    """
    Create a VALIDATED PainSignal (MANUAL source is force-validated in
    save()) on (OPS x <dimension>) so all signals sharing a dimension land
    in the same canonical cluster. When created_at is given, it is applied
    via .update() to bypass auto_now_add so the member's observation date
    can be placed in the past.
    """
    pain = PainSignal(
        account=account,
        source_activity=activity,
        what=SignalWhat.OPS,
        dimension=dimension,
        summary='Reporting is slow',
        source_quote='it takes hours every week',
        source=SignalSource.MANUAL,
    )
    pain.save(user=user_a, client_id=account.client_id)
    if created_at is not None:
        PainSignal.objects.filter(id=pain.id).update(created_at=created_at)
    return pain


def _cluster(account, *, dimension=SignalDimension.TIME):
    canonical_key = 'pain:%s:%s' % (SignalWhat.OPS, dimension)
    clusters = SignalClusterService.list_clusters_for_account(
        account_id=account.id,
        signal_type='pain',
    )
    match = [c for c in clusters if c['canonical_key'] == canonical_key]
    assert len(match) == 1, (
        'expected exactly one cluster for %s, got %s'
        % (canonical_key, [c['canonical_key'] for c in clusters])
    )
    return match[0]


# =============================================================================
# SINGLE MEMBER — span is zero, period collapses to one date
# =============================================================================

class TestSingleMemberCluster:

    def test_single_member_span_is_zero(self, account, activity, user_a):
        pain = _make_pain(
            account, activity, user_a, dimension=SignalDimension.TIME,
        )
        cluster = _cluster(account, dimension=SignalDimension.TIME)

        assert cluster['signal_count'] == 1
        assert cluster['period_start'] == cluster['period_end']
        assert cluster['period_start'] == pain.created_at
        assert cluster['span_days'] == 0

    def test_single_member_serializer_exposes_fields(
        self, account, activity, user_a,
    ):
        _make_pain(account, activity, user_a, dimension=SignalDimension.TIME)
        cluster = _cluster(account, dimension=SignalDimension.TIME)
        data = SignalClusterListSerializer(cluster).data

        assert data['signal_count'] == 1
        assert data['span_days'] == 0
        assert data['period_start'] is not None
        assert data['period_end'] is not None


# =============================================================================
# MULTIPLE MEMBERS SPREAD OVER TIME — count + true span
# =============================================================================

class TestMultiMemberSpread:

    def test_count_and_span_reflect_all_members(
        self, account, activity, user_a,
    ):
        now = timezone.now()
        earliest = now - timedelta(days=40)
        middle = now - timedelta(days=10)
        latest = now

        _make_pain(
            account, activity, user_a,
            dimension=SignalDimension.TIME, created_at=earliest,
        )
        _make_pain(
            account, activity, user_a,
            dimension=SignalDimension.TIME, created_at=middle,
        )
        _make_pain(
            account, activity, user_a,
            dimension=SignalDimension.TIME, created_at=latest,
        )

        cluster = _cluster(account, dimension=SignalDimension.TIME)

        assert cluster['signal_count'] == 3
        assert cluster['period_start'] == earliest
        assert cluster['period_end'] == latest
        assert cluster['span_days'] == 40


# =============================================================================
# SAME COUNT, DIFFERENT SPAN — proves it measures span, not count
# =============================================================================

class TestSpanIsNotJustCount:

    def test_two_clusters_same_count_differ_by_span(
        self, account, activity, user_a,
    ):
        now = timezone.now()

        # Cluster A (OPS x TIME): 2 signals, 2-day span.
        _make_pain(
            account, activity, user_a,
            dimension=SignalDimension.TIME, created_at=now - timedelta(days=2),
        )
        _make_pain(
            account, activity, user_a,
            dimension=SignalDimension.TIME, created_at=now,
        )

        # Cluster B (OPS x COST): 2 signals, 30-day span.
        _make_pain(
            account, activity, user_a,
            dimension=SignalDimension.COST, created_at=now - timedelta(days=30),
        )
        _make_pain(
            account, activity, user_a,
            dimension=SignalDimension.COST, created_at=now,
        )

        cluster_a = _cluster(account, dimension=SignalDimension.TIME)
        cluster_b = _cluster(account, dimension=SignalDimension.COST)

        # Same number of signals ...
        assert cluster_a['signal_count'] == cluster_b['signal_count'] == 2
        # ... but different covered periods.
        assert cluster_a['span_days'] == 2
        assert cluster_b['span_days'] == 30
        assert cluster_a['span_days'] != cluster_b['span_days']
