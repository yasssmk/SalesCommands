# backend/tests/ai_pipelines/test_attribution_by_name.py
"""
TD-279 B4a / B4b — the SERVER links a name as written by the LLM to a
contact registered on the activity (People full_name, Blocker
raised_by_name), through the REAL pipeline path (FakeProvider ->
persist_stage). Since B4b the LLM gets no contact list and no participant
reference ("P1") at all.

  * People "Criminelle Husky" -> linked; "Isabelle Roux" -> not linked; the
    TD-279 smoke (Isabelle twice, Criminelle registered) -> one Isabelle,
    nothing on Criminelle.
  * Blocker raised_by_name "Thomas Lefèvre" -> not linked; "Criminelle" ->
    linked.
  * Several registered contacts match the name -> not linked (no guess);
    the full name settles it when only one contact matches both names.
  * Only the contacts registered on the activity, filtered on tenant AND
    account.
  * Prompts: no contact in any context (context v8 / next_steps v4), people
    v6 without participant_ref, blocker v3 with raised_by_name.
"""

import json

import pytest

from app_modules.signals.constants import InfluenceLevel, PeopleRole

# Cross-account fixture re-used from the signals conftest.
from tests.signals.conftest import other_account, other_account_contact  # noqa: F401


pytestmark = pytest.mark.django_db

TRANSCRIPT = 'Démo SalesCommands – Logistix. Isabelle Roux, notre DAF, tient le budget.'


def _contact(account, user_a, activity, first_name, last_name, department=None):
    from app_modules.contacts.models import Contact
    from app_modules.core_modules.models import StandardDepartment
    dept = None
    if department:
        dept, _ = StandardDepartment.objects.get_or_create(name=department)
    c = Contact(
        account=account, first_name=first_name, last_name=last_name,
        standard_department=dept,
    )
    c.save(user=user_a, client_id=account.client_id)
    activity.contacts.add(c)
    return c


@pytest.fixture
def criminelle(db, account, user_a, activity):
    """The registered contact of the TD-279 smoke (Finance)."""
    return _contact(account, user_a, activity, 'Criminelle', 'Husky', 'Finance')


def _run(account, activity, user_a, fake_provider, **replies):
    from app_modules.ai_pipelines.pipelines.transcript_signals import (
        QualificationSignalsPipeline,
    )
    fake_provider.replies = {
        stage: json.dumps({'signals': signals}) for stage, signals in replies.items()
    }
    return QualificationSignalsPipeline().run(
        transcript=TRANSCRIPT, activity=activity, user=user_a,
        client_id=account.client_id,
    )['signals_by_stage']


def _person(full_name, **overrides):
    payload = {
        'full_name': full_name,
        'role': PeopleRole.CHAMPION.value,
        'influence': InfluenceLevel.HIGH.value,
        'department': None,
        'notes': 'Pushes the project internally.',
        'source_quote': "C'est moi qui préparerai les chiffres du business case.",
        'confidence': 0.9,
        'is_inferred': False,
    }
    payload.update(overrides)
    return payload


def _blocker(raised_by_name):
    return {
        'summary': 'The CIO blocked the last SaaS project.',
        'source_quote': 'il a bloqué le dernier projet de ce type',
        'confidence': 0.85,
        'is_inferred': False,
        'raised_by_name': raised_by_name,
    }


# =============================================================================
# PEOPLE — full_name as written
# =============================================================================

