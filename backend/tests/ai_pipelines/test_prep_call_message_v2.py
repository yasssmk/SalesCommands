# backend/tests/ai_pipelines/test_prep_call_message_v2.py
"""
Sprint 2 Game Plan — sub-step G11: the strict « message » schema and the
language per recipient (PO decisions Q2, Q3, Q7).

Before: an email / a LinkedIn activity got the PLAN (G10 schema) in
output_kind MESSAGE — no message, no recipient, no language.

Now:
  * PREP_CALL_MESSAGE_SCHEMA: per recipient {ref, language, subject (email
    only, null for LinkedIn), body}, each in its target language — ONE LLM
    call, at most PREP_CALL_MESSAGE_RECIPIENTS_MAX recipients (Q7);
  * the recipients are the roster's (G4) participants with a contact; a
    stakeholder without contact gets no message (Q2);
  * resolve_message_language (Q3) reads the stakeholder profile's
    communication_language: manual -> PROFILE, AI -> EXCHANGES, else
    'en' -> DEFAULT (a contact without stakeholder: DEFAULT);
  * GET prep-call/message-languages/<id>/: the preview {ref, first_name,
    language, source} before the generation;
  * the POST takes language_overrides [{ref, language}]: the tag validated by
    the decision_cycles validator, the recipient resolved by the roster — an
    unknown one is a standard 400 (unknown / foreign: the same answer); an
    override enters the hash v2;
  * the plan's guardrails: no last name (no longer: no rhetoric label, G13g),
    refs resolved,
    never guessed.

Real path: POST /module-ai-pipelines/prep-call/run/ (real view and
pipeline; the fake provider records the call options and the prompt).

DB: Postgres.
"""

import json

import pytest
from rest_framework.test import APIClient

from app_modules.activities.constants import ActivityType
from app_modules.activities.models import Activity
from app_modules.ai_pipelines.constants import (
    PREP_CALL_MESSAGE_RECIPIENTS_MAX,
    PREP_CALL_NO_RECIPIENT_CODE,
    PREP_CALL_NOTHING_NEW_CODE,
    AIPipelineStatus,
)
from app_modules.ai_pipelines.models import AIPipelineRun, PrepCallSnapshot
from app_modules.signals.constants import SignalSource

from tests.ai_pipelines.test_prep_call_activity_roster import _contact, _stakeholder
from tests.ai_pipelines.test_prep_call_not_an_analysis import _preparable_activity


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/prep-call/run/'
LANGUAGES_URL = '/module-ai-pipelines/prep-call/message-languages/{id}/'


def _language(value, source):
    return {'communication_language': {
        'value': value, 'source': source, 'updated_at': '2026-11-01T10:00:00Z',
        'updated_by': None, 'original_value': None,
    }}


def _email(account, user, activity_type=ActivityType.EMAIL):
    activity = _preparable_activity(account, user)
    Activity.objects.filter(pk=activity.pk).update(activity_type=activity_type)
    activity.refresh_from_db()
    return activity


@pytest.fixture
def scene(account, user_a):
    """An email of a cycle: Claire (a manual « fr »), Omar (« es » found by the
    AI), Nina (a contact, no stakeholder) and Lea (a stakeholder WITHOUT
    contact)."""
    email = _email(account, user_a)
    cycle = email.decision_cycle
    claire = _contact(account, user_a, 'Claire', 'Morel', 'claire@client.test')
    omar = _contact(account, user_a, 'Omar', 'Haddad', 'omar@client.test')
    nina = _contact(account, user_a, 'Nina', 'Rossi', 'nina@client.test')
    _stakeholder(cycle, user_a, 'Claire Morel', contact=claire,
                 profile=_language('fr', SignalSource.MANUAL))
    _stakeholder(cycle, user_a, 'Omar Haddad', contact=omar,
                 profile=_language('es', SignalSource.LLM_EXTRACTED))
    lea = _stakeholder(cycle, user_a, 'Lea Martin', profile=_language('it', SignalSource.MANUAL))
    email.contacts.add(claire, omar, nina)
    email.stakeholders.add(lea)
    return {'email': email, 'cycle': cycle}


def _message(ref, language, body=None, subject='Our next step'):
    return {'ref': ref, 'language': language, 'subject': subject,
            'body': body or f'Hello {ref}, shall we book the pilot review next week?'}


_ANSWER = {'messages': [_message('Claire', 'fr'), _message('Omar', 'es'), _message('Nina', 'en')]}


def _post(api, activity, provider, answer=_ANSWER, status=201, **payload):
    provider.replies['prep_call'] = json.dumps(answer)
    resp = api.post(RUN_URL, {'activity_id': str(activity.id), **payload}, format='json')
    assert resp.status_code == status, resp.content
    return resp


