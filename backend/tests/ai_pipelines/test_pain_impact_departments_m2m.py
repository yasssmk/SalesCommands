# backend/tests/ai_pipelines/test_pain_impact_departments_m2m.py
"""
Sub-step 2b — Pain and Impact scope in the AI packs (prep-call + deal-health)
moves from the single FK target_department to the multi-department M2M
target_departments. A pain / impact carrying TWO departments must surface
BOTH. RED before the recabling, GREEN once each builder reads the M2M.
Objective stays on the FK (untouched).
"""

import pytest

from tests.decision_cycles.conftest import (  # noqa: F401
    pytest_configure,
    _jwt_only_no_csrf,
    tenant_a_id,
    client_account_a,
    role_individual_a,
    user_a,
    account,
    activity,
    contact,
    api,
    authenticate,
    authed_api_a,
    cache_invalidation_calls,
    cycle,
    five_steps,
)

from app_modules.signals.constants import (
    ScopeLevel,
    SignalDimension,
    SignalSource,
    SignalStatus,
    SignalWhat,
    ImpactType,
)
from app_modules.signals.models import PainSignal, ImpactSignal
from app_modules.ai_pipelines.services.deal_health_evidence_builder import (
    DealHealthEvidenceBuilder,
)
from app_modules.ai_pipelines.services.prep_call.input_pack_assembler import (
    PrepInputPackAssembler,
)


def _dept(name):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name=name)
    return d


def _mk_pain(cycle, user_a, depts):
    p = PainSignal(
        account=cycle.account, decision_cycle=cycle,
        source=SignalSource.MANUAL, status=SignalStatus.VALIDATED,
        what=SignalWhat.OPS, dimension=SignalDimension.TIME,
        scope_level=ScopeLevel.DEPARTMENT, summary='Reporting pain',
        source_quote='q',
    )
    p.save(user=user_a, client_id=cycle.client_id)
    p.target_departments.set(depts)
    return p


def _mk_impact(cycle, user_a, depts):
    i = ImpactSignal(
        account=cycle.account, decision_cycle=cycle,
        source=SignalSource.MANUAL, status=SignalStatus.VALIDATED,
        what=SignalWhat.OPS, dimension=SignalDimension.TIME,
        scope_level=ScopeLevel.DEPARTMENT, impact_type=ImpactType.FINANCIAL,
        summary='Cost impact', source_quote='q', metric_text='20%',
    )
    i.save(user=user_a, client_id=cycle.client_id)
    i.target_departments.set(depts)
    return i


@pytest.mark.django_db
class TestDealHealthPainImpactDepartmentsM2M:

    def test_pain_pack_lists_all_departments(self, cycle, user_a):
        fin, it = _dept('Finance'), _dept('IT')
        _mk_pain(cycle, user_a, [fin, it])
        pack = DealHealthEvidenceBuilder().build(cycle)
        names = set(pack['signals']['pain'][0]['target_departments'])
        assert names == {fin.get_name_display(), it.get_name_display()}

    def test_impact_pack_lists_all_departments(self, cycle, user_a):
        fin, it = _dept('Finance'), _dept('IT')
        _mk_impact(cycle, user_a, [fin, it])
        pack = DealHealthEvidenceBuilder().build(cycle)
        names = set(pack['signals']['impact'][0]['target_departments'])
        assert names == {fin.get_name_display(), it.get_name_display()}


@pytest.mark.django_db
class TestPrepCallPainImpactDepartmentsM2M:

    def test_impact_lever_lists_all_departments(self, activity, cycle, user_a):
        activity.decision_cycle = cycle
        activity.save(user=user_a, client_id=cycle.client_id)
        fin, it = _dept('Finance'), _dept('IT')
        _mk_impact(cycle, user_a, [fin, it])
        pack = PrepInputPackAssembler().build(
            activity=activity, target_contact=None, brief_mode='DISCOVERY',
        )
        value = pack['levers']['value']
        assert len(value) == 1
        assert set(value[0]['departments']) == {fin.get_name_display(), it.get_name_display()}
