# backend/tests/ai_pipelines/test_next_step_extractor_v2_fields.py
"""
Sprint Next steps 3.4 -- NextStepExtractor persists the prompt v2 fields,
through the REAL pipeline path (FakeProvider -> NextStepsPipeline.run).

  a) suggested_date_text, carried_by_prospect, suggested_topics,
     suggested_success_criterion, suggested_internal_names persisted;
  b) step ref S<order> -> the DecisionStep of the next step's cycle (same
     tenant); unknown / malformed ref or no cycle -> null + counter;
  c) prospect names -> PeopleSignal (suggested_people), the TD-279 word rule
     (participant_refs, no accents), among the NON-rejected People of the DC
     and of the source activity (same tenant, same account): several distinct
     IDENTITIES (contacts / normalised names) -> no link, the name is kept in
     suggested_people_names; several signals of the SAME identity -> the most
     recent; a first name alone links when one identity only bears it;
  d) dedup WITHIN one answer (NEXT_STEP_DEDUP_KEY) -- never across activities.
"""

import json

import pytest

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.signals.constants import PeopleRole, SignalSource, SignalStatus
from app_modules.signals.models import PeopleSignal


pytestmark = pytest.mark.django_db

TRANSCRIPT = 'Jordan Lee: on se revoit après la revue, avant vendredi.'


def _ns(title='Relire la revue', **fields):
    return {
        'suggested_title': title, 'suggested_activity_type': 'TASK',
        'carried_by_prospect': False, 'suggested_due_date': None, 'suggested_date_text': '',
        'suggested_decision_step': None, 'suggested_people_names': [],
        'suggested_internal_names': [], 'suggested_objective': '',
        'suggested_success_criterion': '', 'suggested_topics': '',
        'source_quote': 'on se revoit après la revue, avant vendredi.',
        'confidence': 0.9, 'is_inferred': False, **fields,
    }


def _run(conversation, user, fake_provider, *signals):
    from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
    fake_provider.replies = {'next_steps': json.dumps({'signals': list(signals)})}
    result = NextStepsPipeline().run(transcript=TRANSCRIPT, activity=conversation, user=user,
                                     client_id=conversation.client_id)
    for s in result['signals']:
        s.refresh_from_db()
    return result


def _people(account, user, source_activity, full_name, *, cycle=None, contact=None,
            status=SignalStatus.PENDING):
    p = PeopleSignal(account=account, source_activity=source_activity, decision_cycle=cycle,
                     full_name=full_name, target_contact=contact, role=PeopleRole.UNKNOWN,
                     source=SignalSource.LLM_EXTRACTED, status=status)
    p.save(user=user, client_id=account.client_id)
    return p


@pytest.fixture
def deal(account, user_a):
    """A standard DC (create_with_entities, auto-created steps), the
    conversation on Business Case, an earlier activity of the same DC."""
    from app_modules.activities.models import Activity
    from app_modules.activities.services.activity_creation_service import (
        ActivityCreationService,
    )
    service = ActivityCreationService(user_a, account.client_id)
    first = service.create_with_entities(
        activity_data={'account_id': str(account.id), 'title': 'Découverte',
                       'activity_type': ActivityType.CALL, 'status': ActivityStatus.COMPLETED},
        inline_cycle={'name': 'Deal Acme'}, inline_step_stage='QUALIFICATION',
    )
    cycle = first['cycle']
    conversation = service.create_with_entities(activity_data={
        'account_id': str(account.id), 'title': 'Atelier', 'activity_type': ActivityType.MEETING,
        'status': ActivityStatus.COMPLETED, 'decision_cycle_id': str(cycle.id),
        'decision_step_id': str(cycle.steps.get(stage='BUSINESS_CASE').id),
    })['activity']
    return conversation, first['activity'], cycle


