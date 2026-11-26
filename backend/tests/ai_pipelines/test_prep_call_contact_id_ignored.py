# backend/tests/ai_pipelines/test_prep_call_contact_id_ignored.py
"""
Sprint 2 Game Plan — sub-step S2 (C2-11 / TD-325, PO decision Q8): the
prep-call run endpoint no longer takes a `contact_id`.

Before: POST /module-ai-pipelines/prep-call/run/ accepted an optional
`contact_id`, resolved on the TENANT only (prep_call_serializer.py:80-89) —
never against the activity's account nor its participants. The contact then
drove the brief (« Primary contact » / « STAKEHOLDER FOCUS » in the prompt)
and was persisted on the PrepCallSnapshot (`target_contact`). A contact of
ANOTHER account of the same tenant was accepted.

No caller uses it: the front always sends null
(sections/activities/workspace/ActivityPreparationTab.jsx:48) and the Game
Plan takes every participant of the activity, server-side (TD-46 / TD-48).
The input field is removed — no FK received, no hole. The model column
stays, to read the v1 snapshots.

Real path: POST /module-ai-pipelines/prep-call/run/ with the real
PrepCallPipeline (fake LLM provider, tests/ai_pipelines/conftest.py). A
`contact_id` sent is ignored: nothing reaches the prompt, nothing is
persisted, the run succeeds.

DB: Postgres.
"""

import json

import pytest

from app_modules.ai_pipelines.models import PrepCallSnapshot

from tests.ai_pipelines.test_prep_call_not_an_analysis import _VALID_BRIEF, _preparable_activity


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/prep-call/run/'


@pytest.fixture
def activity(account, user_a):
    return _preparable_activity(account, user_a)


@pytest.fixture
def prep_call_provider(patch_active_provider):
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)
    return patch_active_provider


def _contact(account, user, first_name='Lea'):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name=first_name, last_name='Martin')
    c.save(user=user, client_id=account.client_id)
    return c


def _second_account(client_account, user):
    from app_modules.accounts.models import CompanyAccount
    acc = CompanyAccount(company_name='Initech', has_buying_decision=True)
    acc.save(user=user, client_id=client_account.id)
    return acc


def _run(api, activity, contact):
    return api.post(RUN_URL, {
        'activity_id': str(activity.id),
        'contact_id': str(contact.id),
    }, format='json')


def _prompt(provider):
    prompts = [c['user'] for c in provider.calls if c['stage'] == 'prep_call']
    assert len(prompts) == 1, provider.calls  # the real pipeline ran once
    return prompts[0]


def _assert_ignored(resp, provider, activity):
    assert resp.status_code == 201, resp.content
    snapshot = PrepCallSnapshot.objects.get(activity=activity)
    assert snapshot.target_contact_id is None
    assert resp.json()['data']['snapshot']['target_contact'] is None
    prompt = _prompt(provider)
    assert 'Primary contact' not in prompt
    assert 'STAKEHOLDER FOCUS' not in prompt


def test_a_contact_of_the_account_is_ignored(
    authed_api_a, activity, account, user_a, prep_call_provider,
):
    contact = _contact(account, user_a)

    resp = _run(authed_api_a, activity, contact)

    _assert_ignored(resp, prep_call_provider, activity)


def test_a_contact_of_another_account_is_ignored(
    authed_api_a, activity, user_a, client_account_a, prep_call_provider,
):
    other = _second_account(client_account_a, user_a)
    contact = _contact(other, user_a, first_name='Bill')

    resp = _run(authed_api_a, activity, contact)

    _assert_ignored(resp, prep_call_provider, activity)