def _messages(activity):
    snapshot = PrepCallSnapshot.objects.filter(activity=activity).latest('snapshot_date')
    return {m['ref']: m for m in snapshot.brief['messages']}


def _runs(activity):
    return AIPipelineRun.objects.filter(source_activity=activity).count()


# =============================================================================
# THE REPROS — the language of each recipient, and its source
# =============================================================================

@pytest.mark.parametrize('ref, language, source', [
    ('Claire', 'fr', 'PROFILE'),        # a manual profile value
    ('Omar', 'es', 'EXCHANGES'),        # a value the AI found
    ('Nina', 'en', 'DEFAULT'),          # no hint: a contact without stakeholder
])
def test_each_recipient_gets_a_message_in_its_language(
    authed_api_a, scene, patch_active_provider, ref, language, source,
):
    _post(authed_api_a, scene['email'], patch_active_provider)

    message = _messages(scene['email'])[ref]
    assert message['language'] == language
    assert message['language_source'] == source
    assert message['subject'] == 'Our next step'
    snapshot = PrepCallSnapshot.objects.get(activity=scene['email'])
    assert snapshot.output_kind == 'MESSAGE' and snapshot.schema_version == 2


def test_one_llm_call_with_the_message_schema_and_the_recipients(
    authed_api_a, scene, patch_active_provider,
):
    from app_modules.ai_pipelines.prompts.prep_call.message_v2 import PREP_CALL_MESSAGE_SCHEMA

    _post(authed_api_a, scene['email'], patch_active_provider)

    [call] = patch_active_provider.calls_for('prep_call')            # ONE call
    assert call['extra'].get('response_schema') == PREP_CALL_MESSAGE_SCHEMA
    assert 'Claire — language: fr' in call['user']
    assert 'Omar — language: es' in call['user']
    assert 'Nina — language: en' in call['user']
    assert "in the language\n    given for its recipient" in call['system']
    run = AIPipelineRun.objects.get(source_activity=scene['email'])
    assert run.prompt_versions == {'system': 'v2.3', 'context': 'v2', 'message': 'v2'}


def test_a_user_edited_ai_value_is_a_profile_language():
    from app_modules.ai_pipelines.services.prep_call.message_language import (
        resolve_message_language,
    )
    entry = _language('de', SignalSource.LLM_MODIFIED)['communication_language']
    assert resolve_message_language({'language_entry': entry}) == {
        'language': 'de', 'source': 'PROFILE'}
    assert resolve_message_language({'language_entry': None}) == {
        'language': 'en', 'source': 'DEFAULT'}


# =============================================================================
# Q2 — a stakeholder without contact gets no message
# =============================================================================

def test_a_stakeholder_without_contact_gets_no_message(authed_api_a, scene, patch_active_provider):
    answer = {'messages': [*_ANSWER['messages'], _message('Lea', 'it')]}

    _post(authed_api_a, scene['email'], patch_active_provider, answer)

    assert set(_messages(scene['email'])) == {'Claire', 'Omar', 'Nina'}
    [call] = patch_active_provider.calls_for('prep_call')
    assert 'Lea — language' not in call['user']
    run = AIPipelineRun.objects.get(source_activity=scene['email'])
    assert run.sub_calls[0]['persist_counts']['unknown_refs'] == ['Lea']


def test_a_stakeholder_with_a_contact_is_a_recipient(authed_api_a, account, user_a, patch_active_provider):
    """Attached as a stakeholder only, but it has a contact: a recipient (Q2),
    in its profile's language."""
    email = _email(account, user_a)
    paul = _contact(account, user_a, 'Paul', 'Garnier', 'paul@client.test')
    email.stakeholders.add(_stakeholder(email.decision_cycle, user_a, 'Paul Garnier', contact=paul,
                                        profile=_language('fr', SignalSource.MANUAL)))

    _post(authed_api_a, email, patch_active_provider, {'messages': [_message('Paul', 'fr')]})

    assert _messages(email)['Paul']['language_source'] == 'PROFILE'


def test_no_recipient_is_an_info_without_llm_call(authed_api_a, account, user_a, patch_active_provider):
    email = _email(account, user_a)
    lea = _stakeholder(email.decision_cycle, user_a, 'Lea Martin')
    email.stakeholders.add(lea)

    resp = _post(authed_api_a, email, patch_active_provider, status=200)

    assert resp.json()['code'] == PREP_CALL_NO_RECIPIENT_CODE
    assert patch_active_provider.calls_for('prep_call') == []
    assert _runs(email) == 0


