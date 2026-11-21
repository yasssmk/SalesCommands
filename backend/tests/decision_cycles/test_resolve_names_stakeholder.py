# backend/tests/decision_cycles/test_resolve_names_stakeholder.py
"""
Sprint « Deal health v2 », sub-step 5d — giving a nameless stakeholder the
name of the person linked to it, at the « Link » of a People signal (PO:
« information completes itself when it does not contradict »).

POST /module-signals/people/{id}/resolve/ {stakeholder_id, name_stakeholder}:
the server writes the stakeholder's full_name ONLY when the stakeholder has
no name of its own (no full_name, no contact) AND the signal has a full_name.
Otherwise the flag is ignored — a normal business case, no error.

  (a) Link to a department-only stakeholder + name_stakeholder → named;
  (b) Link to an already named stakeholder → its name is unchanged;
  (c) Link to a stakeholder linked to a contact → unchanged;
  (d) end to end: after (a), a deal-health run writes the profile on it
      (the label rule of c8d0742).
"""

import copy
import json

import pytest

from app_modules.ai_pipelines.models import AIPipelineRun
from app_modules.signals.constants import PeopleRole, SignalSource, SignalStatus

from tests.ai_pipelines.conftest import fake_provider, patch_active_provider  # noqa: F401
from tests.ai_pipelines.deal_health_fixtures import V2_DIAGNOSTIC
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


def _resolve_url(signal):
    return f'/module-signals/people/{signal.id}/resolve/'


def _department(name):
    from app_modules.core_modules.models import StandardDepartment
    return StandardDepartment.objects.get_or_create(name=name)[0]


def _stakeholder(cycle, user, *, full_name='', department=None, contact=None):
    from app_modules.decision_cycles.models import Stakeholder
    s = Stakeholder(decision_cycle=cycle, full_name=full_name, department=department,
                    contact=contact)
    s.save(user=user, client_id=cycle.client_id)
    return s


def _pending_person(cycle, activity, user, full_name):
    """A PENDING People observation of the deal, named (no contact) — what the
    extraction leaves to validate on the Activity page."""
    from app_modules.signals.models import PeopleSignal
    activity.decision_cycle = cycle
    activity.save(user=user, client_id=cycle.client_id)
    s = PeopleSignal(
        account=cycle.account, decision_cycle=cycle, source_activity=activity,
        source=SignalSource.LLM_EXTRACTED, status=SignalStatus.PENDING,
        role=PeopleRole.DECISION_MAKER, full_name=full_name, confidence=0.9,
    )
    s.save(user=user, client_id=cycle.client_id)
    return s


def _link(api, signal, stakeholder, **extra):
    resp = api.post(_resolve_url(signal), {'stakeholder_id': str(stakeholder.id), **extra},
                    format='json')
    assert resp.status_code == 200, resp.content
    stakeholder.refresh_from_db()
    signal.refresh_from_db()
    assert signal.stakeholder_id == stakeholder.id
    return stakeholder


# =============================================================================
# (a) — a nameless stakeholder receives the signal's name
# =============================================================================

def test_a_a_nameless_stakeholder_is_named_after_the_signal(
    authed_api_a, cycle, activity, user_a,
):
    finance = _stakeholder(cycle, user_a, department=_department('Finance'))
    colonel = _pending_person(cycle, activity, user_a, 'Colonel Mustard')

    named = _link(authed_api_a, colonel, finance, name_stakeholder=True)

    assert named.full_name == 'Colonel Mustard'
    assert named.full_name_normalized == 'colonel mustard'     # recomputed by save()
    assert named.department_id is not None                     # the department is kept


def test_a_without_the_flag_the_stakeholder_stays_nameless(
    authed_api_a, cycle, activity, user_a,
):
    finance = _stakeholder(cycle, user_a, department=_department('Finance'))
    colonel = _pending_person(cycle, activity, user_a, 'Colonel Mustard')

    assert _link(authed_api_a, colonel, finance).full_name == ''


# =============================================================================
# (b) / (c) — never overwrite, never contradict: the flag is ignored
# =============================================================================

def test_b_an_already_named_stakeholder_keeps_its_name(
    authed_api_a, cycle, activity, user_a,
):
    elena = _stakeholder(cycle, user_a, full_name='Elena Rossi')
    colonel = _pending_person(cycle, activity, user_a, 'Colonel Mustard')

    assert _link(authed_api_a, colonel, elena, name_stakeholder=True).full_name == 'Elena Rossi'


def test_c_a_stakeholder_linked_to_a_contact_is_unchanged(
    authed_api_a, cycle, activity, user_a, contact,
):
    linked = _stakeholder(cycle, user_a, contact=contact)
    colonel = _pending_person(cycle, activity, user_a, 'Colonel Mustard')

    after = _link(authed_api_a, colonel, linked, name_stakeholder=True)

    assert after.full_name == ''                    # named by its contact (étape 5b)
    assert after.contact_id == contact.id


# =============================================================================
# (d) — end to end: the deal health now profiles that stakeholder
# =============================================================================

def test_d_after_naming_the_deal_health_writes_its_profile(
    authed_api_a, cycle, activity, user_a, patch_active_provider,
):
    finance = _stakeholder(cycle, user_a, department=_department('Finance'))
    colonel = _pending_person(cycle, activity, user_a, 'Colonel Mustard')
    _link(authed_api_a, colonel, finance, name_stakeholder=True)

    answer = copy.deepcopy(V2_DIAGNOSTIC)
    answer['stakeholders'] = [{
        'ref': 'Colonel', 'conviction_state': 'SKEPTICAL', 'convincing_metrics': '',
        'frustrations': '', 'conviction_strategy': 'Show the cost of delay',
        'communication_style': '', 'communication_language': '',
    }]
    patch_active_provider.replies['deal_health'] = json.dumps(answer)
    resp = authed_api_a.post('/module-ai-pipelines/deal-health/run/',
                             {'decision_cycle_id': str(cycle.id)}, format='json')
    assert resp.status_code == 201, resp.content

    finance.refresh_from_db()
    assert finance.profile['conviction_strategy']['value'] == 'Show the cost of delay'
    run = AIPipelineRun.objects.get(id=resp.data['data']['run']['run_id'])
    assert run.sub_calls[-1]['persist_counts']['ambiguous_stakeholder_refs'] == []
