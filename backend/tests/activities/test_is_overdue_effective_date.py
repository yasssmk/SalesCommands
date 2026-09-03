# backend/tests/activities/test_is_overdue_effective_date.py
"""
R3 — Activity.is_overdue must use the EFFECTIVE date (scheduled_date if present,
else due_date), matching the canonical rule already used by step-status
derivation (_is_activity_overdue). A PLANNED activity whose scheduled_date is in
the past is overdue even when it has no due_date — the case the header used to
miss because is_overdue was due_date-only.

These are pure-property unit tests: is_overdue only reads status/scheduled_date/
due_date and today's date, so an in-memory Activity (no DB) is enough.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity

TODAY = timezone.now().date()
PAST = TODAY - timedelta(days=3)
FUTURE = TODAY + timedelta(days=3)

_CREATE_URL = '/module-activities/create-with-entities/'


def _act(**kw):
    """An in-memory Activity carrying only the fields is_overdue reads."""
    return Activity(**kw)


class TestIsOverdueEffectiveDate:
    def test_scheduled_only_past_is_overdue(self):
        # THE regression: scheduled in the past, no due_date -> overdue.
        act = _act(status=ActivityStatus.PLANNED, scheduled_date=PAST, due_date=None)
        assert act.is_overdue is True

    def test_scheduled_only_today_is_not_overdue(self):
        # Date comparison, not datetime: today is not yet overdue.
        act = _act(status=ActivityStatus.PLANNED, scheduled_date=TODAY, due_date=None)
        assert act.is_overdue is False

    def test_scheduled_only_future_is_not_overdue(self):
        act = _act(status=ActivityStatus.PLANNED, scheduled_date=FUTURE, due_date=None)
        assert act.is_overdue is False

    def test_due_date_past_is_overdue_no_regression(self):
        # Existing behaviour preserved.
        act = _act(status=ActivityStatus.PLANNED, scheduled_date=None, due_date=PAST)
        assert act.is_overdue is True

    def test_due_date_today_is_not_overdue(self):
        act = _act(status=ActivityStatus.PLANNED, scheduled_date=None, due_date=TODAY)
        assert act.is_overdue is False

    def test_completed_with_past_dates_is_not_overdue(self):
        act = _act(status=ActivityStatus.COMPLETED, scheduled_date=PAST, due_date=PAST)
        assert act.is_overdue is False

    def test_cancelled_with_past_scheduled_is_not_overdue(self):
        act = _act(status=ActivityStatus.CANCELLED, scheduled_date=PAST, due_date=None)
        assert act.is_overdue is False

    def test_no_dates_is_not_overdue(self):
        act = _act(status=ActivityStatus.PLANNED, scheduled_date=None, due_date=None)
        assert act.is_overdue is False


@pytest.mark.django_db
class TestIsOverdueSerializerPath:
    """The REAL path the header reads: create a scheduled-only (no due_date)
    activity in the past — the DC case — and confirm the detail payload
    (ActivitySerializer.is_overdue, a BooleanField bound to the property) is
    True."""

    def test_scheduled_only_overdue_is_true_in_detail_payload(self, authed_api_a, account):
        past = TODAY - timedelta(days=7)
        payload = {
            'activity': {
                'title': 'Scheduled late',
                'activity_type': ActivityType.CALL,
                'status': ActivityStatus.PLANNED,
                'account_id': str(account.id),
                'contact_ids': [],
                'decision_step_id': None,
                'scheduled_date': past.isoformat(),  # no due_date -> the DC case
            },
            'inline_cycle': {'name': 'Cycle late', 'description': None},
            'inline_step_stage': 'QUALIFICATION',
        }
        resp = authed_api_a.post(_CREATE_URL, payload, format='json')
        assert resp.status_code == status.HTTP_201_CREATED, resp.content
        assert resp.json()['data']['activity']['is_overdue'] is True
