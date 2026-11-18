# backend/tests/ai_pipelines/test_llm_people_first_names.py
"""
Sprint « Deal health v2 », step 3a — first names only to the LLM.

services/llm_people.py is THE point that names a person in a prompt. Real
path only: POST /module-ai-pipelines/deal-health/run/ and
POST /module-ai-pipelines/prep-call/run/ with the real pipelines and the
fake provider, which captures the system + user prompts sent to the LLM
(tests/ai_pipelines/conftest.py).

  (a) deal health: a stakeholder « Marc Dupont » who raised a blocker —
      "Dupont" appears nowhere in the prompts, "Marc" does;
  (b) the same for the prep call;
  (c) two « Marc » in different departments are told apart (reference +
      first name + department, amendment A4; P refs — S is the steps);
  (d) the decision cycle's UUID is no longer sent by the prep call (A15).
"""

import json

import pytest
from django.utils import timezone

from app_modules.signals.constants import PeopleRole, SignalSource, SignalStatus

from tests.ai_pipelines.test_deal_health_pipeline import _VALID_DIAGNOSTIC
from tests.ai_pipelines.test_prep_call_not_an_analysis import _VALID_BRIEF
from tests.decision_cycles.conftest import (  # noqa: F401
    pytest_configure,
    _jwt_only_no_csrf,
    tenant_a_id,
    tenant_b_id,
    client_account_a,
    client_account_b,
    role_individual_a,
    role_individual_b,
    user_a,
    user_b,
    account,
    other_tenant_account,
    activity,
    contact,
    api,
    authenticate,
    authed_api_a,
    authed_api_b,
    cache_invalidation_calls,
    cycle,
)


pytestmark = pytest.mark.django_db

DEAL_HEALTH_URL = '/module-ai-pipelines/deal-health/run/'
PREP_CALL_URL = '/module-ai-pipelines/prep-call/run/'


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def provider(patch_active_provider):
    patch_active_provider.replies['deal_health'] = json.dumps(_VALID_DIAGNOSTIC)
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)
    return patch_active_provider


def _department(name):
    from app_modules.core_modules.models import StandardDepartment
    dept, _ = StandardDepartment.objects.get_or_create(name=name)
    return dept


def _contact(account, user, first, last, dept=None):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name=first, last_name=last,
                standard_department=dept)
    c.save(user=user, client_id=account.client_id)
    return c


def _people(cycle, user, contact, dept=None):
    from app_modules.signals.models import PeopleSignal
    s = PeopleSignal(
        account=cycle.account, decision_cycle=cycle, source=SignalSource.MANUAL,
        status=SignalStatus.VALIDATED, role=PeopleRole.CHAMPION,
        target_contact=contact, target_department=dept,
    )
    s.save(user=user, client_id=cycle.client_id)
    return s


def _blocker(cycle, user, contact, summary='No budget allocated'):
    from app_modules.signals.models import BlockerSignal
    s = BlockerSignal(
        account=cycle.account, decision_cycle=cycle, source=SignalSource.MANUAL,
        status=SignalStatus.VALIDATED, summary=summary,
        source_quote='We have no budget for this', contact=contact,
    )
    s.save(user=user, client_id=cycle.client_id)
    return s


@pytest.fixture
def marc_dupont(account, user_a, cycle):
    """A stakeholder « Marc Dupont » (validated People) who raised a blocker."""
    marc = _contact(account, user_a, 'Marc', 'Dupont', _department('Finance'))
    _people(cycle, user_a, marc)
    _blocker(cycle, user_a, marc)
    return marc


@pytest.fixture
def two_marcs(account, user_a, cycle):
    """Two « Marc » of different departments, each a stakeholder with a blocker."""
    finance, it = _department('Finance'), _department('IT')
    marc_f = _contact(account, user_a, 'Marc', 'Dupont', finance)
    marc_i = _contact(account, user_a, 'Marc', 'Durand', it)
    _people(cycle, user_a, marc_f, finance)
    _people(cycle, user_a, marc_i, it)
    _blocker(cycle, user_a, marc_f, summary='No budget this year')
    _blocker(cycle, user_a, marc_i, summary='Security review pending')
    return marc_f, marc_i


