# backend/tests/signals/test_nextstep_attach_activity.py
"""
Sprint Next steps 2.4 — linking a next step to an EXISTING activity.

POST /module-signals/next-steps/{id}/attach-activity/
     {activity_id, updates}

  * the activity must be a link candidate: an OPEN activity of the next
    step's decision cycle, same tenant, not its own conversation;
  * `updates` = the changes the rep chose on the differences screen
    (NEXT_STEP_LINK_UPDATE_FIELDS: type, dates, step, objective, description
    — final texts — and contacts to ADD); applied through
    ActivityUpdateSerializer (same validations, campaign lock COND-1
    included); no other field of the activity is touched;
  * ONE transaction: updates, attached_activity, then the signal validated
    LAST (2.1 invariants) — any refusal leaves everything unchanged.

The differences next step ↔ activity are exposed on each link candidate
(GET .../link-candidates/), by section; a section without difference is
absent.
"""

import datetime
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.signals.constants import PeopleRole, SignalSource, SignalStatus
from app_modules.signals.models import NextStepSignal, PeopleSignal
from core.error_messages import ActivityErrorMessages, SignalErrorMessages


pytestmark = pytest.mark.django_db


def _attach_url(pk):
    return reverse('module_signals:next-step-attach-activity', kwargs={'pk': pk})


def _candidates_url(pk):
    return reverse('module_signals:next-step-link-candidates', kwargs={'pk': pk})


def _error_text(response):
    error = response.json()['error']
    return ' '.join(error) if isinstance(error, list) else error


def _step(cycle, user, order):
    from app_modules.decision_cycles.models import DecisionStep
    step = DecisionStep(cycle=cycle, name=f'Step {order}', order=order)
    step.save(user=user, client_id=cycle.client_id)
    return step


def _contact(account, user, last_name):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name='X', last_name=last_name)
    c.save(user=user, client_id=account.client_id)
    return c


def _snapshot(activity):
    """Every field the link could wrongly touch."""
    activity.refresh_from_db()
    return {
        'title': activity.title, 'activity_type': activity.activity_type,
        'status': activity.status, 'description': activity.description,
        'call_to_action': activity.call_to_action,
        'scheduled_date': activity.scheduled_date, 'due_date': activity.due_date,
        'owner_id': activity.owner_id, 'decision_step_id': activity.decision_step_id,
        'decision_cycle_id': activity.decision_cycle_id,
        'contacts': sorted(str(c) for c in activity.contacts.values_list('id', flat=True)),
        'invited': sorted(str(u) for u in activity.invited_users.values_list('id', flat=True)),
        'next_step_signal_id': activity.next_step_signal_id,
    }


@pytest.fixture
def world(account, activity, decision_cycle, user_a):
    from app_modules.activities.models import Activity
    s1, s2 = _step(decision_cycle, user_a, 1), _step(decision_cycle, user_a, 2)
    thomas, laurent = _contact(account, user_a, 'Lefèvre'), _contact(account, user_a, 'Petit')
    target = Activity(
        title='Revue sécurité', activity_type=ActivityType.CALL,
        status=ActivityStatus.PLANNED, account=account, owner=user_a,
        decision_cycle=decision_cycle, decision_step=s1,
        description='Ordre du jour initial', call_to_action='Objectif initial',
        scheduled_date=datetime.date(2026, 11, 20),
    )
    target.save(user=user_a, client_id=account.client_id)
    target.contacts.set([thomas])
    people = PeopleSignal(
        account=account, source_activity=activity, full_name='Laurent Petit',
        role=PeopleRole.UNKNOWN, source=SignalSource.LLM_EXTRACTED,
        target_contact=laurent,
    )
    people.save(user=user_a, client_id=account.client_id)
    ns = NextStepSignal(
        account=account, source_activity=activity, decision_cycle=decision_cycle,
        suggested_title='Revue sécurité avec le DSI',
        suggested_activity_type=ActivityType.MEETING,
        suggested_due_date=datetime.date(2026, 11, 3),
        suggested_decision_step=s2,
        suggested_objective='Lever le blocage sécurité',
        suggested_topics='Hébergement UE, DPA',
        source=SignalSource.LLM_EXTRACTED, confidence=0.8,
    )
    ns.save(user=user_a, client_id=account.client_id)
    ns.suggested_people.set([people])
    return {'ns': ns, 'target': target, 's1': s1, 's2': s2,
            'thomas': thomas, 'laurent': laurent}


# =============================================================================
# Attach — happy paths
# =============================================================================

