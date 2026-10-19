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
        assert result['run'].prompt_versions['people'] == 'v5'
        # v4 = Sprint TechStack T0 (techstack usage taxonomy); v5 = T4b
        # (shared "Conversation date" line + techstack header); v6 = no list
        # of the persons already known in the deal (people P2); v7 = contacts
        # "registered on this activity", not "in this conversation" (TD-279).
        assert result['run'].prompt_versions['context'] == 'v7'
        assert result['run'].status == AIPipelineStatus.SUCCESS
        people_prompt = fake_provider.calls_for('people')[0]['user']
        assert 'Extract PEOPLE signals' in people_prompt

    def test_participant_ref_resolves_and_derives_name_and_department(
        self, account, activity, user_a, contact, contact_extra,
        fake_provider, patch_active_provider,
    ):
        # Doe = P1, Smith = P2 (last_name order). Smith's own department wins
        # over the extracted one. The stated name must designate the contact
        # (TD-279: "John" matches John Smith; another name would detach).
        contact_extra.standard_department = _dept('Finance')
        contact_extra.save(user=user_a, client_id=account.client_id)
        _dept('IT')
        activity.contacts.add(contact, contact_extra)

        result = _run(account, activity, user_a, fake_provider, [
            _person(participant_ref='P2', full_name='John', department='IT'),
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
# TD-279 — a participant reference whose name is another person is DETACHED
# =============================================================================

ISABELLE_QUOTE = (
    'Mais avant ça, on devra forcément faire un rendez-vous avec Isabelle '
    'Roux, notre DAF. C\'est elle qui tient le budget, elle voudra voir un '
    'business case avec un retour sur investissement chiffré.'
)


@pytest.fixture
def criminelle(db, account, user_a, activity):
    """The registered contact of the TD-279 smoke: Finance, never speaks."""
    from app_modules.contacts.models import Contact
    c = Contact(
        account=account,
        first_name='Criminelle',
        last_name='Husky',
        standard_department=_dept('Finance'),
    )
    c.save(user=user_a, client_id=account.client_id)
    activity.contacts.add(c)
    return c


class TestParticipantNameMismatchIsDetached:
    """
    TD-279: the LLM returns "P1" with the name of ANOTHER person (the cited
    DAF Isabelle Roux) -> the reference is ignored, no contact, the stated
    name is kept; the check runs BEFORE the in-extraction dedup, so the false
    P1 merges with the real "Isabelle Roux" entry.
    """

    def test_a_false_p1_with_another_name_merges_into_the_cited_person(
        self, account, activity, user_a, criminelle,
        fake_provider, patch_active_provider,
    ):
        result = _run(account, activity, user_a, fake_provider, [
            _person(participant_ref='P1', full_name='Isabelle Roux',
                    role=PeopleRole.DECISION_MAKER.value, department='Finance',
                    source_quote=ISABELLE_QUOTE),
            _person(participant_ref=None, full_name='Isabelle Roux',
                    department='Finance', source_quote=ISABELLE_QUOTE),
        ])

        [signal] = _people(result)
        signal.refresh_from_db()
        assert signal.full_name == 'Isabelle Roux'
        assert signal.target_contact_id is None
        assert not PeopleSignal.objects.filter(target_contact=criminelle).exists()

    def test_b_p1_with_the_contact_first_name_stays_attached(
        self, account, activity, user_a, criminelle,
        fake_provider, patch_active_provider,
    ):
        result = _run(account, activity, user_a, fake_provider, [
            _person(participant_ref='P1', full_name='Criminelle'),
        ])

        [signal] = _people(result)
        assert signal.target_contact_id == criminelle.id
        assert signal.full_name == 'Criminelle Husky'

    def test_c_p1_without_a_name_stays_attached(
        self, account, activity, user_a, criminelle,
        fake_provider, patch_active_provider,
    ):
        result = _run(account, activity, user_a, fake_provider, [
            _person(participant_ref='P1', full_name=None),
        ])

        [signal] = _people(result)
        assert signal.target_contact_id == criminelle.id
        assert signal.full_name == 'Criminelle Husky'


class TestStatedNameMatchesContact:
    """The TD-279 word match itself (no DB)."""

    @staticmethod
    def _matches(stated, first='Hélène', last='Le Gall'):
        from types import SimpleNamespace
        from app_modules.ai_pipelines.services.transcript_signal_extractor import (
            stated_name_matches_contact,
        )
        return stated_name_matches_contact(
            stated, SimpleNamespace(first_name=first, last_name=last),
        )

    @pytest.mark.parametrize('stated', [
        'Hélène', 'helene', 'HELENE', 'Hélène Le Gall', 'Mme Le Gall', None, '', '   ',
    ])
    def test_matches(self, stated):
        assert self._matches(stated)

    @pytest.mark.parametrize('stated', ['Isabelle Roux', 'Hélènette', 'Gall', 'Le'])
    def test_does_not_match(self, stated):
        assert not self._matches(stated)


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
# TD-279 B3 — PROMPT v5 / CONTEXT v7: a listed contact is evidence of nothing
# =============================================================================

class TestPeoplePromptV5Attribution:

    def _prompt(self):
        return TestPeoplePromptV3Department()._prompt()

    def test_listed_contact_extracted_only_when_the_transcript_shows_them(self):
        prompt = self._prompt()
        assert 'A contact listed in the SESSION CONTEXT is extracted ONLY when' in prompt
        assert 'is NOT emitted -- being listed is never evidence of a role' in prompt
        # The v4 rule "speaks OR is listed" is gone.
        assert 'OR who is listed as a prospect contact' not in prompt

    def test_reference_only_when_the_evidence_is_about_that_participant(self):
        prompt = self._prompt()
        assert '`participant_ref` to a participant\'s reference' in prompt
        assert 'ONLY when the evidence is about THAT participant' in prompt
        assert 'whose name differs from the listed participant\'s name is NEVER that participant' in prompt

    def test_never_transfer_what_is_said_of_another_named_person(self):
        prompt = self._prompt()
        assert 'NEVER transfer to one person what the transcript says about ANOTHER' in prompt

    def test_full_name_of_a_reference_entry_is_the_name_as_written(self):
        prompt = self._prompt()
        assert 'For a `participant_ref` entry, `full_name` is the participant\'s name' in prompt

    def test_deduction_allowed_conclusion_without_evidence_not(self):
        prompt = self._prompt()
        assert 'A DEDUCTION from what the transcript says is allowed' in prompt
        assert 'a conclusion with NO evidence in the transcript is not' in prompt

    def test_examples_do_not_reuse_the_td279_smoke(self):
        # TD-273: an example taken from the smoke would no longer measure
        # generalisation (B2 runs on that very transcript).
        prompt = self._prompt()
        for smoke_word in ('Isabelle', 'Criminelle', 'Logistix', 'DAF'):
            assert smoke_word not in prompt

    @pytest.mark.parametrize('stage', ['people', 'blocker', 'pain_impact', 'techstack'])
    def test_context_line_says_contacts_are_registered_not_present(
        self, stage, activity, contact,
    ):
        from app_modules.ai_pipelines.prompts.transcript_signals.context import (
            build_context_layer,
        )
        activity.contacts.add(contact)
        context = build_context_layer(activity, stage)
        assert (
            '- Prospect contacts registered on this activity (they may not speak, '
            'and are not necessarily the persons cited in the transcript):'
        ) in context
        assert 'contacts in this conversation' not in context


# =============================================================================
# P2 — NO KNOWN-PEOPLE LIST in the people context nor in the prompt
# =============================================================================

# Marker of the removed "persons already known in the deal" block (P2),
# assembled from its words so the removed wording appears nowhere in backend/.
_REMOVED_BLOCK_MARKER = ' '.join(('ALREADY', 'IDENTIFIED'))


class TestNoKnownPeopleListSentToTheLLM:

    def test_the_people_call_of_a_new_activity_carries_no_known_people_list(
        self, account, activity, user_a, decision_cycle,  # noqa: F811
        fake_provider, patch_active_provider,
    ):
        # Marc Dupont is known in the deal from activity A; the people call of
        # activity B (real context + request assembly) must not list him.
        _attach_cycle(activity, decision_cycle)
        _existing_people(
            activity, user_a, decision_cycle,
            full_name='Marc Dupont', department=_dept('Finance'),
        )
        activity_b = _second_activity(account, user_a, decision_cycle)

        _run(account, activity_b, user_a, fake_provider, [])

        [call] = fake_provider.calls_for('people')
        assert _REMOVED_BLOCK_MARKER not in call['user']
        assert 'Dupont' not in call['user']

    def test_the_people_prompt_no_longer_mentions_the_list(self):
        from app_modules.ai_pipelines.prompts.transcript_signals.people_v1 import (
            build_people_request,
        )
        prompt = ' '.join(build_people_request('Karim will be our first pilot user.').split())
        assert _REMOVED_BLOCK_MARKER not in prompt
        assert 'never emit them again' not in prompt

    def test_versions(self):
        from app_modules.ai_pipelines.prompts.transcript_signals.context import CONTEXT_VERSION
        from app_modules.ai_pipelines.prompts.transcript_signals.people_v1 import (
            PEOPLE_PROMPT_VERSION,
        )
        assert PEOPLE_PROMPT_VERSION == 'v5'
        assert CONTEXT_VERSION == 'v7'


# =============================================================================
# NO FILTER BETWEEN ACTIVITIES — a person already known in the deal is ALWAYS
# created again for a new activity (PO rule: merge only within ONE transcript;
# the grouping across activities is the DC cluster's job).
# =============================================================================

def _attach_cycle(activity, cycle):
    from app_modules.activities.models import Activity
    Activity.objects.filter(id=activity.id).update(decision_cycle=cycle)
    activity.refresh_from_db()
    return activity


def _second_activity(account, user, cycle):
    """Activity B of the SAME deal (activity A is the `activity` fixture)."""
    from app_modules.activities.constants import ActivityStatus, ActivityType
    from app_modules.activities.models import Activity
    b = Activity(
        title='Follow-up call with Acme',
        activity_type=ActivityType.MEETING,
        status=ActivityStatus.COMPLETED,
        account=account,
        owner=user,
        decision_cycle=cycle,
    )
    b.save(user=user, client_id=account.client_id)
    return b


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


class TestKnownPersonIsNeverFiltered:

    @pytest.mark.parametrize('status', [SignalStatus.PENDING, SignalStatus.VALIDATED])
    def test_n1_named_person_known_from_activity_a_is_created_again_for_activity_b(
        self, status, account, activity, user_a, decision_cycle,  # noqa: F811
        fake_provider, patch_active_provider, caplog,
    ):
        _attach_cycle(activity, decision_cycle)
        existing = _existing_people(
            activity, user_a, decision_cycle, status=status,
            full_name='Marc Dupont', department=_dept('Finance'),
        )
        activity_b = _second_activity(account, user_a, decision_cycle)

        with caplog.at_level('WARNING'):
            result = _run(account, activity_b, user_a, fake_provider, [
                _person(full_name='Marc Dupont', department='Finance'),
            ])

        [signal] = _people(result)
        assert signal.id != existing.id
        assert signal.source_activity_id == activity_b.id
        assert signal.full_name == 'Marc Dupont'
        # Two signals in the deal: one per activity.
        assert PeopleSignal.objects.filter(decision_cycle=decision_cycle).count() == 2
        assert not [r for r in caplog.records if r.getMessage() == 'people_already_identified_in_dc']
        people_call = [c for c in result['run'].sub_calls if c['stage'] == 'people'][0]
        assert people_call['dropped_by_safety_filter'] == 0

    def test_n2_participant_contact_known_from_activity_a_is_created_again_for_activity_b(
        self, account, activity, user_a, contact, decision_cycle,  # noqa: F811
        fake_provider, patch_active_provider,
    ):
        _attach_cycle(activity, decision_cycle)
        existing = _existing_people(activity, user_a, decision_cycle, contact=contact)
        activity_b = _second_activity(account, user_a, decision_cycle)
        activity_b.contacts.add(contact)

        result = _run(account, activity_b, user_a, fake_provider, [
            _person(participant_ref='P1'),
        ])

        [signal] = _people(result)
        assert signal.id != existing.id
        assert signal.target_contact_id == contact.id
        assert signal.source_activity_id == activity_b.id
        assert PeopleSignal.objects.filter(target_contact=contact).count() == 2

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
