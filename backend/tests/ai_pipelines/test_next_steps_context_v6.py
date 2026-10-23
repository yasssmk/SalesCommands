# backend/tests/ai_pipelines/test_next_steps_context_v6.py
"""
Sprint Next steps 3.2 -- next_steps context v6: the decision cycle of the
conversation, read by the REAL pipeline path (FakeProvider captures the
prompt sent).

  * the steps of the DC, in order: reference (S<order>), name, DERIVED status
    (StepStatusDerivationService), the "current" mark (first non-validated
    step -- the shared definition, CycleAggregationService);
  * the OPEN activities of the DC (PLANNED / ON_HOLD), in the
    ActivitySequenceService order, the conversation itself excepted: title,
    type, date (scheduled, else due), step reference, people by FIRST NAME
    only;
  * concise JSON; a conversation outside any DC says so.
"""

import datetime
import json

import pytest

from app_modules.activities.constants import ActivityStatus, ActivityType


pytestmark = pytest.mark.django_db

TRANSCRIPT = 'Jordan Lee: on se revoit après la revue.'


def _compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def _context_sent(fake_provider):
    [call] = fake_provider.calls_for('next_steps')
    return call['user'].split('\n---\n')[0]


def _run(activity, user, fake_provider):
    from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
    NextStepsPipeline().run(transcript=TRANSCRIPT, activity=activity, user=user,
                            client_id=activity.client_id)
    return _context_sent(fake_provider)


def _contact(account, user, first, last):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name=first, last_name=last)
    c.save(user=user, client_id=account.client_id)
    return c


def _activity(account, user, title, cycle, step, *, status=ActivityStatus.PLANNED,
              type_=ActivityType.CALL, scheduled=None, due=None, contacts=()):
    from app_modules.activities.models import Activity
    a = Activity(title=title, activity_type=type_, status=status, account=account,
                 owner=user, decision_cycle=cycle, decision_step=step,
                 scheduled_date=scheduled, due_date=due)
    a.save(user=user, client_id=account.client_id)
    if contacts:
        a.contacts.set(contacts)
    return a


@pytest.fixture
def deal(account, user_a):
    """A standard DC (inline cycle, auto-created steps) whose conversation is
    on Business Case; S1-S3 done, an open meeting on S4, a task on hold on S5,
    plus activities that must NOT be listed."""
    from app_modules.activities.services.activity_creation_service import (
        ActivityCreationService,
    )
    from app_modules.decision_cycles.models import DecisionCycle
    created = ActivityCreationService(user_a, account.client_id).create_with_entities(
        activity_data={'account_id': str(account.id), 'title': 'Atelier ROI',
                       'activity_type': ActivityType.MEETING,
                       'status': ActivityStatus.COMPLETED},
        inline_cycle={'name': 'Deal Acme'}, inline_step_stage='BUSINESS_CASE',
    )
    conversation, cycle = created['activity'], created['cycle']
    steps = {s.order: s for s in cycle.steps.all()}
    for order in (1, 2, 3):
        _activity(account, user_a, f'Done {order}', cycle, steps[order],
                  status=ActivityStatus.COMPLETED)
    jordan = _contact(account, user_a, 'Jordan', 'Lee')
    sam = _contact(account, user_a, 'Sam', 'Rivera')
    _activity(account, user_a, 'Revue sécurité', cycle, steps[4], type_=ActivityType.MEETING,
              scheduled=datetime.date(2027, 3, 2), contacts=[jordan, sam])
    _activity(account, user_a, 'Préparer le contrat', cycle, steps[5], type_=ActivityType.TASK,
              status=ActivityStatus.ON_HOLD, due=datetime.date(2027, 4, 1))
    # Never listed: closed, cancelled, another cycle.
    _activity(account, user_a, 'Closed call', cycle, steps[4], status=ActivityStatus.COMPLETED)
    _activity(account, user_a, 'Cancelled call', cycle, steps[4], status=ActivityStatus.CANCELLED,
              scheduled=datetime.date(2027, 3, 1))
    other = DecisionCycle(account=account, owner=user_a, name='Other', is_active=True)
    other.save(user=user_a, client_id=account.client_id)
    _activity(account, user_a, 'Other deal call', other, None, scheduled=datetime.date(2027, 3, 1))
    return conversation, [steps[o] for o in sorted(steps)]


class TestDecisionCycleContext:

    def test_the_steps_with_derived_status_and_current_mark(
        self, deal, user_a, fake_provider, patch_active_provider,
    ):
        conversation, steps = deal
        context = _run(conversation, user_a, fake_provider)
        assert 'DECISION CYCLE' in context
        assert _compact([
            {'ref': 'S1', 'name': steps[0].name, 'status': 'VALIDATED'},
            {'ref': 'S2', 'name': steps[1].name, 'status': 'VALIDATED'},
            {'ref': 'S3', 'name': steps[2].name, 'status': 'VALIDATED'},
            {'ref': 'S4', 'name': steps[3].name, 'status': 'IN_PROGRESS', 'current': True},
            {'ref': 'S5', 'name': steps[4].name, 'status': 'NOT_STARTED'},
        ]) in context

    def test_the_open_activities_of_the_cycle(
        self, deal, user_a, fake_provider, patch_active_provider,
    ):
        conversation, _steps = deal
        context = _run(conversation, user_a, fake_provider)
        assert _compact([
            {'title': 'Revue sécurité', 'type': 'MEETING', 'date': '2027-03-02',
             'step': 'S4', 'people': ['Jordan', 'Sam']},
            {'title': 'Préparer le contrat', 'type': 'TASK', 'date': '2027-04-01',
             'step': 'S5', 'people': []},
        ]) in context
        for absent in ('Atelier ROI', 'Closed call', 'Cancelled call', 'Other deal call', 'Done 1'):
            assert absent not in context

    def test_the_conversation_itself_is_never_listed(
        self, deal, user_a, fake_provider, patch_active_provider,
    ):
        """Even when still open (extracted before being marked completed)."""
        conversation, _steps = deal
        conversation.status = ActivityStatus.PLANNED
        conversation.save(user=user_a)
        context = _run(conversation, user_a, fake_provider)
        assert 'Revue sécurité' in context
        assert 'Atelier ROI' not in context

    def test_people_by_first_name_only(self, deal, user_a, fake_provider, patch_active_provider):
        conversation, _steps = deal
        context = _run(conversation, user_a, fake_provider)
        assert 'Jordan' in context
        assert 'Lee' not in context and 'Rivera' not in context

    def test_a_conversation_outside_any_cycle(
        self, activity, user_a, fake_provider, patch_active_provider,
    ):
        context = _run(activity, user_a, fake_provider)
        assert 'DECISION CYCLE' in context
        assert '- none' in context

    def test_the_session_block_is_kept(self, deal, user_a, fake_provider, patch_active_provider):
        conversation, _steps = deal
        context = _run(conversation, user_a, fake_provider)
        assert context.startswith('SESSION CONTEXT')
        assert '- Prospect (the account being analyzed): Acme Corp' in context


def test_versions():
    from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
    from app_modules.ai_pipelines.prompts.next_steps.context import CONTEXT_VERSION
    assert CONTEXT_VERSION == 'v6'
    assert NextStepsPipeline.PROMPT_VERSIONS['context'] == 'v6'
