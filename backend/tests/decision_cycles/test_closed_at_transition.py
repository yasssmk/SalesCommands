# backend/tests/decision_cycles/test_closed_at_transition.py
"""
``DecisionCycle.closed_at`` — the WON-transition stamp.

Stamped by ``DecisionCycle.save()`` (models.py, ``_stamp_closed_at_on_won_transition``)
rather than by the close endpoint, so EVERY write path reaches it: the API
(views/views.py:734, the only production writer of ``outcome``), a shell fix, a
data migration, a future service.

Rules pinned here:
- stamped when the cycle ENTERS the WON outcome, never before;
- a cycle saved again while already WON keeps its original stamp (idempotent);
- reopening leaves the stamp alone, and re-winning OVERWRITES it with the later
  time (the latest close wins, per the PO rule);
- a cycle closed LOST / ON_HOLD / NOT_QUALIFIED is never stamped;
- the field is not writable through the API (``editable=False``), so the
  transition is the only way in.

The API-level tests drive the real close endpoint, mirroring
tests/decision_cycles/test_deal_product_api.py's use of ``authed_api_a``.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status

from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle


pytestmark = pytest.mark.django_db


def _close_url(cycle_id):
    return f'/decision_cycles/{cycle_id}/close/'


def _reopen_url(cycle_id):
    return f'/decision_cycles/{cycle_id}/reopen/'


# ===========================================================================
# The model-level transition
# ===========================================================================

class TestTransitionStamp:

    def test_a_new_open_cycle_has_no_stamp(self, cycle):
        assert cycle.outcome is None
        assert cycle.closed_at is None

    def test_saving_an_open_cycle_never_stamps_it(self, cycle, user_a):
        cycle.name = 'renamed'
        cycle.save(user=user_a)

        cycle.refresh_from_db()
        assert cycle.closed_at is None

    def test_transition_to_won_stamps_it(self, cycle, user_a):
        before = timezone.now()

        cycle.outcome = CycleOutcome.WON
        cycle.outcome_date = timezone.now().date()
        cycle.save(user=user_a)

        cycle.refresh_from_db()
        assert cycle.closed_at is not None
        assert before <= cycle.closed_at <= timezone.now()

    def test_a_cycle_created_directly_as_won_is_stamped(self, account, user_a):
        won = DecisionCycle(account=account, owner=user_a, name='born-won',
                            outcome=CycleOutcome.WON,
                            outcome_date=timezone.now().date())
        won.save(user=user_a, client_id=account.client_id)

        won.refresh_from_db()
        assert won.closed_at is not None

    def test_saving_an_already_won_cycle_keeps_the_original_stamp(
        self, cycle, user_a,
    ):
        cycle.outcome = CycleOutcome.WON
        cycle.save(user=user_a)
        first_stamp = DecisionCycle.objects.get(pk=cycle.pk).closed_at

        reloaded = DecisionCycle.objects.get(pk=cycle.pk)
        reloaded.name = 'touched again'
        reloaded.save(user=user_a)

        assert DecisionCycle.objects.get(pk=cycle.pk).closed_at == first_stamp

    def test_lost_and_on_hold_are_never_stamped(self, account, user_a):
        for outcome in (CycleOutcome.LOST, CycleOutcome.ON_HOLD,
                        CycleOutcome.NOT_QUALIFIED):
            dc = DecisionCycle(account=account, owner=user_a, name=f'dc-{outcome}',
                               outcome=outcome,
                               outcome_date=timezone.now().date())
            dc.save(user=user_a, client_id=account.client_id)

            dc.refresh_from_db()
            assert dc.closed_at is None, outcome

    def test_re_winning_after_a_reopen_overwrites_with_the_later_time(
        self, cycle, user_a,
    ):
        cycle.outcome = CycleOutcome.WON
        cycle.save(user=user_a)
        first_stamp = DecisionCycle.objects.get(pk=cycle.pk).closed_at

        # Reopen: the stamp is deliberately left in place ...
        reopened = DecisionCycle.objects.get(pk=cycle.pk)
        reopened.outcome = None
        reopened.outcome_date = None
        reopened.save(user=user_a)
        assert DecisionCycle.objects.get(pk=cycle.pk).closed_at == first_stamp

        # ... and the next win overwrites it with the LATER close.
        rewon = DecisionCycle.objects.get(pk=cycle.pk)
        rewon.outcome = CycleOutcome.WON
        rewon.save(user=user_a)

        second_stamp = DecisionCycle.objects.get(pk=cycle.pk).closed_at
        assert second_stamp > first_stamp

    def test_a_targeted_update_fields_save_still_persists_the_stamp(
        self, cycle, user_a,
    ):
        """save(update_fields=['outcome']) must not drop the stamp."""
        cycle.outcome = CycleOutcome.WON
        cycle.save(user=user_a, update_fields=['outcome'])

        cycle.refresh_from_db()
        assert cycle.closed_at is not None

    def test_the_field_is_not_editable_through_a_form_or_serializer(self):
        assert DecisionCycle._meta.get_field('closed_at').editable is False


# ===========================================================================
# Through the real close / reopen endpoints
# ===========================================================================

class TestCloseEndpointStamps:

    def test_closing_as_won_stamps_closed_at(self, authed_api_a, cycle):
        before = timezone.now()

        resp = authed_api_a.post(_close_url(cycle.id), {'outcome': 'WON'},
                                 format='json')

        assert resp.status_code == status.HTTP_200_OK
        cycle.refresh_from_db()
        assert cycle.closed_at is not None
        assert before <= cycle.closed_at <= timezone.now()

    def test_closing_as_lost_does_not_stamp(self, authed_api_a, cycle):
        resp = authed_api_a.post(_close_url(cycle.id), {'outcome': 'LOST'},
                                 format='json')

        assert resp.status_code == status.HTTP_200_OK
        cycle.refresh_from_db()
        assert cycle.closed_at is None

    def test_close_reopen_close_keeps_the_latest_stamp(self, authed_api_a, cycle):
        authed_api_a.post(_close_url(cycle.id), {'outcome': 'WON'}, format='json')
        cycle.refresh_from_db()
        first_stamp = cycle.closed_at

        # Backdate the first stamp so the comparison cannot be a clock tie.
        DecisionCycle.objects.filter(pk=cycle.pk).update(
            closed_at=first_stamp - timedelta(days=3)
        )

        authed_api_a.post(_reopen_url(cycle.id), {}, format='json')
        authed_api_a.post(_close_url(cycle.id), {'outcome': 'WON'}, format='json')

        cycle.refresh_from_db()
        assert cycle.closed_at > first_stamp - timedelta(days=3)
        assert cycle.outcome == CycleOutcome.WON
