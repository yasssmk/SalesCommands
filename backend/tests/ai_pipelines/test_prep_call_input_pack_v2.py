# backend/tests/ai_pipelines/test_prep_call_input_pack_v2.py
"""
Sprint 2 Game Plan — sub-step G7: the prep call's input pack v2 — it READS
what exists (DC, deal health, signals, objectives, manager notes, campaign,
seller profile) and recalculates nothing.

Before: the pack carried the signals, the v1 maturity (global_reading +
dimensions) and the participants (G4) — none of the activity's own content
(description, call_to_action, notes, preparation notes), none of the deal
health v2, the objectives' criteria, the products, the account, the
manager notes, the seller profile nor the previous conversations. Its
dedup hash ignored all of them: two POST with a changed description gave
back the OLD snapshot.

Now the pack also carries:
  * `deal_health` — the latest snapshot through the canonical reader
    (DealHealthEvidenceBuilder.latest_snapshot): summary,
    strategic_conclusion, objectives, missing_info, top_arguments,
    stakeholders, bant, the three axes, estimated_step, and its trace
    (snapshot_id + schema_version);
  * `activity` — description, call_to_action, outcome_notes,
    preparation_notes;
  * `objectives` — the validated Objective signals with success_criteria,
    notes and target_date (the deal health's own serializer);
  * `deal` / `account` — the deal health's cycle and account contexts
    (products included), read once with the cycle's current step;
  * `manager_notes` — the deal health's reading;
  * `seller_profile` — the tenant's (G6);
  * `previous_activities` — the notes of the COMPLETED activities of the
    same cycle or of the same sequence, the most recent ones, capped
    (PREP_CALL_PREVIOUS_ACTIVITIES_MAX — PO decision Q5);
  every free text bounded by PREP_CALL_MAX_CHARS_PER_SOURCE (the deal
  health's bound).
The dedup hash v2 covers the activity's content, the participants'
identities, the deal-health snapshot id, the seller profile's update date,
the products and the previous activities' notes.
No N+1: the pack's cost does not grow with the number of participants nor
of previous activities.

Real path for the repro: POST /module-ai-pipelines/prep-call/run/ (real view
and pipeline, fake LLM provider). The pack blocks and the hash are checked on
PrepInputPackAssembler.build / PrepCallPipeline's hash. Seeded through the
ORM: the deal-health snapshot, the signals, the manager note, the product,
the seller profile, the previous activities.

DB: Postgres.
"""

import copy
import datetime
import json

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from app_modules.activities.constants import ActivityOutcome, ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.ai_pipelines.models import PrepCallSnapshot
from app_modules.ai_pipelines.pipelines.prep_call import PrepCallPipeline
from app_modules.ai_pipelines.services.prep_call.input_pack_assembler import (
    PrepInputPackAssembler,
)
from app_modules.signals.constants import (
    PeopleRole,
    ScopeLevel,
    SignalDimension,
    SignalSource,
    SignalStatus,
    SignalWhat,
)

from tests.ai_pipelines.deal_health_fixtures import V2_DIAGNOSTIC
from tests.ai_pipelines.test_prep_call_not_an_analysis import _VALID_BRIEF
from tests.signals.test_signal_cycle_attachment import TODAY, _cycle


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/prep-call/run/'


# =============================================================================
# FIXTURES / HELPERS
# =============================================================================

@pytest.fixture
def provider(patch_active_provider):
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)
    return patch_active_provider


def _contact(account, user, first, last):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name=first, last_name=last)
    c.save(user=user, client_id=account.client_id)
    return c


