# backend/tests/signals/test_signal_counts_view.py
"""
Tests for GET /module-signals/by-activity/<activity_id>/counts/

Verifies aggregated signal counts (PENDING / VALIDATED / REJECTED)
broken down by signal type, tenant isolation, and 404 on unknown activity.
"""

import uuid

import pytest
from rest_framework import status as http_status

from app_modules.signals.constants import (
    SignalStatus,
    SignalSource,
    SignalWhat,
    SignalDimension,
    ScopeLevel,
    ImpactType,
)
from app_modules.signals.models import (
    PainSignal,
    ObjectiveSignal,
    ImpactSignal,
    TechStackSignal,
    BlockerSignal,
    NextStepSignal,
)
from app_modules.activities.constants import ActivityType


URL_TEMPLATE = '/module-signals/by-activity/{activity_id}/counts/'

ZERO_COUNTS = {'pending': 0, 'validated': 0, 'rejected': 0}

EMPTY_BY_TYPE = {
    'pain': ZERO_COUNTS.copy(),
    'objective': ZERO_COUNTS.copy(),
    'impact': ZERO_COUNTS.copy(),
    'tech_stack': ZERO_COUNTS.copy(),
    'blocker': ZERO_COUNTS.copy(),
    'next_step': ZERO_COUNTS.copy(),
}


def _url(activity_id):
    return URL_TEMPLATE.format(activity_id=activity_id)


def _make_pain(account, activity, user, *, source=SignalSource.LLM_EXTRACTED):
    sig = PainSignal(
        account=account,
        source_activity=activity,
        what=SignalWhat.OPS,
        dimension=SignalDimension.TIME,
        summary='Test pain',
        source=source,
    )
    sig.save(user=user, client_id=account.client_id)
    return sig


def _make_objective(account, activity, user, *, source=SignalSource.LLM_EXTRACTED):
    sig = ObjectiveSignal(
        account=account,
        source_activity=activity,
        what=SignalWhat.GROWTH,
        dimension=SignalDimension.COST,
        scope_level=ScopeLevel.BUSINESS,
        summary='Test objective',
        source=source,
    )
    sig.save(user=user, client_id=account.client_id)
    return sig


def _make_impact(account, activity, user, *, source=SignalSource.LLM_EXTRACTED):
    sig = ImpactSignal(
        account=account,
        source_activity=activity,
        what=SignalWhat.DATA,
        dimension=SignalDimension.QUALITY,
        scope_level=ScopeLevel.DEPARTMENT,
        impact_type=ImpactType.TIME,
        summary='Test impact',
        source=source,
    )
    sig.save(user=user, client_id=account.client_id)
    return sig


def _make_blocker(account, activity, user, *, source=SignalSource.LLM_EXTRACTED):
    sig = BlockerSignal(
        account=account,
        source_activity=activity,
        summary='Test blocker',
        source=source,
    )
    sig.save(user=user, client_id=account.client_id)
    return sig


def _make_next_step(account, activity, user, *, source=SignalSource.LLM_EXTRACTED):
    sig = NextStepSignal(
        account=account,
        source_activity=activity,
        suggested_title='Follow-up call',
        suggested_activity_type=ActivityType.MEETING,
        source=source,
    )
    sig.save(user=user, client_id=account.client_id)
    return sig


def _set_status(signal, new_status):
    type(signal).objects.filter(pk=signal.pk).update(status=new_status)


@pytest.mark.django_db
class TestSignalCountsByActivity:

    def test_zero_signals_returns_all_zeros(self, authed_api_a, activity):
        resp = authed_api_a.get(_url(activity.id))

        assert resp.status_code == http_status.HTTP_200_OK
        data = resp.json()
        assert data['pending'] == 0
        assert data['validated'] == 0
        assert data['rejected'] == 0
        assert data['by_type'] == EMPTY_BY_TYPE

    def test_mixed_statuses_counted_correctly(
        self, authed_api_a, activity, account, user_a,
    ):
        p1 = _make_pain(account, activity, user_a)
        p2 = _make_pain(account, activity, user_a)
        _set_status(p2, SignalStatus.VALIDATED)

        b1 = _make_blocker(account, activity, user_a)
        _set_status(b1, SignalStatus.REJECTED)

        _make_objective(account, activity, user_a)

        _make_next_step(account, activity, user_a)
        ns2 = _make_next_step(account, activity, user_a)
        _set_status(ns2, SignalStatus.VALIDATED)

        resp = authed_api_a.get(_url(activity.id))
        assert resp.status_code == http_status.HTTP_200_OK
        data = resp.json()

        assert data['pending'] == 3
        assert data['validated'] == 2
        assert data['rejected'] == 1

        assert data['by_type']['pain'] == {'pending': 1, 'validated': 1, 'rejected': 0}
        assert data['by_type']['blocker'] == {'pending': 0, 'validated': 0, 'rejected': 1}
        assert data['by_type']['objective'] == {'pending': 1, 'validated': 0, 'rejected': 0}
        assert data['by_type']['next_step'] == {'pending': 1, 'validated': 1, 'rejected': 0}
        assert data['by_type']['impact'] == ZERO_COUNTS
        assert data['by_type']['tech_stack'] == ZERO_COUNTS

    def test_activity_not_found_returns_404(self, authed_api_a):
        fake_id = uuid.uuid4()
        resp = authed_api_a.get(_url(fake_id))

        assert resp.status_code == http_status.HTTP_404_NOT_FOUND

    def test_tenant_isolation(
        self, authed_api_b, activity, account, user_a,
    ):
        _make_pain(account, activity, user_a)

        resp = authed_api_b.get(_url(activity.id))
        assert resp.status_code == http_status.HTTP_404_NOT_FOUND

    def test_by_type_keys_always_present(self, authed_api_a, activity):
        resp = authed_api_a.get(_url(activity.id))
        data = resp.json()

        expected_keys = {'pain', 'objective', 'impact', 'tech_stack', 'blocker', 'next_step'}
        assert set(data['by_type'].keys()) == expected_keys

    def test_manual_signals_counted_as_validated(
        self, authed_api_a, activity, account, user_a,
    ):
        _make_pain(account, activity, user_a, source=SignalSource.MANUAL)
        _make_blocker(account, activity, user_a, source=SignalSource.MANUAL)

        resp = authed_api_a.get(_url(activity.id))
        data = resp.json()

        assert data['pending'] == 0
        assert data['validated'] == 2
        assert data['rejected'] == 0
