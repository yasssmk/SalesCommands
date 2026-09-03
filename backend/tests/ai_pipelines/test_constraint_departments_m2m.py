# backend/tests/ai_pipelines/test_constraint_departments_m2m.py
"""
Sub-step 1b — Constraint scope in the AI packs (prep-call + deal-health)
moves from the single FK target_department to the multi-department M2M
target_departments.

A ConstraintSignal carrying TWO departments in target_departments (FK left
NULL) must surface BOTH in each pack. RED before the recabling (the builders
read the FK via .values('target_department__name') / .target_department, so
they see nothing) and GREEN once each builder reads the M2M collection.
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
    ConstraintNature,
    Rigidity,
    SignalSource,
    SignalStatus,
)
from app_modules.signals.models import ConstraintSignal
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


def _mk_validated_constraint(cycle, user_a, depts):
    sig = ConstraintSignal(
        account=cycle.account,
        decision_cycle=cycle,
        source=SignalSource.MANUAL,
        status=SignalStatus.VALIDATED,
        nature=ConstraintNature.FINANCIAL,
        summary='ROI must exceed 20% within 18 months',
        source_quote='We need at least 20% ROI in 18 months',
        rigidity=Rigidity.FIRM,
    )
    sig.save(user=user_a, client_id=cycle.client_id)
    sig.target_departments.set(depts)
    return sig


@pytest.mark.django_db
class TestDealHealthConstraintDepartmentsM2M:

    def test_evidence_pack_lists_all_departments(self, cycle, user_a):
        fin, it = _dept('Finance'), _dept('IT')
        _mk_validated_constraint(cycle, user_a, [fin, it])

        pack = DealHealthEvidenceBuilder().build(cycle)
        constraint = pack['signals']['constraint'][0]
        names = set(constraint['target_departments'])
        assert names == {fin.get_name_display(), it.get_name_display()}


@pytest.mark.django_db
class TestPrepCallConstraintDepartmentsM2M:

    def test_levers_constraints_list_all_departments(self, activity, cycle, user_a):
        # bind the activity to the cycle so the DC-scoped constraint is picked up
        activity.decision_cycle = cycle
        activity.save(user=user_a, client_id=cycle.client_id)

        fin, it = _dept('Finance'), _dept('IT')
        _mk_validated_constraint(cycle, user_a, [fin, it])

        pack = PrepInputPackAssembler().build(
            activity=activity,
            target_contact=None,
            brief_mode='DISCOVERY',
        )
        constraints = pack['levers']['constraints']
        assert len(constraints) == 1
        names = set(constraints[0]['departments'])
        assert names == {fin.get_name_display(), it.get_name_display()}