class TestAttach:

    def test_attach_without_updates_touches_nothing_on_the_activity(
        self, authed_api_a, world,
    ):
        ns, target = world['ns'], world['target']
        before = _snapshot(target)

        response = authed_api_a.post(
            _attach_url(ns.id), {'activity_id': str(target.id)}, format='json',
        )

        assert response.status_code == status.HTTP_200_OK, response.content
        ns.refresh_from_db()
        assert ns.status == SignalStatus.VALIDATED
        assert ns.attached_activity_id == target.id
        assert _snapshot(target) == before
        assert response.json()['data']['attached_activity']['id'] == str(target.id)

    def test_attach_applies_only_the_chosen_updates(self, authed_api_a, world):
        ns, target = world['ns'], world['target']
        before = _snapshot(target)

        response = authed_api_a.post(_attach_url(ns.id), {
            'activity_id': str(target.id),
            'updates': {
                'activity_type': 'MEETING',
                'scheduled_date': '2026-11-03',
                'decision_step_id': str(world['s2'].id),
                'call_to_action': 'Objectif initial\n\nLever le blocage sécurité',
                'description': 'Ordre du jour initial\n\nHébergement UE, DPA',
                'add_contact_ids': [str(world['laurent'].id)],
            },
        }, format='json')

        assert response.status_code == status.HTTP_200_OK, response.content
        after = _snapshot(target)
        assert after['activity_type'] == 'MEETING'
        assert after['scheduled_date'] == datetime.date(2026, 11, 3)
        assert after['decision_step_id'] == world['s2'].id
        assert after['call_to_action'] == 'Objectif initial\n\nLever le blocage sécurité'
        assert after['description'] == 'Ordre du jour initial\n\nHébergement UE, DPA'
        assert after['contacts'] == sorted(
            [str(world['thomas'].id), str(world['laurent'].id)]
        )
        # Nothing else moved.
        for field in ('title', 'status', 'owner_id', 'due_date', 'decision_cycle_id',
                      'invited', 'next_step_signal_id'):
            assert after[field] == before[field], field
        ns.refresh_from_db()
        assert ns.status == SignalStatus.VALIDATED


# =============================================================================
# Attach — refusals leave EVERYTHING unchanged
# =============================================================================

