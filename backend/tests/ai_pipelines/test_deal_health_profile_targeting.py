# backend/tests/ai_pipelines/test_deal_health_profile_targeting.py
"""
Sprint « Deal health v2 », sub-step 5c, anomaly 1 — a profile is written ONLY
when the label the LLM wrote back designates, without ambiguity, ONE
stakeholder; otherwise it is skipped and traced (persist_counts).

The defect: the roster names a person after the PeopleSignal affiliated to a
stakeholder, while the profile lands on the STAKEHOLDER. A stakeholder with
no name of its own (department only) to which a named observation was
affiliated — resolve_people_signal accepts any stakeholder of the cycle, and
its « create » branch may build a department-only one for a named signal —
received that person's profile.

Real path: the affiliation through stakeholder_service.resolve_people_signal,
then POST /module-ai-pipelines/deal-health/run/ with the fake provider
returning profiles by label.
"""

import copy
import json

import pytest

from app_modules.ai_pipelines.models import AIPipelineRun
from app_modules.signals.constants import PeopleRole, SignalSource, SignalStatus

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

RUN_URL = '/module-ai-pipelines/deal-health/run/'


def _profile_entry(ref, strategy):
    return {
        'ref': ref, 'conviction_state': 'SKEPTICAL', 'convincing_metrics': '',
        'frustrations': '', 'conviction_strategy': strategy,
        'communication_style': '', 'communication_language': '',
    }


def _answer(*entries):
    answer = copy.deepcopy(V2_DIAGNOSTIC)
    answer['stakeholders'] = list(entries)
    return answer


def _department(name):
    from app_modules.core_modules.models import StandardDepartment
    return StandardDepartment.objects.get_or_create(name=name)[0]


def _stakeholder(cycle, user, *, full_name='', department=None):
    from app_modules.decision_cycles.models import Stakeholder
    s = Stakeholder(decision_cycle=cycle, full_name=full_name, department=department)
    s.save(user=user, client_id=cycle.client_id)
    return s


def _named_signal(cycle, user, full_name):
    """A validated People observation naming a person (no contact)."""
    from app_modules.signals.models import PeopleSignal
    s = PeopleSignal(
        account=cycle.account, decision_cycle=cycle, source=SignalSource.MANUAL,
        status=SignalStatus.VALIDATED, role=PeopleRole.DECISION_MAKER, full_name=full_name,
    )
    s.save(user=user, client_id=cycle.client_id)
    return s


def _affiliate(signal, user, **choice):
    """THE affiliation path of the app (« Link to the deal »)."""
    from app_modules.decision_cycles.services.stakeholder_service import (
        resolve_people_signal,
    )
    resolve_people_signal(signal, user, **choice)
    signal.refresh_from_db()
    return signal.stakeholder


def _run(api, cycle, provider, answer):
    provider.replies['deal_health'] = json.dumps(answer)
    resp = api.post(RUN_URL, {'decision_cycle_id': str(cycle.id)}, format='json')
    assert resp.status_code == 201, resp.content
    run = AIPipelineRun.objects.get(id=resp.data['data']['run']['run_id'])
    return run.sub_calls[-1]['persist_counts']


def _profile(stakeholder):
    stakeholder.refresh_from_db()
    return stakeholder.profile


# =============================================================================
# THE DEFECT — a named observation affiliated to a stakeholder without a name
# =============================================================================

def test_a_department_only_stakeholder_never_gets_a_named_persons_profile(
    authed_api_a, cycle, user_a, patch_active_provider,
):
    finance = _stakeholder(cycle, user_a, department=_department('Finance'))
    colonel = _named_signal(cycle, user_a, 'Colonel Mustard')
    assert _affiliate(colonel, user_a, stakeholder_id=finance.id) == finance

    counts = _run(authed_api_a, cycle, patch_active_provider,
                  _answer(_profile_entry('Colonel', "Use the Colonel's decision role")))

    assert _profile(finance) == {}                       # nothing on the department
    assert counts['ambiguous_stakeholder_refs'] == ['Colonel']
    assert counts['profiles_written'] == 0


def test_b_a_name_carried_only_by_the_current_signal_is_not_enough(
    authed_api_a, cycle, user_a, patch_active_provider,
):
    """« Link to the deal » → new stakeholder with a department only: the
    stakeholder has no name; only its current PeopleSignal carries one."""
    colonel = _named_signal(cycle, user_a, 'Colonel Mustard')
    created = _affiliate(colonel, user_a, create={'department_id': _department('Legal').id})
    assert created.full_name == '' and created.contact_id is None
    assert created.current_signal_id == colonel.id

    counts = _run(authed_api_a, cycle, patch_active_provider,
                  _answer(_profile_entry('Colonel', "Use the Colonel's decision role")))

    assert _profile(created) == {}
    assert counts['ambiguous_stakeholder_refs'] == ['Colonel']


# =============================================================================
# GUARDS
# =============================================================================

def test_c_two_stakeholders_without_a_name_receive_nothing(
    authed_api_a, cycle, user_a, patch_active_provider,
):
    a = _stakeholder(cycle, user_a, department=_department('Finance'))
    b = _stakeholder(cycle, user_a, department=_department('IT'))

    counts = _run(authed_api_a, cycle, patch_active_provider,
                  _answer(_profile_entry('Finance', 'x'), _profile_entry('', 'y')))

    assert _profile(a) == {} and _profile(b) == {}
    assert counts['profiles_written'] == 0


def test_d_a_stakeholder_named_by_its_own_name_still_gets_its_profile(
    authed_api_a, cycle, user_a, patch_active_provider,
):
    elena = _stakeholder(cycle, user_a, full_name='Elena Rossi')
    signal = _named_signal(cycle, user_a, 'Elena Rossi')
    _affiliate(signal, user_a, stakeholder_id=elena.id)

    counts = _run(authed_api_a, cycle, patch_active_provider,
                  _answer(_profile_entry('Elena', 'Show the payback in months')))

    assert _profile(elena)['conviction_strategy']['value'] == 'Show the payback in months'
    assert counts['profiles_written'] == 1
    assert counts['ambiguous_stakeholder_refs'] == []


def test_e_two_labels_resolving_to_one_stakeholder_write_nothing(
    authed_api_a, cycle, user_a, patch_active_provider,
):
    """An observation NOT affiliated and the stakeholder of the same name are
    two roster entries (« P1 Elena », « P2 Elena ») that both resolve to the
    same stakeholder: ambiguous, nothing written."""
    elena = _stakeholder(cycle, user_a, full_name='Elena Rossi')
    _named_signal(cycle, user_a, 'Elena Rossi')               # not affiliated

    counts = _run(authed_api_a, cycle, patch_active_provider, _answer(
        _profile_entry('P1 Elena', 'one'), _profile_entry('P2 Elena', 'two'),
    ))

    assert _profile(elena) == {}
    assert sorted(counts['ambiguous_stakeholder_refs']) == ['P1 Elena', 'P2 Elena']
