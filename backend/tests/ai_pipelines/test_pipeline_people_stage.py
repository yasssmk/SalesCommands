# backend/tests/ai_pipelines/test_pipeline_people_stage.py
"""
People-stage integration tests for QualificationSignalsPipeline
(UX Activity — People S1), through the REAL pipeline path (FakeProvider).

  * Participant reference -> target_contact; full_name and department
    DERIVED from the contact (department falls back to the extracted one).
  * Cited person -> full_name as stated + resolved department, no contact.
    Unnamed cited person ("our CFO") -> department alone, kept.
  * Drops: role out of PeopleRole, no identity, blank source_quote.
    Folds: invalid influence -> None. Unresolved / other-account reference
    -> no contact, signal kept.
  * is_inferred=true is KEPT for people (DROP_INFERRED_EXEMPT_STAGES) and
    still dropped for another stage in the same run; the confidence floor
    still applies to people.
  * In-extraction dedup (shared with TechStack): same participant twice ->
    one signal + 1 additional quote; same name twice -> one signal; two
    unnamed persons -> two signals.
  * Endpoint response carries the `people` key (fresh, cached, empty).
"""

import json
from contextlib import ExitStack
from unittest.mock import patch

import pytest

from app_modules.ai_pipelines.constants import AIPipelineStatus
from app_modules.signals.constants import (
    InfluenceLevel,
    PeopleRole,
    SignalSource,
    SignalStatus,
)
from app_modules.signals.models import BlockerSignal, PeopleSignal

# Cross-account fixtures (tenant A, second account) and the DC fixture --
# re-used from the signals conftest.
from tests.signals.conftest import (  # noqa: F401
    decision_cycle,
    other_account,
    other_account_contact,
)


pytestmark = pytest.mark.django_db

TRANSCRIPT = 'Discovery call with Acme. The CFO will decide on the budget.'


def _dept(name):
    from app_modules.core_modules.models import StandardDepartment
    dept, _ = StandardDepartment.objects.get_or_create(name=name)
    return dept


def _person(**overrides):
    payload = {
        'participant_ref': None,
        'full_name': None,
        'role': PeopleRole.ECONOMIC_BUYER.value,
        'influence': InfluenceLevel.HIGH.value,
        'department': None,
        'notes': 'Holds the budget sign-off.',
        'source_quote': 'The CFO will decide on the budget.',
        'confidence': 0.9,
        'is_inferred': False,
    }
    payload.update(overrides)
    return payload


def _run(account, activity, user_a, fake_provider, people, extra_replies=None):
    from app_modules.ai_pipelines.pipelines.transcript_signals import (
        QualificationSignalsPipeline,
    )
    fake_provider.replies = {
        'people': json.dumps({'signals': people}),
        **(extra_replies or {}),
    }
    return QualificationSignalsPipeline().run(
        transcript=TRANSCRIPT,
        activity=activity,
        user=user_a,
        client_id=account.client_id,
    )


def _people(result):
    return result['signals_by_stage']['people']


# =============================================================================
# PERSISTENCE + FIELD MAPPING
# =============================================================================

