# backend/tests/ai_pipelines/test_prep_call_activity_roster.py
"""
Sprint 2 Game Plan — sub-step G4: ONE roster per activity, the point of the
Game Plan's people (TD-46 / TD-48, PO: every participant, one angle per
person; first names only).

Before: the prep call named no participant at all — at most the single
`target_contact` (removed in S2); the activity's contacts and stakeholders
never reached the prompt.

Now: ai_pipelines/services/llm_people.activity_roster(activity):
  * starts from cycle_roster(dc) — the cycle's people, so a label is the
    one the deal health uses — or an empty LLMPeopleRoster without a cycle;
  * adds the activity's participants, read through bounded querysets —
    the contacts by participant_refs.ordered_participants (tenant AND
    account), the stakeholders of the activity's cycle on its account —
    EVERY one registered BEFORE any label is read (the label() without add()
    trap: an unregistered person gets a bare first name, no homonym ref);
  * per participant: label (first name; « P1 Marc » / « P2 Marc » for
    homonyms), contact and/or stakeholder, role (the stakeholder's current
    signal), department, the profile VALUES (never their source / author);
  * and the way back: label -> participant (the roster's identity_of — the
    server resolves a person, never the LLM).
NEVER a last name, an email or a phone in what reaches the LLM.

Real path: POST /module-ai-pipelines/prep-call/run/ with the real
PrepCallPipeline; the fake provider records the prompt. Unit tests on
activity_roster for the cases of the plan.

DB: Postgres.
"""

import json

import pytest

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.signals.constants import PeopleRole, SignalSource, SignalStatus

from tests.ai_pipelines.test_prep_call_not_an_analysis import _VALID_BRIEF
from tests.signals.test_signal_cycle_attachment import TODAY, _cycle


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/prep-call/run/'
LAST_NAMES = ('Dupont', 'Durand', 'Martin', 'Lumbergh')


# =============================================================================
# FIXTURES / HELPERS
# =============================================================================

@pytest.fixture
def provider(patch_active_provider):
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)
    return patch_active_provider


def _contact(account, user, first, last, email):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name=first, last_name=last, email=email,
                phone_number='+33612345678', job_title='Finance lead')
    c.save(user=user, client_id=account.client_id)
    return c


def _stakeholder(cycle, user, full_name, contact=None, role=None, profile=None):
    from app_modules.decision_cycles.models import Stakeholder
    from app_modules.signals.models import PeopleSignal
    signal = None
    if role:
        signal = PeopleSignal(account=cycle.account, decision_cycle=cycle, target_contact=contact,
                              source=SignalSource.LLM_EXTRACTED, role=role, full_name=full_name,
                              source_quote=f'{full_name} said so', confidence=0.8)
        signal.save(user=user, client_id=cycle.client_id)
        PeopleSignal.objects.filter(pk=signal.pk).update(status=SignalStatus.VALIDATED)
        signal.refresh_from_db()
    s = Stakeholder(decision_cycle=cycle, full_name=full_name, contact=contact,
                    current_signal=signal, profile=profile or {})
    s.save(user=user, client_id=cycle.client_id)
    return s


def _profile_entry(value):
    return {'value': value, 'source': 'MANUAL', 'updated_at': '2026-11-01T10:00:00Z',
            'updated_by': 'someone@tenant-a.test', 'original_value': value}


@pytest.fixture
def scene(account, user_a, client_account_a):
    """A meeting of a cycle: two « Marc » (homonyms, one of them a profiled
    stakeholder), a stakeholder with no contact (Lea), and a contact of ANOTHER
    account of the tenant forced onto the activity (must be ignored)."""
    from app_modules.accounts.models import CompanyAccount
    cycle = _cycle(account, user_a)
    marc_1 = _contact(account, user_a, 'Marc', 'Dupont', 'marc.dupont@client.test')
    marc_2 = _contact(account, user_a, 'Marc', 'Durand', 'marc.durand@client.test')
    _stakeholder(cycle, user_a, 'Marc Dupont', contact=marc_1, role=PeopleRole.ECONOMIC_BUYER,
                 profile={'communication_language': _profile_entry('fr'),
                          'frustrations': _profile_entry('Month-end close takes ten days.')})
    lea = _stakeholder(cycle, user_a, 'Lea Martin')
    other = CompanyAccount(company_name='Initech', has_buying_decision=True)
    other.save(user=user_a, client_id=client_account_a.id)
    outsider = _contact(other, user_a, 'Bill', 'Lumbergh', 'bill@initech.test')

    meeting = Activity(title='Business case review', activity_type=ActivityType.MEETING,
                       status=ActivityStatus.PLANNED, account=account, owner=user_a,
                       decision_cycle=cycle, decision_step=cycle.qualification,
                       scheduled_date=TODAY)
    meeting.save(user=user_a, client_id=account.client_id)
    meeting.contacts.add(marc_1, marc_2, outsider)   # the outsider bypasses the rules (ORM)
    meeting.stakeholders.add(lea)
    return {'cycle': cycle, 'meeting': meeting, 'marc_1': marc_1, 'marc_2': marc_2,
            'lea': lea, 'outsider': outsider}


