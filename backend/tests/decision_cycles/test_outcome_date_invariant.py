# backend/tests/decision_cycles/test_outcome_date_invariant.py
"""
``DecisionCycle.outcome_date`` — the SINGLE close date, and its invariant.

Replaces the short-lived ``closed_at`` stamp (added and removed on this same
branch): one field, one write site, one clearing site, so a close date cannot
disagree with itself.

    INVARIANT: outcome_date is non-null IFF the cycle carries an outcome.

Written once at ``views/views.py:735`` — unconditionally, for every value the
close endpoint accepts — and cleared at ``:839`` on reopen. That is what lets a
won amount be selected by STATUS and windowed on this date: a reopened cycle
leaves the won population by both criteria at once.

ONE DEVIATION, pinned below rather than papered over: ``ON_HOLD`` also sets the
date, and ON_HOLD is NOT terminal. So the invariant holds as "non-null IFF an
outcome is set", not as "IFF the cycle is terminal". It costs the money metrics
nothing — they filter ``outcome=WON`` before ever looking at the date — but a
future reader that filters on the date ALONE would count paused deals as closed,
and the DC header already renders a paused cycle as "Closed {date}"
(frontend/src/sections/accounts/dc-workspace/DCWorkspaceHeader.jsx:291-302).

API-level tests drive the real close / reopen endpoints, mirroring
tests/decision_cycles/test_deal_product_api.py's use of ``authed_api_a``.
"""

import pytest
from django.utils import timezone
from rest_framework import status

from app_modules.decision_cycles.constants import CycleOutcome, TERMINAL_OUTCOMES
from app_modules.decision_cycles.models import DecisionCycle


pytestmark = pytest.mark.django_db


def _close_url(cycle_id):
    return f'/decision_cycles/{cycle_id}/close/'


def _reopen_url(cycle_id):
    return f'/decision_cycles/{cycle_id}/reopen/'


def _holds_the_invariant(cycle):
    """outcome_date is non-null exactly when an outcome is set."""
    return (cycle.outcome is not None) == (cycle.outcome_date is not None)


# ===========================================================================
# The invariant, through the real endpoints
# ===========================================================================

class TestInvariant:

    def test_an_open_cycle_has_no_close_date(self, cycle):
        assert cycle.outcome is None
        assert cycle.outcome_date is None
        assert _holds_the_invariant(cycle)

    @pytest.mark.parametrize('outcome', ['WON', 'LOST', 'NOT_QUALIFIED'])
    def test_closing_terminally_sets_the_close_date(
        self, authed_api_a, cycle, outcome,
    ):
        today = timezone.now().date()

        resp = authed_api_a.post(_close_url(cycle.id), {'outcome': outcome},
                                 format='json')

        assert resp.status_code == status.HTTP_200_OK
        cycle.refresh_from_db()
        assert cycle.outcome == outcome
        assert cycle.outcome_date == today
        assert _holds_the_invariant(cycle)

    def test_reopening_clears_the_close_date(self, authed_api_a, cycle):
        authed_api_a.post(_close_url(cycle.id), {'outcome': 'WON'}, format='json')
        cycle.refresh_from_db()
        assert cycle.outcome_date is not None

        resp = authed_api_a.post(_reopen_url(cycle.id), {}, format='json')

        assert resp.status_code == status.HTTP_200_OK
        cycle.refresh_from_db()
        assert cycle.outcome is None
        assert cycle.outcome_date is None
        assert _holds_the_invariant(cycle)

    def test_close_reopen_close_carries_the_latest_close_date(
        self, authed_api_a, cycle,
    ):
        authed_api_a.post(_close_url(cycle.id), {'outcome': 'WON'}, format='json')
        DecisionCycle.objects.filter(pk=cycle.pk).update(
            outcome_date=timezone.now().date() - timezone.timedelta(days=30)
        )
        authed_api_a.post(_reopen_url(cycle.id), {}, format='json')
        authed_api_a.post(_close_url(cycle.id), {'outcome': 'WON'}, format='json')

        cycle.refresh_from_db()
        assert cycle.outcome_date == timezone.now().date()   # the LATEST close
        assert _holds_the_invariant(cycle)

    def test_the_close_date_is_never_writable_by_a_client(
        self, authed_api_a, cycle,
    ):
        """It is read-only on every serializer — only close/reopen move it."""
        resp = authed_api_a.patch(
            f'/decision_cycles/{cycle.id}/',
            {'outcome_date': '2020-01-01'},
            format='json',
        )

        cycle.refresh_from_db()
        assert cycle.outcome_date is None
        assert resp.status_code in (status.HTTP_200_OK,
                                    status.HTTP_400_BAD_REQUEST)


# ===========================================================================
# The ON_HOLD deviation — documented, not hidden
# ===========================================================================

class TestOnHoldDeviation:

    def test_on_hold_also_sets_the_close_date_although_it_is_not_terminal(
        self, authed_api_a, cycle,
    ):
        tomorrow = timezone.now().date() + timezone.timedelta(days=1)

        resp = authed_api_a.post(
            _close_url(cycle.id),
            {'outcome': 'ON_HOLD', 'outcome_notes': 'paused',
             'hold_until': tomorrow.isoformat()},
            format='json',
        )

        assert resp.status_code == status.HTTP_200_OK
        cycle.refresh_from_db()
        assert cycle.outcome == CycleOutcome.ON_HOLD
        assert cycle.outcome not in TERMINAL_OUTCOMES        # not terminal ...
        assert cycle.outcome_date is not None                # ... yet dated
        assert _holds_the_invariant(cycle)                   # invariant as stated

    def test_a_paused_cycle_is_in_no_money_population(self, authed_api_a, cycle):
        """Why the deviation is harmless where it matters: every money read
        selects by outcome first, so a paused cycle is in neither pipeline
        (outcome is not NULL) nor won (outcome is not WON)."""
        tomorrow = timezone.now().date() + timezone.timedelta(days=1)
        authed_api_a.post(
            _close_url(cycle.id),
            {'outcome': 'ON_HOLD', 'outcome_notes': 'paused',
             'hold_until': tomorrow.isoformat()},
            format='json',
        )
        cycle.refresh_from_db()

        assert cycle.outcome is not None                     # out of pipeline
        assert cycle.outcome != CycleOutcome.WON             # out of won


# ===========================================================================
# closed_at is gone
# ===========================================================================

class TestClosedAtIsRemoved:

    def test_the_model_has_no_second_close_date(self):
        names = {f.name for f in DecisionCycle._meta.get_fields()}

        assert 'closed_at' not in names
        assert 'outcome_date' in names
        # no other date field claims to be a close date either
        assert not {n for n in names if n.startswith('closed')}