class TestScalarFields:

    def test_the_v2_fields_are_persisted(self, deal, user_a, fake_provider, patch_active_provider):
        conversation, _first, _cycle = deal
        [signal] = _run(conversation, user_a, fake_provider, _ns(
            carried_by_prospect=True, suggested_date_text='avant vendredi',
            suggested_topics='Points à couvrir', suggested_success_criterion='Accord écrit',
            suggested_internal_names=['  Julie Martin ', '', 'Julie Martin', 7],
        ))['signals']
        assert signal.carried_by_prospect is True
        assert signal.suggested_date_text == 'avant vendredi'
        assert signal.suggested_topics == 'Points à couvrir'
        assert signal.suggested_success_criterion == 'Accord écrit'
        # Strings only, stripped, non-empty, once each, in order.
        assert signal.suggested_internal_names == ['Julie Martin']

    def test_a_v1_answer_keeps_the_defaults(self, deal, user_a, fake_provider, patch_active_provider):
        conversation, _first, _cycle = deal
        v1 = {k: v for k, v in _ns().items() if k in (
            'suggested_title', 'suggested_activity_type', 'suggested_due_date',
            'suggested_objective', 'source_quote', 'confidence', 'is_inferred')}
        [signal] = _run(conversation, user_a, fake_provider, v1)['signals']
        assert (signal.carried_by_prospect, signal.suggested_date_text, signal.suggested_topics,
                signal.suggested_internal_names, signal.suggested_people_names,
                signal.suggested_decision_step_id) == (False, '', '', [], [], None)


class TestStepRef:

    def test_a_ref_maps_to_the_step_of_the_cycle(
        self, deal, user_a, fake_provider, patch_active_provider,
    ):
        conversation, _first, cycle = deal
        result = _run(conversation, user_a, fake_provider,
                      _ns('Préparer le chiffrage', suggested_decision_step='S4'))
        [signal] = result['signals']
        assert signal.suggested_decision_step == cycle.steps.get(order=4)
        assert result['run'].sub_calls[-1]['persist_counts']['step_ref_unknown'] == 0

    @pytest.mark.parametrize('ref', ['S9', 'S0', 'Business Case', 'S4b', ''])
    def test_an_unknown_ref_is_null_and_counted(
        self, deal, user_a, fake_provider, patch_active_provider, ref,
    ):
        conversation, _first, _cycle = deal
        result = _run(conversation, user_a, fake_provider, _ns(suggested_decision_step=ref))
        [signal] = result['signals']
        assert signal.suggested_decision_step_id is None
        assert result['run'].sub_calls[-1]['persist_counts']['step_ref_unknown'] == (1 if ref else 0)

    def test_without_a_cycle_a_ref_is_null_and_counted(
        self, activity, user_a, fake_provider, patch_active_provider,
    ):
        result = _run(activity, user_a, fake_provider, _ns(suggested_decision_step='S1'))
        [signal] = result['signals']
        assert signal.suggested_decision_step_id is None
        assert result['run'].sub_calls[-1]['persist_counts']['step_ref_unknown'] == 1

    def test_only_the_next_steps_own_cycle_is_read(
        self, account, user_a, user_b, other_tenant_account, fake_provider,
        patch_active_provider,
    ):
        """Cycles of the same tenant and of another tenant, created BEFORE the
        conversation's cycle, never give the step."""
        from app_modules.activities.services.activity_creation_service import (
            ActivityCreationService,
        )

        def new_deal(user, acc, title):
            return ActivityCreationService(user, acc.client_id).create_with_entities(
                activity_data={'account_id': str(acc.id), 'title': title,
                               'activity_type': ActivityType.MEETING,
                               'status': ActivityStatus.COMPLETED},
                inline_cycle={'name': title}, inline_step_stage='QUALIFICATION',
            )
        new_deal(user_b, other_tenant_account, 'Other tenant deal')
        new_deal(user_a, account, 'Older deal')
        created = new_deal(user_a, account, 'This deal')
        [signal] = _run(created['activity'], user_a, fake_provider,
                        _ns(suggested_decision_step='S2'))['signals']
        assert signal.suggested_decision_step == created['cycle'].steps.get(order=2)