def _stakeholder(cycle, user, contact, role=PeopleRole.CHAMPION):
    from app_modules.decision_cycles.models import Stakeholder
    from app_modules.signals.models import PeopleSignal
    signal = PeopleSignal(account=cycle.account, decision_cycle=cycle, target_contact=contact,
                          source=SignalSource.LLM_EXTRACTED, role=role,
                          full_name=f'{contact.first_name} {contact.last_name}',
                          source_quote='said so', confidence=0.8)
    signal.save(user=user, client_id=cycle.client_id)
    PeopleSignal.objects.filter(pk=signal.pk).update(status=SignalStatus.VALIDATED)
    s = Stakeholder(decision_cycle=cycle, full_name=signal.full_name, contact=contact,
                    current_signal_id=signal.pk)
    s.save(user=user, client_id=cycle.client_id)
    return s


def _activity(account, user, cycle, *, status=ActivityStatus.PLANNED, title='Business case review',
              **fields):
    a = Activity(title=title, activity_type=ActivityType.MEETING, status=status, account=account,
                 owner=user, decision_cycle=cycle, decision_step=cycle.qualification,
                 scheduled_date=TODAY, **fields)
    a.save(user=user, client_id=account.client_id)
    return a


def _previous(account, user, cycle, notes, days_ago):
    return _activity(
        account, user, cycle, status=ActivityStatus.COMPLETED, title=f'Earlier call {days_ago}',
        outcome=ActivityOutcome.SUCCESSFUL, outcome_notes=notes,
        completed_at=timezone.now() - datetime.timedelta(days=days_ago),
    )


@pytest.fixture
def scene(account, user_a, client_account_a):
    from app_modules.decision_cycles.models import DealHealthSnapshot, DealProduct, ManagerNote
    from app_modules.product_catalog.models import ProductCatalog, SellerProfile
    from app_modules.signals.models import ObjectiveSignal

    cycle = _cycle(account, user_a)
    meeting = _activity(
        account, user_a, cycle,
        description='Walk the CFO through the business case.',
        call_to_action='Agree on the pilot scope.',
        outcome_notes='Bring the ROI sheet.',
        preparation_notes='Ask about the Q2 budget review.',
    )
    marc = _contact(account, user_a, 'Marc', 'Dupont')
    _stakeholder(cycle, user_a, marc)
    meeting.contacts.add(marc)

    diagnostic = copy.deepcopy(V2_DIAGNOSTIC)
    dh = DealHealthSnapshot(decision_cycle=cycle, diagnostic=diagnostic, schema_version=2)
    dh.save(user=user_a, client_id=cycle.client_id)

    objective = ObjectiveSignal(
        account=account, decision_cycle=cycle, source=SignalSource.MANUAL,
        status=SignalStatus.VALIDATED, what=SignalWhat.OPS, dimension=SignalDimension.TIME,
        scope_level=ScopeLevel.BUSINESS, summary='Close the month in three days',
        source_quote='We want to close in three days',
        success_criteria='A close signed off on day three.', notes='The board reviews it in June.',
        target_date=datetime.date(2027, 6, 30),
    )
    objective.save(user=user_a, client_id=account.client_id)

    product = ProductCatalog(name='Reporting suite', description='Automated reporting.',
                             value_proposition='Closes the month in two days.')
    product.save(user=user_a, client_id=account.client_id)
    DealProduct(decision_cycle=cycle, product_catalog_entry=product, quantity=3).save(
        user=user_a, client_id=account.client_id)
    ManagerNote(decision_cycle=cycle, content='Push for the CFO meeting.').save(
        user=user_a, client_id=account.client_id)
    SellerProfile(company_description='An AI-native CRM.',
                  customer_references=[{'name': 'Logistix', 'sector': 'Logistics'}]).save(
        user=user_a, client_id=account.client_id)
    _previous(account, user_a, cycle, 'They loved the forecast view.', days_ago=10)
    other_cycle = _cycle(account, user_a, name='Another deal')
    _previous(account, user_a, other_cycle, 'NOT OF THIS DEAL.', days_ago=5)
    return {'cycle': cycle, 'meeting': meeting, 'dh': dh, 'product': product}