def _prompt(api, activity, provider):
    resp = api.post(RUN_URL, {'activity_id': str(activity.id)}, format='json')
    assert resp.status_code == 201, resp.content
    prompts = [c['user'] for c in provider.calls if c['stage'] == 'prep_call']
    assert len(prompts) == 1, provider.calls
    return prompts[0]


# =============================================================================
# THE REPRO — every participant reaches the prompt, first names only
# =============================================================================

def test_every_participant_reaches_the_prompt_by_first_name(authed_api_a, scene, provider):
    prompt = _prompt(authed_api_a, scene['meeting'], provider)

    assert 'PARTICIPANTS' in prompt
    assert 'P1 Marc' in prompt and 'P2 Marc' in prompt
    assert 'Lea' in prompt
    for last_name in LAST_NAMES:
        assert last_name not in prompt, last_name
    assert '@' not in prompt                       # no email
    assert '612345678' not in prompt               # no phone
    assert 'Bill' not in prompt                    # another account: ignored
    # The profile VALUES reach the prompt, never their metadata.
    assert 'Month-end close takes ten days.' in prompt
    assert 'someone@tenant-a.test' not in prompt


# =============================================================================
# UNIT — activity_roster
# =============================================================================

def activity_roster(activity):
    from app_modules.ai_pipelines.services.llm_people import activity_roster as build
    return build(activity)


def _by_contact(roster, contact):
    [p] = [p for p in roster.participants if p['contact_id'] == str(contact.id)]
    return p


def test_homonyms_get_a_reference_and_the_way_back_resolves_them(scene):
    roster = activity_roster(scene['meeting'])

    labels = {_by_contact(roster, scene['marc_1'])['label'],
              _by_contact(roster, scene['marc_2'])['label']}
    assert {label.split(' ')[0] for label in labels} == {'P1', 'P2'}
    for contact in (scene['marc_1'], scene['marc_2']):
        p = _by_contact(roster, contact)
        assert roster.participant_for_label(p['label']) is p
    assert roster.participant_for_label('Marc') is None      # ambiguous, never guessed
    assert roster.participant_for_label('Nobody') is None


def test_a_profiled_stakeholder_carries_its_role_and_profile_values(scene):
    p = _by_contact(activity_roster(scene['meeting']), scene['marc_1'])

    assert p['stakeholder_id'] is not None
    assert p['role']                                          # its current signal's role
    assert p['profile'] == {'communication_language': 'fr',
                            'frustrations': 'Month-end close takes ten days.'}


def test_a_contact_who_is_not_a_stakeholder_has_no_role_nor_profile(scene):
    p = _by_contact(activity_roster(scene['meeting']), scene['marc_2'])

    assert p['stakeholder_id'] is None
    assert p['role'] is None
    assert p['profile'] == {}


def test_a_stakeholder_without_contact_is_a_participant(scene):
    roster = activity_roster(scene['meeting'])

    [lea] = [p for p in roster.participants if p['stakeholder_id'] == str(scene['lea'].id)]
    assert lea['contact_id'] is None
    assert lea['label'] == 'Lea'


def test_a_participant_of_another_account_is_ignored(scene):
    roster = activity_roster(scene['meeting'])

    assert all(p['contact_id'] != str(scene['outsider'].id) for p in roster.participants)
    assert len(roster.participants) == 3


def test_without_a_cycle_the_contacts_are_still_the_participants(account, user_a):
    marc = _contact(account, user_a, 'Marc', 'Dupont', 'marc.dupont@client.test')
    call = Activity(title='Cold call', activity_type=ActivityType.CALL,
                    status=ActivityStatus.PLANNED, account=account, owner=user_a,
                    scheduled_date=TODAY)
    call.save(user=user_a, client_id=account.client_id)
    call.contacts.add(marc)

    roster = activity_roster(call)

    [p] = roster.participants
    assert p['label'] == 'Marc'
    assert p['stakeholder_id'] is None and p['role'] is None and p['profile'] == {}