class TestPeopleLinkedByName:

    def test_a_registered_contact_named_in_full_is_linked(
        self, account, activity, user_a, criminelle,
        fake_provider, patch_active_provider,
    ):
        [signal] = _run(account, activity, user_a, fake_provider,
                        people=[_person('Criminelle Husky')])['people']
        signal.refresh_from_db()
        assert signal.target_contact_id == criminelle.id
        # Same effect as a resolved reference: name + department of the contact.
        assert signal.full_name == 'Criminelle Husky'
        assert signal.target_department.name == 'Finance'

    def test_b_a_cited_person_who_is_not_registered_is_not_linked(
        self, account, activity, user_a, criminelle,
        fake_provider, patch_active_provider,
    ):
        [signal] = _run(account, activity, user_a, fake_provider,
                        people=[_person('Isabelle Roux')])['people']
        assert signal.target_contact_id is None
        assert signal.full_name == 'Isabelle Roux'

    def test_two_mentions_of_the_same_contact_merge(
        self, account, activity, user_a, criminelle,
        fake_provider, patch_active_provider,
    ):
        # The link is set BEFORE the in-extraction dedup: "Criminelle" and
        # "Criminelle Husky" are ONE person.
        [signal] = _run(account, activity, user_a, fake_provider, people=[
            _person('Criminelle'),
            _person('Criminelle Husky', source_quote='Je valide les hypothèses de coût.'),
        ])['people']
        assert signal.target_contact_id == criminelle.id


    def test_td279_smoke_the_cited_cfo_is_never_put_on_the_registered_contact(
        self, account, activity, user_a, criminelle,
        fake_provider, patch_active_provider,
    ):
        quote = ('Mais avant ça, on devra forcément faire un rendez-vous avec '
                 'Isabelle Roux, notre DAF. C\'est elle qui tient le budget.')
        [signal] = _run(account, activity, user_a, fake_provider, people=[
            _person('Isabelle Roux', role=PeopleRole.DECISION_MAKER.value,
                    department='Finance', source_quote=quote),
            _person('Isabelle Roux', department='Finance', source_quote=quote),
        ])['people']
        assert signal.full_name == 'Isabelle Roux'
        assert signal.target_contact_id is None
        from app_modules.signals.models import PeopleSignal
        assert not PeopleSignal.objects.filter(target_contact=criminelle).exists()


# =============================================================================
# BLOCKER — raised_by_name as written
# =============================================================================

class TestBlockerLinkedByName:

    def test_c_a_speaker_who_is_not_registered_is_not_linked(
        self, account, activity, user_a, criminelle,
        fake_provider, patch_active_provider,
    ):
        [signal] = _run(account, activity, user_a, fake_provider,
                        blocker=[_blocker('Thomas Lefèvre')])['blocker']
        assert signal.contact_id is None

    def test_c_the_registered_contact_is_linked_by_first_name(
        self, account, activity, user_a, criminelle,
        fake_provider, patch_active_provider,
    ):
        [signal] = _run(account, activity, user_a, fake_provider,
                        blocker=[_blocker('Criminelle')])['blocker']
        signal.refresh_from_db()
        assert signal.contact_id == criminelle.id

    def test_a_null_name_is_not_linked(
        self, account, activity, user_a, criminelle,
        fake_provider, patch_active_provider,
    ):
        [signal] = _run(account, activity, user_a, fake_provider,
                        blocker=[_blocker(None)])['blocker']
        assert signal.contact_id is None


# =============================================================================
# AMBIGUITY + SCOPE
# =============================================================================