def _pack(activity):
    activity.refresh_from_db()
    return PrepInputPackAssembler().build(activity=activity)


def _hash(activity):
    return PrepCallPipeline._compute_idempotence_hash(
        input_pack=_pack(activity), target_contact=None,
    )


# =============================================================================
# THE REPRO — a changed description makes a new Game Plan
# =============================================================================

def test_a_changed_description_is_not_deduplicated_into_the_old_snapshot(
    authed_api_a, scene, provider,
):
    meeting = scene['meeting']
    first = authed_api_a.post(RUN_URL, {'activity_id': str(meeting.id)}, format='json')
    assert first.status_code == 201, first.content
    Activity.objects.filter(pk=meeting.pk).update(description='A new agenda: the pilot.')

    second = authed_api_a.post(RUN_URL, {'activity_id': str(meeting.id)}, format='json')

    assert second.status_code == 201, second.content
    assert second.json()['data']['snapshot']['id'] != first.json()['data']['snapshot']['id']
    assert PrepCallSnapshot.objects.filter(activity=meeting).count() == 2
    prompts = [c['user'] for c in provider.calls if c['stage'] == 'prep_call']
    assert len(prompts) == 2                           # the LLM really ran twice


# =============================================================================
# EVERY BLOCK OF THE PACK
# =============================================================================

def test_every_block_of_the_pack(scene):
    pack = _pack(scene['meeting'])

    dh = pack['deal_health']
    assert dh['snapshot_id'] == str(scene['dh'].id) and dh['schema_version'] == 2
    for key in ('summary', 'strategic_conclusion', 'objectives', 'missing_info', 'top_arguments',
                'stakeholders', 'bant', 'needs_and_urgency', 'credibility', 'fit_and_value',
                'estimated_step'):
        assert dh[key] == V2_DIAGNOSTIC[key], key

    assert pack['activity'] == {
        'type': ActivityType.MEETING, 'date': TODAY.isoformat(),
        'description': 'Walk the CFO through the business case.',
        'call_to_action': 'Agree on the pilot scope.',
        'outcome_notes': 'Bring the ROI sheet.',
        'preparation_notes': 'Ask about the Q2 budget review.',
    }

    [objective] = pack['objectives']
    assert objective['success_criteria'] == 'A close signed off on day three.'
    assert objective['notes'] == 'The board reviews it in June.'
    assert objective['target_date'] == '2027-06-30'

    assert pack['deal']['products'][0]['name'] == 'Reporting suite'
    assert pack['deal']['products'][0]['value_proposition'] == 'Closes the month in two days.'
    assert 'industry' in pack['account'] and 'company_size' in pack['account']
    assert [n['content'] for n in pack['manager_notes']] == ['Push for the CFO meeting.']

    profile = pack['seller_profile']
    assert profile['company_description'] == 'An AI-native CRM.'
    assert profile['customer_references'] == [{'name': 'Logistix', 'sector': 'Logistics'}]

    assert [p['notes'] for p in pack['previous_activities']] == ['They loved the forecast view.']

    [marc] = pack['participants']                       # G4, read once
    assert marc['role'] and marc['label'] == 'Marc'


def test_the_previous_activities_are_capped_most_recent_first_kept(
    scene, account, user_a, monkeypatch,
):
    from app_modules.ai_pipelines.services.prep_call import input_pack_assembler
    monkeypatch.setattr(input_pack_assembler, 'PREP_CALL_PREVIOUS_ACTIVITIES_MAX', 2)
    for days_ago in (8, 6, 4):
        _previous(account, user_a, scene['cycle'], f'Notes {days_ago}', days_ago=days_ago)

    notes = [p['notes'] for p in _pack(scene['meeting'])['previous_activities']]

    assert notes == ['Notes 6', 'Notes 4']              # the 2 most recent, oldest first


