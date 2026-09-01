# backend/tests/signals/test_pain_impact_target_dept.py
"""
Pain / Impact scope: the legacy single FK target_department is DROPPED
(sub-step 2d). The scope axis is now the multi-department target_departments
M2M (sub-steps 2a-2c); scope_level stays. These tests pin the FK's absence and
the M2M's presence via _meta on both models, and check canonical_key is
unaffected by the drop.

Objective and People keep their own target_department FK (covered elsewhere).
"""

import pytest
from django.core.exceptions import FieldDoesNotExist

from app_modules.signals.constants import (
    SignalDimension,
    SignalSource,
    SignalWhat,
)
from app_modules.signals.models import ImpactSignal, PainSignal


pytestmark = pytest.mark.django_db


# =============================================================================
# PAIN SIGNAL — legacy FK dropped, M2M present
# =============================================================================

class TestPainSignalTargetDepartmentFKDropped:

    def test_legacy_target_department_fk_is_removed(self):
        with pytest.raises(FieldDoesNotExist):
            PainSignal._meta.get_field('target_department')

    def test_target_departments_m2m_is_present(self):
        assert PainSignal._meta.get_field('target_departments').many_to_many is True

    def test_canonical_key_unchanged(self, account, activity, user_a):
        s = PainSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.OPS,
            dimension=SignalDimension.TIME,
            summary='Reporting overhead',
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        assert s.canonical_key == 'pain:OPS:TIME'


# =============================================================================
# IMPACT SIGNAL — legacy FK dropped, M2M present
# =============================================================================

class TestImpactSignalTargetDepartmentFKDropped:

    def test_legacy_target_department_fk_is_removed(self):
        with pytest.raises(FieldDoesNotExist):
            ImpactSignal._meta.get_field('target_department')

    def test_target_departments_m2m_is_present(self):
        assert ImpactSignal._meta.get_field('target_departments').many_to_many is True

    def test_save_without_department_still_works(self, account, activity, user_a):
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
        assert list(s.target_departments.all()) == []
        assert s.scope_level == ScopeLevel.BUSINESS