@pytest.fixture
def meeting_on_cycle(account, user_a, cycle):
    from app_modules.activities.constants import ActivityStatus, ActivityType
    from app_modules.activities.models import Activity
    a = Activity(
        title='Discovery', activity_type=ActivityType.MEETING,
        status=ActivityStatus.PLANNED, account=account, owner=user_a,
        decision_cycle=cycle, scheduled_date=timezone.now().date(),
    )
    a.save(user=user_a, client_id=account.client_id)
    return a


def _prompts(provider, stage):
    calls = provider.calls_for(stage)
    assert len(calls) == 1
    return calls[0]['system'] + '\n' + calls[0]['user']


def _run_deal_health(api, cycle, provider):
    resp = api.post(DEAL_HEALTH_URL, {'decision_cycle_id': str(cycle.id)}, format='json')
    assert resp.status_code == 201, resp.content
    return _prompts(provider, 'deal_health')


def _run_prep_call(api, activity, provider):
    resp = api.post(PREP_CALL_URL, {'activity_id': str(activity.id)}, format='json')
    assert resp.status_code == 201, resp.content
    return _prompts(provider, 'prep_call')


# =============================================================================
# (a) / (b) — first names only
# =============================================================================

def test_a_deal_health_names_the_stakeholder_by_first_name_only(
    authed_api_a, cycle, marc_dupont, provider,
):
    prompt = _run_deal_health(authed_api_a, cycle, provider)

    assert 'Marc' in prompt            # the person is still named...
    assert 'Dupont' not in prompt      # ...by the first name only


def test_b_prep_call_names_the_blocker_actor_by_first_name_only(
    authed_api_a, meeting_on_cycle, marc_dupont, provider,
):
    prompt = _run_prep_call(authed_api_a, meeting_on_cycle, provider)

    assert 'Marc' in prompt
    assert 'Dupont' not in prompt


# =============================================================================
# (c) — two « Marc » are told apart
# =============================================================================

def test_c_deal_health_tells_two_marcs_apart(authed_api_a, cycle, two_marcs, provider):
    prompt = _run_deal_health(authed_api_a, cycle, provider)

    assert 'P1 Marc (Finance & Accounting)' in prompt or 'P1 Marc (Information Technology (IT))' in prompt
    assert 'Marc (Finance & Accounting)' in prompt
    assert 'Marc (Information Technology (IT))' in prompt
    assert 'P2 Marc' in prompt
    assert 'S1 Marc' not in prompt and 'S2 Marc' not in prompt   # S = steps
    assert 'Dupont' not in prompt and 'Durand' not in prompt


def test_c_prep_call_tells_two_marcs_apart(
    authed_api_a, meeting_on_cycle, two_marcs, provider,
):
    prompt = _run_prep_call(authed_api_a, meeting_on_cycle, provider)

    assert 'Marc (Finance & Accounting)' in prompt
    assert 'Marc (Information Technology (IT))' in prompt
    assert 'P1 Marc' in prompt and 'P2 Marc' in prompt
    assert 'S1 Marc' not in prompt and 'S2 Marc' not in prompt   # S = steps
    assert 'Dupont' not in prompt and 'Durand' not in prompt


# =============================================================================
# (d) — no decision cycle UUID in the prep call
# =============================================================================

def test_d_prep_call_does_not_send_the_cycle_uuid(
    authed_api_a, meeting_on_cycle, cycle, provider,
):
    prompt = _run_prep_call(authed_api_a, meeting_on_cycle, provider)

    assert str(cycle.id) not in prompt
    assert 'Decision cycle:' not in prompt