def test_a_free_text_is_bounded(scene, monkeypatch):
    from app_modules.ai_pipelines.services.prep_call import input_pack_assembler
    monkeypatch.setattr(input_pack_assembler, 'PREP_CALL_MAX_CHARS_PER_SOURCE', 10)

    pack = _pack(scene['meeting'])

    assert pack['activity']['description'].startswith('Walk the C')
    assert 'Walk the CFO through' not in pack['activity']['description']


# =============================================================================
# THE HASH v2 — each input moves it
# =============================================================================

def _change_description(scene, account, user_a):
    Activity.objects.filter(pk=scene['meeting'].pk).update(description='Another agenda.')


def _change_call_to_action(scene, account, user_a):
    Activity.objects.filter(pk=scene['meeting'].pk).update(call_to_action='Sign the pilot.')


def _change_outcome_notes(scene, account, user_a):
    Activity.objects.filter(pk=scene['meeting'].pk).update(outcome_notes='Other notes.')


def _change_preparation_notes(scene, account, user_a):
    Activity.objects.filter(pk=scene['meeting'].pk).update(preparation_notes='Other prep.')


def _add_participant(scene, account, user_a):
    scene['meeting'].contacts.add(_contact(account, user_a, 'Lea', 'Martin'))


def _new_deal_health(scene, account, user_a):
    from app_modules.decision_cycles.models import DealHealthSnapshot
    DealHealthSnapshot(decision_cycle=scene['cycle'], diagnostic=copy.deepcopy(V2_DIAGNOSTIC),
                       schema_version=2).save(user=user_a, client_id=account.client_id)


def _update_seller_profile(scene, account, user_a):
    from app_modules.product_catalog.models import SellerProfile
    profile = SellerProfile.objects.get(client_id=account.client_id)
    profile.value_proposition = 'Win more.'
    profile.save(user=user_a)


def _add_product(scene, account, user_a):
    from app_modules.decision_cycles.models import DealProduct
    from app_modules.product_catalog.models import ProductCatalog
    product = ProductCatalog(name='Forecast add-on')
    product.save(user=user_a, client_id=account.client_id)
    DealProduct(decision_cycle=scene['cycle'], product_catalog_entry=product, quantity=1).save(
        user=user_a, client_id=account.client_id)


def _add_previous_notes(scene, account, user_a):
    _previous(account, user_a, scene['cycle'], 'A new earlier call.', days_ago=2)


@pytest.mark.parametrize('change', [
    _change_description, _change_call_to_action, _change_outcome_notes,
    _change_preparation_notes, _add_participant, _new_deal_health, _update_seller_profile,
    _add_product, _add_previous_notes,
], ids=lambda f: f.__name__.strip('_'))
def test_each_input_moves_the_hash(change, scene, account, user_a):
    before = _hash(scene['meeting'])

    change(scene, account, user_a)

    assert _hash(scene['meeting']) != before


def test_the_hash_is_stable_when_nothing_changes(scene):
    assert _hash(scene['meeting']) == _hash(scene['meeting'])


# =============================================================================
# NO N+1 — the cost does not grow with participants nor previous activities
# =============================================================================

def test_the_pack_cost_does_not_grow_with_participants_nor_previous_activities(
    scene, account, user_a,
):
    def count():
        meeting = Activity.objects.get(pk=scene['meeting'].pk)
        with CaptureQueriesContext(connection) as ctx:
            PrepInputPackAssembler().build(activity=meeting)
        return len(ctx.captured_queries)

    few = count()
    for i, first in enumerate(('Lea', 'Hugo', 'Paul')):
        contact = _contact(account, user_a, first, f'Name{i}')
        _stakeholder(scene['cycle'], user_a, contact, role=PeopleRole.INFLUENCER)
        scene['meeting'].contacts.add(contact)
    for days_ago in (9, 7, 3, 1):
        _previous(account, user_a, scene['cycle'], f'More notes {days_ago}', days_ago=days_ago)
    many = count()

    assert many == few, (few, many)
