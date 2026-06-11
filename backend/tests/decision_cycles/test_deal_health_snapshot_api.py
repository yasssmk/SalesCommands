# tests/decision_cycles/test_deal_health_snapshot_api.py
"""
Integration tests for DealHealthSnapshot API endpoints (read-only).

Snapshots are created via ORM (the pipeline creates them, not the user).
Verifies list, retrieve, latest, write-blocking, and cross-tenant isolation.
"""

import uuid

import pytest
from rest_framework import status


def _snapshots_url(cycle_id):
    return f'/decision-cycles/{cycle_id}/health-snapshots/'


def _snapshot_detail_url(cycle_id, snapshot_id):
    return f'/decision-cycles/{cycle_id}/health-snapshots/{snapshot_id}/'


def _snapshot_latest_url(cycle_id):
    return f'/decision-cycles/{cycle_id}/health-snapshots/latest/'


# =============================================================================
# LIST
# =============================================================================


@pytest.mark.django_db
class TestDealHealthSnapshotList:

    def test_list_snapshots(self, authed_api_a, cycle, deal_health_snapshot):
        resp = authed_api_a.get(_snapshots_url(cycle.id))
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()['data']
        assert len(data) == 1
        assert data[0]['id'] == str(deal_health_snapshot.id)

    def test_list_empty(self, authed_api_a, cycle):
        resp = authed_api_a.get(_snapshots_url(cycle.id))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data'] == []


# =============================================================================
# RETRIEVE
# =============================================================================


@pytest.mark.django_db
class TestDealHealthSnapshotRetrieve:

    def test_retrieve_snapshot(self, authed_api_a, cycle, deal_health_snapshot):
        resp = authed_api_a.get(
            _snapshot_detail_url(cycle.id, deal_health_snapshot.id)
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()['data']
        assert data['id'] == str(deal_health_snapshot.id)
        assert 'diagnostic' in data

    def test_retrieve_nonexistent_returns_404(self, authed_api_a, cycle):
        fake_id = uuid.uuid4()
        resp = authed_api_a.get(_snapshot_detail_url(cycle.id, fake_id))
        assert resp.status_code in (
            status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN
        )


# =============================================================================
# LATEST
# =============================================================================


@pytest.mark.django_db
class TestDealHealthSnapshotLatest:

    def test_latest_returns_most_recent(self, authed_api_a, cycle, user_a):
        from app_modules.decision_cycles.models import DealHealthSnapshot

        snap1 = DealHealthSnapshot(
            decision_cycle=cycle,
            diagnostic={'global_diagnostic': 'First', 'dimensions': []},
        )
        snap1.save(user=user_a, client_id=cycle.client_id)

        snap2 = DealHealthSnapshot(
            decision_cycle=cycle,
            diagnostic={'global_diagnostic': 'Second', 'dimensions': []},
        )
        snap2.save(user=user_a, client_id=cycle.client_id)

        resp = authed_api_a.get(_snapshot_latest_url(cycle.id))
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()['data']
        assert data['id'] == str(snap2.id)

    def test_latest_returns_null_when_empty(self, authed_api_a, cycle):
        resp = authed_api_a.get(_snapshot_latest_url(cycle.id))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data'] is None


# =============================================================================
# WRITE OPERATIONS — blocked
# =============================================================================


@pytest.mark.django_db
class TestDealHealthSnapshotWriteBlocked:

    def test_create_blocked(self, authed_api_a, cycle):
        resp = authed_api_a.post(
            _snapshots_url(cycle.id),
            {'diagnostic': {}},
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_blocked(self, authed_api_a, cycle, deal_health_snapshot):
        resp = authed_api_a.delete(
            _snapshot_detail_url(cycle.id, deal_health_snapshot.id)
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# ISOLATION
# =============================================================================


@pytest.mark.django_db
class TestDealHealthSnapshotIsolation:

    def test_tenant_b_cannot_access_tenant_a_snapshots(
        self, authed_api_b, cycle, deal_health_snapshot
    ):
        resp = authed_api_b.get(_snapshots_url(cycle.id))
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_snapshot_not_visible_from_other_cycle(
        self, authed_api_a, cycle, deal_health_snapshot, account, user_a
    ):
        from app_modules.decision_cycles.models import DecisionCycle
        other_cycle = DecisionCycle(
            account=account, owner=user_a, name='Other Cycle', is_active=False,
        )
        other_cycle.save(user=user_a, client_id=account.client_id)

        resp = authed_api_a.get(_snapshots_url(other_cycle.id))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data'] == []