class TestPeopleLink:

    @pytest.fixture
    def people(self, deal, account, user_a, user_b, other_tenant_account):
        from app_modules.contacts.models import Contact
        from app_modules.decision_cycles.models import DecisionCycle
        conversation, first, cycle = deal
        casey = Contact(account=account, first_name='Casey', last_name='Nguyen')
        casey.save(user=user_a, client_id=account.client_id)
        other_cycle = DecisionCycle(account=account, owner=user_a, name='Other', is_active=True)
        other_cycle.save(user=user_a, client_id=account.client_id)
        made = {
            'jordan': _people(account, user_a, conversation, 'Jordan Lee', cycle=cycle),
            'sam_old': _people(account, user_a, first, 'Sam Rivera', cycle=cycle),
            'sam_new': _people(account, user_a, first, 'Sam  RIVERA', cycle=cycle),
            'alex_m': _people(account, user_a, first, 'Alex Martin', cycle=cycle),
            'alex_d': _people(account, user_a, first, 'Alex Dubois', cycle=cycle),
            'robin': _people(account, user_a, first, 'Robin Petit', cycle=cycle,
                             status=SignalStatus.REJECTED),
            'casey_1': _people(account, user_a, first, '', cycle=cycle, contact=casey),
            'casey_2': _people(account, user_a, conversation, '', cycle=cycle, contact=casey),
            'morgan': _people(account, user_a, None, 'Morgan Blake', cycle=other_cycle),
        }
        made['elsewhere'] = _people(other_tenant_account, user_b, None, 'Taylor Reed')
        return made

    def test_links_and_kept_names(self, deal, people, user_a, fake_provider, patch_active_provider):
        conversation, _first, _cycle = deal
        result = _run(conversation, user_a, fake_provider, _ns(suggested_people_names=[
            'Jordan Lee',      # source activity
            'Sam',             # first name alone, one identity -> its MOST RECENT signal
            'Alex',            # two identities bear it -> ambiguous, kept
            'Robin Petit',     # rejected -> not a candidate, kept
            'Morgan Blake',    # another DC of the account -> not a candidate, kept
            'casey nguyen',    # contact identity (two signals) -> the most recent
            'Taylor Reed',     # another tenant -> kept
            'Jordan Lee',      # repeated -> once
        ]))
        [signal] = result['signals']
        assert set(signal.suggested_people.all()) == {
            people['jordan'], people['sam_new'], people['casey_2']}
        assert signal.suggested_people_names == ['Alex', 'Robin Petit', 'Morgan Blake', 'Taylor Reed']
        counts = result['run'].sub_calls[-1]['persist_counts']
        assert (counts['people_linked'], counts['people_unlinked']) == (3, 4)

    def test_the_full_name_wins_over_a_shared_first_name(
        self, deal, people, user_a, fake_provider, patch_active_provider,
    ):
        """TD-279 rule: the identity matching the MOST name parts wins when
        it is the only one."""
        conversation, _first, _cycle = deal
        [signal] = _run(conversation, user_a, fake_provider,
                        _ns(suggested_people_names=['Alex Dubois']))['signals']
        assert list(signal.suggested_people.all()) == [people['alex_d']]
        assert signal.suggested_people_names == []

    def test_accents_are_ignored(self, deal, account, user_a, fake_provider, patch_active_provider):
        conversation, _first, cycle = deal
        helene = _people(account, user_a, conversation, 'Hélène Faure', cycle=cycle)
        [signal] = _run(conversation, user_a, fake_provider,
                        _ns(suggested_people_names=['Helene Faure']))['signals']
        assert list(signal.suggested_people.all()) == [helene]


class TestDedup:

    def test_a_repeated_action_in_one_answer_is_stored_once(
        self, deal, user_a, fake_provider, patch_active_provider,
    ):
        conversation, _first, _cycle = deal
        result = _run(conversation, user_a, fake_provider,
                      _ns('Relire la revue'), _ns('  relire  LA revue '),
                      _ns('Relire la revue', suggested_activity_type='CALL'),
                      _ns('Relire la revue', suggested_due_date='2027-01-05'))
        titles = sorted((s.suggested_activity_type, str(s.suggested_due_date))
                        for s in result['signals'])
        assert titles == [('CALL', 'None'), ('TASK', '2027-01-05'), ('TASK', 'None')]
        entry = result['run'].sub_calls[-1]
        assert entry['persist_counts']['deduplicated'] == 1
        assert entry['dropped_by_safety_filter'] == 1

    def test_never_across_activities(self, deal, user_a, fake_provider, patch_active_provider):
        conversation, first, _cycle = deal
        _run(first, user_a, fake_provider, _ns('Relire la revue'))
        result = _run(conversation, user_a, fake_provider, _ns('Relire la revue'))
        assert len(result['signals']) == 1
        assert result['run'].sub_calls[-1]['persist_counts']['deduplicated'] == 0


def test_the_dedup_key_is_a_constant():
    from app_modules.ai_pipelines.constants import NEXT_STEP_DEDUP_KEY
    assert NEXT_STEP_DEDUP_KEY == ('suggested_title', 'suggested_activity_type', 'suggested_due_date')