class TestAttachRefusals:

    def _assert_nothing_changed(self, ns, target, before):
        ns.refresh_from_db()
        assert ns.status == SignalStatus.PENDING
        assert ns.attached_activity_id is None
        assert _snapshot(target) == before

    def test_an_invalid_update_rolls_everything_back(
        self, authed_api_a, account, user_a, world,
    ):
        from app_modules.decision_cycles.models import DecisionCycle
        ns, target = world['ns'], world['target']
        before = _snapshot(target)
        other = DecisionCycle(account=account, owner=user_a, name='Other', is_active=True)
        other.save(user=user_a, client_id=account.client_id)
        foreign_step = _step(other, user_a, 1)

        response = authed_api_a.post(_attach_url(ns.id), {
            'activity_id': str(target.id),
            'updates': {
                'description': 'would be written first',
                'decision_step_id': str(foreign_step.id),
            },
        }, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self._assert_nothing_changed(ns, target, before)

    def test_a_field_outside_the_differences_is_refused(self, authed_api_a, world):
        ns, target = world['ns'], world['target']
        before = _snapshot(target)

        response = authed_api_a.post(_attach_url(ns.id), {
            'activity_id': str(target.id),
            'updates': {'title': 'renamed by the link', 'status': 'COMPLETED'},
        }, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert _error_text(response) == str(
            SignalErrorMessages.NEXT_STEP_LINK_UPDATE_NOT_ALLOWED
        )
        self._assert_nothing_changed(ns, target, before)

    def test_campaign_lock_cond1_applies(
        self, authed_api_a, account, user_a, client_account_a, world,
    ):
        from app_modules.activities.models import Activity
        from app_modules.campaigns.constants import CampaignStatus, CampaignType
        from app_modules.campaigns.models import Campaign
        today = timezone.now().date()
        campaign = Campaign(
            name='Q4 Outbound', campaign_type=CampaignType.OUTBOUND,
            status=CampaignStatus.DRAFT, owner=user_a,
            planned_start_date=today, planned_end_date=today + timedelta(days=30),
        )
        campaign.save(user=user_a, client_id=client_account_a.id)
        campaign_activity = Activity(
            title='Sequence step', activity_type=ActivityType.CALL,
            status=ActivityStatus.PLANNED, account=account, owner=user_a,
            campaign=campaign, decision_cycle=world['ns'].decision_cycle,
            decision_step=world['s1'], scheduled_date=today + timedelta(days=1),
        )
        campaign_activity.save(user=user_a, client_id=account.client_id)
        before = _snapshot(campaign_activity)

        response = authed_api_a.post(_attach_url(world['ns'].id), {
            'activity_id': str(campaign_activity.id),
            'updates': {'scheduled_date': '2026-11-03'},
        }, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'set by the campaign' in _error_text(response)
        self._assert_nothing_changed(world['ns'], campaign_activity, before)

    @pytest.mark.parametrize('case', ['completed', 'other_cycle', 'own_conversation'])
    def test_the_activity_must_be_a_link_candidate(
        self, authed_api_a, account, activity, user_a, world, case,
    ):
        from app_modules.activities.models import Activity
        from app_modules.decision_cycles.models import DecisionCycle
        ns = world['ns']
        if case == 'completed':
            bad = Activity(
                title='done', activity_type=ActivityType.CALL,
                status=ActivityStatus.COMPLETED, account=account, owner=user_a,
                decision_cycle=ns.decision_cycle, decision_step=world['s1'],
                scheduled_date=datetime.date(2026, 10, 1),
            )
            bad.save(user=user_a, client_id=account.client_id)
        elif case == 'other_cycle':
            other = DecisionCycle(account=account, owner=user_a, name='Other', is_active=True)
            other.save(user=user_a, client_id=account.client_id)
            bad = Activity(
                title='elsewhere', activity_type=ActivityType.CALL,
                status=ActivityStatus.PLANNED, account=account, owner=user_a,
                decision_cycle=other, decision_step=_step(other, user_a, 1),
                scheduled_date=datetime.date(2026, 11, 20),
            )
            bad.save(user=user_a, client_id=account.client_id)
        else:
            bad = activity
            bad.decision_cycle = ns.decision_cycle
            bad.status = ActivityStatus.PLANNED
            bad.save()

        response = authed_api_a.post(
            _attach_url(ns.id), {'activity_id': str(bad.id)}, format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert _error_text(response) == str(SignalErrorMessages.NEXT_STEP_LINK_TARGET_INVALID)
        ns.refresh_from_db()
        assert ns.status == SignalStatus.PENDING and ns.attached_activity_id is None

    def test_an_already_resolved_next_step_cannot_be_linked_again(
        self, authed_api_a, world,
    ):
        ns, target = world['ns'], world['target']
        first = authed_api_a.post(
            _attach_url(ns.id), {'activity_id': str(target.id)}, format='json',
        )
        assert first.status_code == 200

        again = authed_api_a.post(
            _attach_url(ns.id), {'activity_id': str(target.id)}, format='json',
        )

        assert again.status_code == status.HTTP_400_BAD_REQUEST

    def test_a_next_step_already_created_into_an_activity_rolls_back(
        self, authed_api_a, account, user_a, world,
    ):
        """Legacy PENDING next step that already has a created activity: the
        exclusivity check of validate() (run LAST) refuses and the updates
        already applied are rolled back."""
        from app_modules.activities.models import Activity
        ns, target = world['ns'], world['target']
        created = Activity(
            title='created from it', activity_type=ActivityType.MEETING,
            status=ActivityStatus.PLANNED, account=account, owner=user_a,
            next_step_signal=ns, scheduled_date=datetime.date(2026, 11, 3),
        )
        created.save(user=user_a, client_id=account.client_id)
        before = _snapshot(target)

        response = authed_api_a.post(_attach_url(ns.id), {
            'activity_id': str(target.id),
            'updates': {'description': 'should be rolled back'},
        }, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert _error_text(response) == str(SignalErrorMessages.NEXT_STEP_CREATED_AND_LINKED)
        self._assert_nothing_changed(ns, target, before)

    def test_another_tenant_cannot_attach(self, authed_api_b, world):
        response = authed_api_b.post(
            _attach_url(world['ns'].id), {'activity_id': str(world['target'].id)},
            format='json',
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


# =============================================================================
# Differences next step ↔ activity, on each link candidate
# =============================================================================

class TestDifferences:

    def _differences(self, authed_api, ns, activity):
        candidates = authed_api.get(_candidates_url(ns.id)).json()['data']['candidates']
        return next(c for c in candidates if c['id'] == str(activity.id))['differences']

    def test_every_section_when_everything_differs(self, authed_api_a, world):
        diff = self._differences(authed_api_a, world['ns'], world['target'])

        assert diff['activity_type'] == {'current': 'CALL', 'proposed': 'MEETING'}
        assert diff['date'] == {
            'current':  {'field': 'scheduled_date', 'value': '2026-11-20'},
            'proposed': {'field': 'scheduled_date', 'value': '2026-11-03'},
        }
        assert diff['decision_step'] == {
            'current':  {'id': str(world['s1'].id), 'name': 'Step 1'},
            'proposed': {'id': str(world['s2'].id), 'name': 'Step 2'},
        }
        assert diff['call_to_action'] == {
            'current': 'Objectif initial', 'proposed': 'Lever le blocage sécurité',
        }
        assert diff['description'] == {
            'current': 'Ordre du jour initial', 'proposed': 'Hébergement UE, DPA',
        }
        assert diff['contacts'] == {'to_add': [{
            'id': str(world['laurent'].id), 'first_name': 'X', 'last_name': 'Petit',
        }]}

    def test_a_section_without_difference_is_absent(self, authed_api_a, user_a, world):
        target = world['target']
        target.activity_type = ActivityType.MEETING
        target.scheduled_date = datetime.date(2026, 11, 3)
        target.decision_step = world['s2']
        target.call_to_action = 'Lever le blocage sécurité'
        target.description = 'Hébergement UE, DPA'
        target.save(user=user_a)
        target.contacts.add(world['laurent'])

        assert self._differences(authed_api_a, world['ns'], target) == {}

    def test_the_proposed_date_field_follows_d6_on_the_activity_type(
        self, authed_api_a, user_a, world,
    ):
        """An EMAIL activity: the next step's date is a deadline (due_date)."""
        target = world['target']
        target.activity_type = ActivityType.EMAIL
        target.save(user=user_a)

        diff = self._differences(authed_api_a, world['ns'], target)

        assert diff['date']['proposed'] == {'field': 'due_date', 'value': '2026-11-03'}