# =============================================================================
# Q7 — the recipients are capped
# =============================================================================

def test_beyond_the_cap_the_recipients_are_bounded(
    authed_api_a, account, user_a, patch_active_provider,
):
    email = _email(account, user_a)
    names = [f'Person{chr(65 + i)}' for i in range(PREP_CALL_MESSAGE_RECIPIENTS_MAX + 2)]
    for i, first in enumerate(names):
        email.contacts.add(_contact(account, user_a, first, f'Zed{chr(65 + i)}', f'p{i}@client.test'))
    answer = {'messages': [_message(n, 'en') for n in names]}

    _post(authed_api_a, email, patch_active_provider, answer)

    [call] = patch_active_provider.calls_for('prep_call')
    assert call['user'].count(' — language: ') == PREP_CALL_MESSAGE_RECIPIENTS_MAX
    assert len(_messages(email)) == PREP_CALL_MESSAGE_RECIPIENTS_MAX
    preview = authed_api_a.get(LANGUAGES_URL.format(id=email.id)).json()['data']
    assert len(preview['recipients']) == PREP_CALL_MESSAGE_RECIPIENTS_MAX
    assert preview['omitted_count'] == 2


# =============================================================================
# OVERRIDES — applied, validated, resolved by the roster, in the hash
# =============================================================================

def test_an_override_is_applied(authed_api_a, scene, patch_active_provider):
    answer = {'messages': [_message('Claire', 'fr'), _message('Omar', 'es'), _message('Nina', 'de')]}

    _post(authed_api_a, scene['email'], patch_active_provider, answer,
          language_overrides=[{'ref': 'Nina', 'language': 'de'}])

    nina = _messages(scene['email'])['Nina']
    assert nina['language'] == 'de' and nina['language_source'] == 'OVERRIDE'
    [call] = patch_active_provider.calls_for('prep_call')
    assert 'Nina — language: de' in call['user']


@pytest.mark.parametrize('ref', ['Zoe', 'Lea'])
def test_an_override_to_an_unknown_recipient_is_a_standard_400(
    authed_api_a, scene, patch_active_provider, ref,
):
    """Zoe: nobody; Lea: a participant WITHOUT contact — not a recipient.
    The same answer, nothing run."""
    resp = _post(authed_api_a, scene['email'], patch_active_provider, status=400,
                 language_overrides=[{'ref': ref, 'language': 'fr'}])

    assert f"Unknown recipient '{ref}'" in json.dumps(resp.json())
    assert patch_active_provider.calls_for('prep_call') == [] and _runs(scene['email']) == 0


def test_an_override_to_a_foreign_contact_gets_the_same_400(
    authed_api_a, scene, patch_active_provider, user_a, client_account_a,
):
    from app_modules.accounts.models import CompanyAccount
    other = CompanyAccount(company_name='Initech', has_buying_decision=True)
    other.save(user=user_a, client_id=client_account_a.id)
    bill = _contact(other, user_a, 'Bill', 'Lumbergh', 'bill@initech.test')
    scene['email'].contacts.add(bill)                  # another account (ORM bypass)

    unknown = _post(authed_api_a, scene['email'], patch_active_provider, status=400,
                    language_overrides=[{'ref': 'Zoe', 'language': 'fr'}]).json()
    foreign = _post(authed_api_a, scene['email'], patch_active_provider, status=400,
                    language_overrides=[{'ref': 'Bill', 'language': 'fr'}]).json()

    assert json.dumps(foreign).replace('Bill', 'X') == json.dumps(unknown).replace('Zoe', 'X')


def test_an_invalid_language_tag_is_a_standard_400(authed_api_a, scene, patch_active_provider):
    resp = _post(authed_api_a, scene['email'], patch_active_provider, status=400,
                 language_overrides=[{'ref': 'Nina', 'language': 'french!'}])

    assert "Invalid language 'french!'" in json.dumps(resp.json())
    assert _runs(scene['email']) == 0


def test_an_override_enters_the_hash(authed_api_a, scene, patch_active_provider):
    _post(authed_api_a, scene['email'], patch_active_provider)
    same = _post(authed_api_a, scene['email'], patch_active_provider, status=200)
    assert same.json()['code'] == PREP_CALL_NOTHING_NEW_CODE

    answer = {'messages': [_message('Claire', 'fr'), _message('Omar', 'es'), _message('Nina', 'de')]}
    _post(authed_api_a, scene['email'], patch_active_provider, answer,
          language_overrides=[{'ref': 'Nina', 'language': 'de'}])

    assert PrepCallSnapshot.objects.filter(activity=scene['email']).count() == 2


