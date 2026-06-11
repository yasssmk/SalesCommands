# backend/tests/decision_cycles/test_deal_health_snapshot.py
"""
Model-level tests for DealHealthSnapshot.
"""

import pytest


pytestmark = pytest.mark.django_db


class TestDealHealthSnapshotCreate:

    def test_create(self, cycle, user_a):
        from app_modules.decision_cycles.models import DealHealthSnapshot

        snap = DealHealthSnapshot(
            decision_cycle=cycle,
            diagnostic={'dimensions': [], 'gaps': []},
        )
        snap.save(user=user_a, client_id=cycle.client_id)

        assert snap.pk is not None
        assert snap.snapshot_date is not None
        assert snap.pipeline_run is None
        assert snap.diagnostic == {'dimensions': [], 'gaps': []}

    def test_str(self, deal_health_snapshot):
        s = str(deal_health_snapshot)
        assert 'Test Cycle' in s


class TestDealHealthSnapshotOrdering:

    def test_latest_first(self, cycle, user_a):
        from app_modules.decision_cycles.models import DealHealthSnapshot
        import datetime

        snap1 = DealHealthSnapshot(
            decision_cycle=cycle,
            diagnostic={'v': 1},
        )
        snap1.save(user=user_a, client_id=cycle.client_id)

        snap2 = DealHealthSnapshot(
            decision_cycle=cycle,
            diagnostic={'v': 2},
        )
        snap2.save(user=user_a, client_id=cycle.client_id)

        snapshots = list(
            DealHealthSnapshot.objects.filter(decision_cycle=cycle)
        )
        assert snapshots[0].pk == snap2.pk

    def test_latest_query(self, cycle, user_a):
        from app_modules.decision_cycles.models import DealHealthSnapshot

        DealHealthSnapshot(
            decision_cycle=cycle,
            diagnostic={'v': 1},
        ).save(user=user_a, client_id=cycle.client_id)

        DealHealthSnapshot(
            decision_cycle=cycle,
            diagnostic={'v': 2},
        ).save(user=user_a, client_id=cycle.client_id)

        latest = (
            DealHealthSnapshot.objects
            .filter(decision_cycle=cycle)
            .first()
        )
        assert latest.diagnostic == {'v': 2}


class TestDealHealthSnapshotCascade:

    def test_cascade_on_cycle_delete(self, deal_health_snapshot, cycle):
        from app_modules.decision_cycles.models import DealHealthSnapshot

        snap_id = deal_health_snapshot.pk
        cycle.delete()
        assert not DealHealthSnapshot.objects.filter(pk=snap_id).exists()
