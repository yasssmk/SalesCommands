# backend/tests/quotas/test_quota_create_validation.py
"""
Create-time validation on the objectives endpoint: a start date in the past is
rejected on CREATE, but an already-running objective stays editable.
"""

from datetime import date, timedelta

import pytest

from app_modules.bi.metrics import MetricKey
from app_modules.quotas.models import Quota


URL = '/quotas/quotas/'
TODAY = date.today()


@pytest.mark.django_db
class TestCreateDateValidation:

    def _payload(self, start, end, metric=MetricKey.MEETINGS):
        return {
            'metric': metric,
            'target_value': '10.00',
            'period_start': start.isoformat(),
            'period_end': end.isoformat(),
        }

    def test_future_start_is_accepted(self, authed_api_a):
        resp = authed_api_a.post(
            URL, self._payload(TODAY + timedelta(days=5), TODAY + timedelta(days=40)),
            format='json',
        )
        assert resp.status_code in (200, 201), resp.content

    def test_today_start_is_accepted(self, authed_api_a):
        resp = authed_api_a.post(
            URL, self._payload(TODAY, TODAY + timedelta(days=40)), format='json',
        )
        assert resp.status_code in (200, 201), resp.content

    def test_past_start_is_rejected(self, authed_api_a):
        resp = authed_api_a.post(
            URL, self._payload(TODAY - timedelta(days=1), TODAY + timedelta(days=40)),
            format='json',
        )
        assert resp.status_code == 400, resp.content

    def test_edit_of_past_started_objective_is_allowed(self, authed_api_a, user_a, client_account_a):
        # An objective whose start is already in the past (created directly).
        q = Quota(
            owner=user_a, metric=MetricKey.MEETINGS, target_value=10,
            period_start=TODAY - timedelta(days=30), period_end=TODAY + timedelta(days=30),
        )
        q.save(user=user_a, client_id=client_account_a.id)

        # PATCH another field — the past start must NOT block the edit.
        resp = authed_api_a.patch(f'{URL}{q.id}/', {'target_value': '20.00'}, format='json')
        assert resp.status_code == 200, resp.content
        q.refresh_from_db()
        assert str(q.target_value) == '20.00'