class TestNoGuessAndScope:

    def test_d_two_registered_contacts_match_the_name_none_is_linked(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        _contact(account, user_a, activity, 'Marie', 'Dupont')
        _contact(account, user_a, activity, 'Marie', 'Curie')
        stages = _run(account, activity, user_a, fake_provider,
                      people=[_person('Marie')], blocker=[_blocker('Marie')])
        assert stages['people'][0].target_contact_id is None
        assert stages['blocker'][0].contact_id is None

    def test_the_full_name_settles_two_homonym_first_names(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        dupont = _contact(account, user_a, activity, 'Marie', 'Dupont')
        _contact(account, user_a, activity, 'Marie', 'Curie')
        stages = _run(account, activity, user_a, fake_provider,
                      people=[_person('Marie Dupont')], blocker=[_blocker('Marie Dupont')])
        assert stages['people'][0].target_contact_id == dupont.id
        assert stages['blocker'][0].contact_id == dupont.id

    def test_a_contact_of_another_account_is_never_linked(
        self, account, activity, user_a, other_account_contact,  # noqa: F811
        fake_provider, patch_active_provider,
    ):
        activity.contacts.add(other_account_contact)
        name = f'{other_account_contact.first_name} {other_account_contact.last_name}'
        stages = _run(account, activity, user_a, fake_provider,
                      people=[_person(name)], blocker=[_blocker(name)])
        assert stages['people'][0].target_contact_id is None
        assert stages['blocker'][0].contact_id is None


# =============================================================================
# B4b — prompts without participant references (people v6, blocker v3,
# context v8, next_steps context v4)
# =============================================================================

def _flat(text):
    return ' '.join(text.split())


class TestPromptsWithoutReferences:

    @pytest.mark.parametrize('stage', [
        'pain_impact', 'pain', 'objective', 'impact', 'techstack', 'blocker',
        'constraint', 'competitor', 'people',
    ])
    def test_context_lists_no_contact(self, stage, activity, criminelle):
        from app_modules.ai_pipelines.prompts.transcript_signals.context import (
            build_context_layer,
        )
        context = build_context_layer(activity, stage)
        assert 'Prospect contacts' not in context
        assert 'Criminelle' not in context
        assert 'P1' not in context

    def test_next_steps_context_lists_no_contact(self, activity, criminelle):
        from app_modules.ai_pipelines.prompts.next_steps.context import (
            build_context_layer,
        )
        context = build_context_layer(activity)
        assert 'Prospect contacts' not in context
        assert 'Criminelle' not in context

    def test_people_prompt_has_no_reference(self):
        from app_modules.ai_pipelines.prompts.transcript_signals.people_v1 import (
            build_people_request,
        )
        prompt = _flat(build_people_request('TRANSCRIPT'))
        for gone in ('participant_ref', 'ATTRIBUTION RULES', 'P<n>',
                     'A contact listed in the SESSION CONTEXT',
                     'NOT listed in the SESSION CONTEXT', 'listed contact'):
            assert gone not in prompt
        assert ("`full_name` = the person's name exactly as written in the "
                'transcript: the speaker label for a person who speaks, the '
                'name as cited otherwise.') in prompt
        # Kept from v5.
        assert 'NEVER transfer to one person what the transcript says about ANOTHER' in prompt
        assert 'A DEDUCTION from what the transcript says is allowed' in prompt

    def test_blocker_prompt_asks_the_speaker_name(self):
        from app_modules.ai_pipelines.prompts.transcript_signals.blocker_v1 import (
            build_blocker_request,
        )
        prompt = _flat(build_blocker_request('TRANSCRIPT'))
        assert '"raised_by_name":' in prompt
        assert 'ATTRIBUTION RULES (raised_by_name)' in prompt
        assert ('Set `raised_by_name` to the name of the PROSPECT-side speaker '
                'who voiced the blocker, exactly as written in the speaker label.') in prompt
        assert 'NEVER output a name that does not appear in the transcript.' in prompt
        assert 'never the seller' in prompt
        for gone in ('"raised_by":', 'exactly ONE prospect participant', 'P<n>', 'P1'):
            assert gone not in prompt

    def test_versions(self):
        from app_modules.ai_pipelines.prompts.next_steps import context as next_steps_context
        from app_modules.ai_pipelines.prompts.transcript_signals.blocker_v1 import (
            BLOCKER_PROMPT_VERSION,
        )
        from app_modules.ai_pipelines.prompts.transcript_signals.context import CONTEXT_VERSION
        from app_modules.ai_pipelines.prompts.transcript_signals.people_v1 import (
            PEOPLE_PROMPT_VERSION,
        )
        assert PEOPLE_PROMPT_VERSION == 'v7'
        assert BLOCKER_PROMPT_VERSION == 'v4'
        assert CONTEXT_VERSION == 'v8'
        assert next_steps_context.CONTEXT_VERSION == 'v4'
