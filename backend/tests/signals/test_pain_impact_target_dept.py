# backend/tests/signals/test_pain_impact_target_dept.py
"""
Tests for the target_department FK added to PainSignal and ImpactSignal.

Covers:
  * FK is nullable — signals can be saved without a department
  * FK can be set to a StandardDepartment instance
  * SET_NULL semantics on department deletion
  * No regression on existing Pain/Impact behaviour
"""

import pytest

from app_modules.signals.constants import (
    SignalDimension,
    SignalSource,
    SignalWhat,
)
from app_modules.signals.models import ImpactSignal, PainSignal


pytestmark = pytest.mark.django_db


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def department(db, client_account_a, user_a):
    from app_modules.core_modules.models import StandardDepartment
    dept = StandardDepartment(name='Marketing')
    dept.save(user=user_a, client_id=client_account_a.id)
    return dept


# =============================================================================
# PAIN SIGNAL — target_department
# =============================================================================

class TestPainSignalTargetDepartment:

    def test_save_without_department(self, account, activity, user_a):
        s = PainSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.OPS,
            dimension=SignalDimension.TIME,
            summary='Manual reporting takes 10h/week',
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.target_department_id is None

    def test_save_with_department(self, account, activity, department, user_a):
        s = PainSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.DATA,
            dimension=SignalDimension.QUALITY,
            summary='Data quality issues in Marketing',
            target_department=department,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.target_department_id == department.id

    def test_set_null_on_department_delete(
        self, account, activity, department, user_a,
    ):
        s = PainSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.OPS,
            dimension=SignalDimension.COST,
            summary='Budget overrun in Marketing',
            target_department=department,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        dept_id = department.id

        department.delete()

        s.refresh_from_db()
        assert s.target_department_id is None
        assert s.pk is not None

    def test_canonical_key_unchanged(self, account, activity, department, user_a):
        s = PainSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.OPS,
            dimension=SignalDimension.TIME,
            summary='Reporting overhead',
            target_department=department,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        assert s.canonical_key == 'pain:OPS:TIME'


# =============================================================================
# IMPACT SIGNAL — target_department
# =============================================================================

class TestImpactSignalTargetDepartment:

    def test_save_without_department(self, account, activity, user_a):
        from app_modules.signals.constants import ImpactType, ScopeLevel
        s = ImpactSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.OPS,
            dimension=SignalDimension.TIME,
            scope_level=ScopeLevel.BUSINESS,
            impact_type=ImpactType.TIME,
            summary='5h/week lost on manual work',
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.target_department_id is None

    def test_save_with_department(self, account, activity, department, user_a):
        from app_modules.signals.constants import ImpactType, ScopeLevel
        s = ImpactSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.DATA,
            dimension=SignalDimension.QUALITY,
            scope_level=ScopeLevel.DEPARTMENT,
            impact_type=ImpactType.PRODUCTIVITY,
            summary='Marketing team productivity down 30%',
            target_department=department,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.target_department_id == department.id

    def test_set_null_on_department_delete(
        self, account, activity, department, user_a,
    ):
        from app_modules.signals.constants import ImpactType, ScopeLevel
        s = ImpactSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.OPS,
            dimension=SignalDimension.COST,
            scope_level=ScopeLevel.DEPARTMENT,
            impact_type=ImpactType.FINANCIAL,
            summary='30k/month wasted',
            target_department=department,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)

        department.delete()

        s.refresh_from_db()
        assert s.target_department_id is None
        assert s.pk is not None