# =============================================================================
# THE GUARDRAILS — the plan's validation
# =============================================================================

def test_a_last_name_is_refused(authed_api_a, scene, patch_active_provider):
    """Renamed from test_a_label_or_a_last_name_is_refused (G13g: the
    rhetoric label is no longer refused — the last name still is, TD-317)."""
    answer = {'messages': [_message('Claire', 'fr', body='Hello Claire Morel, shall we meet?'),
                           _message('Omar', 'es'), _message('Nina', 'en')]}

    _post(authed_api_a, scene['email'], patch_active_provider, answer, status=502)

    run = AIPipelineRun.objects.get(source_activity=scene['email'])
    assert run.status == AIPipelineStatus.PARSE_ERROR and 'last name' in run.error_message
    assert not PrepCallSnapshot.objects.filter(activity=scene['email']).exists()


def test_a_rhetoric_label_in_a_message_is_no_longer_refused(authed_api_a, scene, patch_active_provider):
    answer = {'messages': [_message('Claire', 'fr', body='Hello Claire, a word on pathos.'),
                           _message('Omar', 'es'), _message('Nina', 'en')]}

    _post(authed_api_a, scene['email'], patch_active_provider, answer)

    assert PrepCallSnapshot.objects.filter(activity=scene['email']).exists()


def test_a_message_in_another_language_than_its_recipients_is_dropped(
    authed_api_a, scene, patch_active_provider,
):
    answer = {'messages': [_message('Claire', 'en'), _message('Omar', 'es'), _message('Nina', 'en')]}

    _post(authed_api_a, scene['email'], patch_active_provider, answer)

    assert set(_messages(scene['email'])) == {'Omar', 'Nina'}
    counts = AIPipelineRun.objects.get(source_activity=scene['email']).sub_calls[0]['persist_counts']
    assert counts['wrong_language_refs'] == ['Claire'] and counts['missing_refs'] == ['Claire']


def test_an_email_needs_a_subject(authed_api_a, scene, patch_active_provider):
    answer = {'messages': [_message('Claire', 'fr', subject=None), _message('Omar', 'es'),
                           _message('Nina', 'en')]}

    _post(authed_api_a, scene['email'], patch_active_provider, answer, status=502)


def test_a_linkedin_message_has_no_subject(authed_api_a, account, user_a, patch_active_provider):
    linkedin = _email(account, user_a, ActivityType.LINKEDIN)
    linkedin.contacts.add(_contact(account, user_a, 'Nina', 'Rossi', 'nina@client.test'))

    _post(authed_api_a, linkedin, patch_active_provider, {'messages': [_message('Nina', 'en')]})

    assert _messages(linkedin)['Nina']['subject'] is None
    [call] = patch_active_provider.calls_for('prep_call')
    assert 'subject: null' in call['user']


# =============================================================================
# THE LANGUAGES PREVIEW — GET, before the generation
# =============================================================================

def test_the_languages_preview(authed_api_a, scene):
    resp = authed_api_a.get(LANGUAGES_URL.format(id=scene['email'].id))

    assert resp.status_code == 200, resp.content
    assert resp.json()['data']['recipients'] == [
        # the roster's order (last name, first name): Haddad, Morel, Rossi
        {'ref': 'Omar', 'first_name': 'Omar', 'language': 'es', 'source': 'EXCHANGES'},
        {'ref': 'Claire', 'first_name': 'Claire', 'language': 'fr', 'source': 'PROFILE'},
        {'ref': 'Nina', 'first_name': 'Nina', 'language': 'en', 'source': 'DEFAULT'},
    ]
    assert 'Morel' not in resp.content.decode()           # first names only


def test_the_preview_is_empty_for_a_conversation(authed_api_a, account, user_a):
    meeting = _preparable_activity(account, user_a)
    resp = authed_api_a.get(LANGUAGES_URL.format(id=meeting.id))
    assert resp.json()['data']['recipients'] == []


def test_the_preview_needs_the_right_to_generate(scene, authenticate, client_account_a, user_a):
    from end_users.models import User
    stranger = User.objects.create(email='g11-stranger@tenant-a.test', client_account=client_account_a,
                                   role=user_a.role, is_active=True)
    client = APIClient(enforce_csrf_checks=False)
    authenticate(client, stranger, client_account_a.id)

    assert client.get(LANGUAGES_URL.format(id=scene['email'].id)).status_code == 403


def test_the_preview_of_another_tenant_is_not_found(scene, authed_api_b):
    assert authed_api_b.get(LANGUAGES_URL.format(id=scene['email'].id)).status_code == 404