class TestPeoplePersistence:

    def test_people_stage_runs_last_with_its_prompt_version(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        result = _run(account, activity, user_a, fake_provider, [])
        assert fake_provider.stages_in_order()[-1] == 'people'
        assert result['run'].prompt_versions['people'] == 'v3'
        assert result['run'].prompt_versions['context'] == 'v3'
        assert result['run'].status == AIPipelineStatus.SUCCESS
        people_prompt = fake_provider.calls_for('people')[0]['user']
        assert 'Extract PEOPLE signals' in people_prompt

    def test_participant_ref_resolves_and_derives_name_and_department(
        self, account, activity, user_a, contact, contact_extra,
        fake_provider, patch_active_provider,
    ):
        # Doe = P1, Smith = P2 (last_name order). Smith's own department wins
        # over the extracted one.
        contact_extra.standard_department = _dept('Finance')
        contact_extra.save(user=user_a, client_id=account.client_id)
        _dept('IT')
        activity.contacts.add(contact, contact_extra)

        result = _run(account, activity, user_a, fake_provider, [
            _person(participant_ref='P2', full_name='Johnny', department='IT'),
        ])

        [signal] = _people(result)
        signal.refresh_from_db()
        assert signal.target_contact_id == contact_extra.id
        assert signal.full_name == 'John Smith'
        assert signal.target_department.name == 'Finance'
        assert signal.role == PeopleRole.ECONOMIC_BUYER
        assert signal.influence == InfluenceLevel.HIGH
        assert signal.notes == 'Holds the budget sign-off.'
        assert signal.status == SignalStatus.PENDING
        assert signal.source == SignalSource.LLM_EXTRACTED
        assert signal.source_activity_id == activity.id
        assert signal.account_id == account.id
        assert signal.canonical_key is None

    def test_participant_without_department_takes_the_extracted_one(
        self, account, activity, user_a, contact,
        fake_provider, patch_active_provider,
    ):
        _dept('IT')
        activity.contacts.add(contact)

        result = _run(account, activity, user_a, fake_provider, [
            _person(participant_ref='P1', department='IT'),
        ])

        [signal] = _people(result)
        assert signal.target_contact_id == contact.id
        assert signal.full_name == 'Jane Doe'
        assert signal.target_department.name == 'IT'

    def test_cited_person_keeps_stated_name_and_department_without_contact(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        _dept('Finance')

        result = _run(account, activity, user_a, fake_provider, [
            _person(full_name='Marc', department='Finance'),
        ])

        [signal] = _people(result)
        assert signal.target_contact_id is None
        assert signal.full_name == 'Marc'
        assert signal.full_name_normalized == 'marc'
        assert signal.target_department.name == 'Finance'

    def test_unnamed_cited_person_kept_with_department_alone(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        _dept('Finance')

        result = _run(account, activity, user_a, fake_provider, [
            _person(full_name=None, department='Finance'),
        ])

        [signal] = _people(result)
        assert signal.target_contact_id is None
        assert signal.full_name == ''
        assert signal.target_department.name == 'Finance'

    def test_decision_cycle_propagated_from_activity(
        self, account, activity, user_a, decision_cycle,  # noqa: F811
        fake_provider, patch_active_provider,
    ):
        from app_modules.activities.models import Activity
        Activity.objects.filter(id=activity.id).update(decision_cycle=decision_cycle)
        activity.refresh_from_db()

        result = _run(account, activity, user_a, fake_provider, [
            _person(full_name='Marc Dubois'),
        ])

        [signal] = _people(result)
        assert signal.decision_cycle_id == decision_cycle.id


# =============================================================================
# DROPS AND FOLDS
# =============================================================================

class TestPeopleDropsAndFolds:

    @pytest.mark.parametrize('role', ['GATEKEEPER', None, ''])
    def test_role_out_of_list_is_dropped(
        self, account, activity, user_a, fake_provider, patch_active_provider, role,
    ):
        result = _run(account, activity, user_a, fake_provider, [
            _person(full_name='Marc', role=role),
        ])
        assert _people(result) == []
        assert PeopleSignal.objects.count() == 0

    @pytest.mark.parametrize('influence', ['UNKNOWN', 'DECISION_MAKER', None])
    def test_invalid_influence_folds_to_none(
        self, account, activity, user_a, fake_provider, patch_active_provider,
        influence,
    ):
        result = _run(account, activity, user_a, fake_provider, [
            _person(full_name='Marc', influence=influence),
        ])
        [signal] = _people(result)
        assert signal.influence is None

    def test_other_account_participant_is_not_attributed(
        self, account, activity, user_a, contact, other_account_contact,
        fake_provider, patch_active_provider,
    ):
        # Filtered on the activity's account, the other-account contact is
        # not a participant: P2 does not resolve.
        activity.contacts.add(contact, other_account_contact)

        result = _run(account, activity, user_a, fake_provider, [
            _person(participant_ref='P2', full_name='Bill'),
        ])

        [signal] = _people(result)
        assert signal.target_contact_id is None
        assert signal.full_name == 'Bill'

    def test_unresolved_reference_keeps_signal_without_contact(
        self, account, activity, user_a, contact,
        fake_provider, patch_active_provider,
    ):
        activity.contacts.add(contact)

        result = _run(account, activity, user_a, fake_provider, [
            _person(participant_ref='P9', full_name='Marc'),
        ])

        [signal] = _people(result)
        assert signal.target_contact_id is None
        assert signal.full_name == 'Marc'

    def test_no_identity_is_dropped(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        result = _run(account, activity, user_a, fake_provider, [
            _person(participant_ref=None, full_name=None, department='Martians'),
        ])
        assert _people(result) == []
        assert PeopleSignal.objects.count() == 0

    @pytest.mark.parametrize('quote', ['', '   ', None])
    def test_blank_source_quote_is_dropped(
        self, account, activity, user_a, fake_provider, patch_active_provider, quote,
    ):
        result = _run(account, activity, user_a, fake_provider, [
            _person(full_name='Marc', source_quote=quote),
        ])
        assert _people(result) == []


# =============================================================================
# SAFETY FILTER — is_inferred exemption limited to people
# =============================================================================

class TestPeopleInferredExemption:

    def test_inferred_people_kept_inferred_blocker_still_dropped(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        blocker_reply = json.dumps({'signals': [{
            'summary': 'No budget this quarter',
            'source_quote': 'We have no budget allocated for Q4',
            'confidence': 0.6,
            'is_inferred': True,
            'raised_by': None,
        }]})

        result = _run(
            account, activity, user_a, fake_provider,
            [_person(full_name='Marc', role=PeopleRole.CHAMPION.value,
                     confidence=0.6, is_inferred=True)],
            extra_replies={'blocker': blocker_reply},
        )

        [signal] = _people(result)
        assert signal.is_inferred is True
        assert signal.role == PeopleRole.CHAMPION
        # Témoin: the same epistemic state is still dropped for blocker.
        assert result['signals_by_stage']['blocker'] == []
        assert BlockerSignal.objects.count() == 0

    def test_confidence_floor_still_applies_to_people(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        result = _run(account, activity, user_a, fake_provider, [
            _person(full_name='Marc', confidence=0.3, is_inferred=True),
        ])
        assert _people(result) == []


# =============================================================================
# IN-EXTRACTION DEDUPLICATION (shared with TechStack)
# =============================================================================

class TestPeopleDeduplication:

    def test_same_participant_twice_is_one_signal_with_additional_quote(
        self, account, activity, user_a, contact,
        fake_provider, patch_active_provider,
    ):
        activity.contacts.add(contact)

        result = _run(account, activity, user_a, fake_provider, [
            _person(participant_ref='P1', source_quote='Jane signs off.'),
            _person(participant_ref='P1', role=PeopleRole.CHAMPION.value,
                    source_quote='Jane pushes for it internally.'),
        ])

        [signal] = _people(result)
        assert signal.target_contact_id == contact.id
        assert signal.role == PeopleRole.ECONOMIC_BUYER   # first wins
        assert signal.source_quote == 'Jane signs off.'
        assert signal.metadata['additional_quotes'] == ['Jane pushes for it internally.']

    def test_same_name_twice_is_one_signal(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        result = _run(account, activity, user_a, fake_provider, [
            _person(full_name='Marc', source_quote='Marc decides.'),
            _person(full_name='  marc ', source_quote='Ask Marc.'),
        ])

        [signal] = _people(result)
        assert signal.full_name == 'Marc'
        assert signal.metadata['additional_quotes'] == ['Ask Marc.']

    def test_same_name_different_departments_are_two_signals(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        # Identity of a cited person = normalised name + department (the DC
        # cluster rule): Marc / Finance and Marc / IT are two persons.
        _dept('Finance')
        _dept('IT')

        result = _run(account, activity, user_a, fake_provider, [
            _person(full_name='Marc', department='Finance', source_quote='Marc decides.'),
            _person(full_name='Marc', department='IT', source_quote='Marc from IT.'),
        ])

        people = _people(result)
        assert len(people) == 2
        assert {p.target_department.name for p in people} == {'Finance', 'IT'}

    def test_same_name_same_department_twice_is_one_signal(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        _dept('Finance')

        result = _run(account, activity, user_a, fake_provider, [
            _person(full_name='Marc', department='Finance', source_quote='Marc decides.'),
            _person(full_name='marc', department='Finance', source_quote='Ask Marc.'),
        ])

        [signal] = _people(result)
        assert signal.target_department.name == 'Finance'
        assert signal.metadata['additional_quotes'] == ['Ask Marc.']

    def test_two_unnamed_persons_are_never_merged(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        _dept('Finance')

        result = _run(account, activity, user_a, fake_provider, [
            _person(full_name=None, department='Finance', source_quote='Our CFO decides.'),
            _person(full_name=None, department='Finance', source_quote='Our CFO approves.'),
        ])

        assert len(_people(result)) == 2


# =============================================================================
# PROMPT v2 — unlisted prospect speakers + seller side + no-omission taxonomy
# =============================================================================

class TestPeoplePromptV2:

    def _prompt(self):
        from app_modules.ai_pipelines.prompts.transcript_signals.people_v1 import (
            build_people_request,
        )
        # Whitespace collapsed: the rules wrap over several prompt lines.
        return ' '.join(
            build_people_request('Claire Dubois: we need the CFO on board.').split()
        )

    def test_unlisted_prospect_speaker_rule_present(self):
        prompt = self._prompt()
        assert 'SPEAKS in the transcript' in prompt
        assert 'speaker label' in prompt
        assert 'NOT listed in the SESSION CONTEXT' in prompt

    def test_seller_side_rule_present(self):
        prompt = self._prompt()
        assert 'presents or sells the solution' in prompt
        assert 'even when their organization is not named' in prompt

    def test_unlisted_speaker_attribution_rule(self):
        prompt = self._prompt()
        assert 'speaker who is NOT a listed participant' in prompt

    def test_people_taxonomy_header_has_no_omission_rule(self, activity):
        from app_modules.ai_pipelines.prompts.transcript_signals.context import (
            build_context_layer,
        )
        context = build_context_layer(activity, 'people')
        assert 'PEOPLE TAXONOMY' in context
        assert 'OMIT' not in context
        assert 'CANONICAL TAXONOMY' not in context

    def test_unlisted_speaker_emitted_without_ref_is_created_without_contact(
        self, account, activity, user_a, contact,
        fake_provider, patch_active_provider,
    ):
        activity.contacts.add(contact)

        result = _run(account, activity, user_a, fake_provider, [
            _person(participant_ref=None, full_name='Claire Dubois'),
        ])

        [signal] = _people(result)
        assert signal.target_contact_id is None
        assert signal.full_name == 'Claire Dubois'


# =============================================================================
# PROMPT v3 — department strictly from what the transcript says of the person
# =============================================================================

class TestPeoplePromptV3Department:

    def _prompt(self):
        from app_modules.ai_pipelines.prompts.transcript_signals.people_v1 import (
            build_people_request,
        )
        # Whitespace collapsed: the rules wrap over several prompt lines.
        return ' '.join(build_people_request('Karim will be our first pilot user.').split())

    def test_department_only_from_what_the_transcript_says_of_the_person(self):
        prompt = self._prompt()
        assert "ONLY from what the transcript says about THIS person" in prompt

    def test_department_never_inferred_from_other_sources(self):
        prompt = self._prompt()
        assert 'NEVER infer it from' in prompt
        for source in (
            'the company name', 'the meeting title', "the prospect's industry",
            'the department of the SPEAKER', 'the other persons',
            'PEOPLE ALREADY IDENTIFIED IN THIS DEAL',
        ):
            assert source in prompt

    def test_department_null_when_nothing_is_said(self):
        prompt = self._prompt()
        assert 'set `department` to null' in prompt

    def test_real_case_example_maps_key_accounts_lead_to_sales(self):
        from app_modules.core_modules.models import StandardDepartment
        prompt = self._prompt()
        sales = StandardDepartment.DepartmentChoices.SALES.value
        assert f'"head of the key accounts team" -> department "{sales}"' in prompt


# =============================================================================
# DC SAFETY NET — never recreate a person already identified in the deal
# =============================================================================

def _attach_cycle(activity, cycle):
    from app_modules.activities.models import Activity
    Activity.objects.filter(id=activity.id).update(decision_cycle=cycle)
    activity.refresh_from_db()
    return activity


def _existing_people(activity, user, cycle, *, status=SignalStatus.PENDING,
                     full_name='', contact=None, department=None):
    """A PeopleSignal already in the deal (seeded PENDING, then moved by update)."""
    signal = PeopleSignal(
        account=activity.account,
        source_activity=activity,
        decision_cycle=cycle,
        role=PeopleRole.ECONOMIC_BUYER,
        full_name=full_name,
        target_contact=contact,
        target_department=department,
        source=SignalSource.LLM_EXTRACTED,
        status=SignalStatus.PENDING,
    )
    signal.save(user=user, client_id=activity.client_id)
    if status != SignalStatus.PENDING:
        PeopleSignal.objects.filter(id=signal.id).update(status=status)
    return signal


class TestPeopleAlreadyIdentifiedInDeal:

    def test_f1_named_person_already_in_dc_is_not_recreated_and_logged(
        self, account, activity, user_a, decision_cycle,  # noqa: F811
        fake_provider, patch_active_provider, caplog,
    ):
        _attach_cycle(activity, decision_cycle)
        existing = _existing_people(
            activity, user_a, decision_cycle,
            full_name='Isabelle Roux', department=_dept('Finance'),
        )

        with caplog.at_level('WARNING'):
            result = _run(account, activity, user_a, fake_provider, [
                _person(full_name='isabelle  ROUX', department='Finance'),
            ])

        assert _people(result) == []
        assert PeopleSignal.objects.filter(decision_cycle=decision_cycle).count() == 1
        records = [r for r in caplog.records if r.getMessage() == 'people_already_identified_in_dc']
        assert len(records) == 1
        assert records[0].existing_signal_id == str(existing.id)
        # The log never carries the person's name.
        assert 'roux' not in str(records[0].__dict__).lower()
        people_call = [c for c in result['run'].sub_calls if c['stage'] == 'people'][0]
        assert people_call['dropped_by_safety_filter'] == 1

    def test_f2_participant_contact_already_in_dc_is_not_recreated(
        self, account, activity, user_a, contact, decision_cycle,  # noqa: F811
        fake_provider, patch_active_provider,
    ):
        activity.contacts.add(contact)
        _attach_cycle(activity, decision_cycle)
        _existing_people(activity, user_a, decision_cycle, contact=contact)

        result = _run(account, activity, user_a, fake_provider, [
            _person(participant_ref='P1'),
        ])

        assert _people(result) == []
        assert PeopleSignal.objects.filter(target_contact=contact).count() == 1

    def test_f3_new_person_is_created(
        self, account, activity, user_a, decision_cycle,  # noqa: F811
        fake_provider, patch_active_provider,
    ):
        _attach_cycle(activity, decision_cycle)
        _existing_people(activity, user_a, decision_cycle, full_name='Isabelle Roux')

        result = _run(account, activity, user_a, fake_provider, [
            _person(full_name='Marc Lefort'),
        ])

        [signal] = _people(result)
        assert signal.full_name == 'Marc Lefort'

    def test_f4_activity_without_dc_has_no_filter(
        self, account, activity, user_a, decision_cycle,  # noqa: F811
        fake_provider, patch_active_provider,
    ):
        # A same-named person exists in some DC, but this activity has none.
        _existing_people(activity, user_a, decision_cycle, full_name='Isabelle Roux')

        result = _run(account, activity, user_a, fake_provider, [
            _person(full_name='Isabelle Roux'),
        ])

        assert len(_people(result)) == 1

    def test_f5_rejected_existing_person_does_not_block(
        self, account, activity, user_a, decision_cycle,  # noqa: F811
        fake_provider, patch_active_provider,
    ):
        _attach_cycle(activity, decision_cycle)
        _existing_people(
            activity, user_a, decision_cycle,
            full_name='Isabelle Roux', status=SignalStatus.REJECTED,
        )

        result = _run(account, activity, user_a, fake_provider, [
            _person(full_name='Isabelle Roux'),
        ])

        assert len(_people(result)) == 1

    def test_f6_unnamed_person_is_never_filtered(
        self, account, activity, user_a, decision_cycle,  # noqa: F811
        fake_provider, patch_active_provider,
    ):
        finance = _dept('Finance')
        _attach_cycle(activity, decision_cycle)
        _existing_people(activity, user_a, decision_cycle, department=finance)

        result = _run(account, activity, user_a, fake_provider, [
            _person(full_name=None, department='Finance'),
        ])

        assert len(_people(result)) == 1


# =============================================================================
# ENDPOINT RESPONSE — `people` key (fresh, cached, empty)
# =============================================================================

_URL = '/module-ai-pipelines/activity-extraction/run/'

_BYPASS_REDIS = (
    'app_modules.ai_pipelines.views.activity_extraction_view.start_op',
    'app_modules.ai_pipelines.views.activity_extraction_view.complete_op',
    'app_modules.ai_pipelines.views.activity_extraction_view.fail_op',
)


def _post(api, activity):
    with ExitStack() as stack:
        for target in _BYPASS_REDIS:
            stack.enter_context(patch(target, return_value=None))
        return api.post(
            _URL,
            {'activity_id': str(activity.id), 'transcript': TRANSCRIPT},
            format='json',
        )


class TestEndpointPeopleKey:

    def test_fresh_then_cached_response_carry_people(
        self, authed_api_a, activity, decision_cycle,  # noqa: F811
        fake_provider, patch_active_provider,
    ):
        # DC context so BOTH pipelines run: the replay then takes the
        # "both cached" path (409 ALREADY_EXTRACTED, cached payload).
        from app_modules.activities.models import Activity
        Activity.objects.filter(id=activity.id).update(decision_cycle=decision_cycle)
        activity.refresh_from_db()
        fake_provider.replies = {
            'people': json.dumps({'signals': [_person(full_name='Marc Dubois')]}),
        }

        fresh = _post(authed_api_a, activity)
        assert fresh.status_code == 200, fresh.content
        data = fresh.json()['data']
        assert data['qualification_run']['from_cache'] is False
        [person] = data['qualification_signals']['people']
        assert person['full_name'] == 'Marc Dubois'
        assert person['role'] == PeopleRole.ECONOMIC_BUYER

        cached = _post(authed_api_a, activity)
        assert cached.status_code == 409, cached.content
        data = cached.json()['data']
        assert data['qualification_run']['from_cache'] is True
        [person] = data['qualification_signals']['people']
        assert person['full_name'] == 'Marc Dubois'

    def test_empty_qualification_payload_has_people_key(self):
        from app_modules.ai_pipelines.views.activity_extraction_view import (
            ActivityExtractionView,
        )
        assert ActivityExtractionView._empty_qualif_signals()['people'] == []
