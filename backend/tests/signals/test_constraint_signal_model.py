# backend/tests/signals/test_constraint_signal_model.py
"""
Model-level invariants for ConstraintSignal.

Covers:
  * Shadow-overrides (signal_category)
  * canonical_key computation ("constraint:<what>:<dimension>")
  * clean() requires source_activity
  * Rigidity field (FIRM / FLEXIBLE)
  * MANUAL → VALIDATED auto, LLM_EXTRACTED → PENDING auto
  * Cache invalidation: SIGNALS_CACHE_TAG + SIGNAL_CLUSTERS_CACHE_TAG
"""

import pytest
from django.core.exceptions import FieldDoesNotExist, ValidationError

from app_modules.signals.constants import (
    Rigidity,
    SIGNAL_CLUSTERS_CACHE_TAG,
    SIGNALS_CACHE_TAG,
    SignalDimension,
    SignalSource,
    SignalStatus,
    SignalWhat,
)
from app_modules.signals.models import ConstraintSignal


pytestmark = pytest.mark.django_db


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def department(db, client_account_a, user_a):
    from app_modules.core_modules.models import StandardDepartment
    dept = StandardDepartment(name='Finance')
    dept.save(user=user_a, client_id=client_account_a.id)
    return dept


# =============================================================================
# SHADOW OVERRIDES
# =============================================================================

class TestConstraintSignalShadowOverride:

    def test_signal_category_field_does_not_exist_on_meta(self):
        with pytest.raises(FieldDoesNotExist):
            ConstraintSignal._meta.get_field('signal_category')

    def test_signal_category_class_attr_is_none(self):
        assert ConstraintSignal.signal_category is None


# =============================================================================
# CANONICAL KEY
# =============================================================================

class TestConstraintSignalCanonicalKey:

    def test_canonical_key_computed_on_save(self, account, activity, user_a):
        s = ConstraintSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.GROWTH,
            dimension=SignalDimension.COST,
            summary='ROI > 20% under 18 months',
            rigidity=Rigidity.FIRM,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.canonical_key == 'constraint:GROWTH:COST'

    def test_canonical_key_none_when_axes_missing(self, account, activity, user_a):
        s = ConstraintSignal(
            account=account,
            source_activity=activity,
            what='',
            dimension=SignalDimension.TIME,
            summary='Deployment before Q3',
            rigidity=Rigidity.FLEXIBLE,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.canonical_key is None

    def test_canonical_key_updates_on_resave(self, account, activity, user_a):
        s = ConstraintSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.OPS,
            dimension=SignalDimension.TIME,
            summary='Process must complete in under 2 weeks',
            rigidity=Rigidity.FIRM,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        assert s.canonical_key == 'constraint:OPS:TIME'

        s.what = SignalWhat.TECH
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.canonical_key == 'constraint:TECH:TIME'


# =============================================================================
# CLEAN() — source_activity required
# =============================================================================

class TestConstraintSignalClean:

    def test_clean_raises_without_source_activity(self, account):
        s = ConstraintSignal(
            account=account,
            what=SignalWhat.GROWTH,
            dimension=SignalDimension.COST,
            summary='ROI > 20%',
            rigidity=Rigidity.FIRM,
        )
        with pytest.raises(ValidationError) as exc_info:
            s.clean()
        assert 'source_activity' in exc_info.value.message_dict

    def test_clean_passes_with_source_activity(self, account, activity):
        s = ConstraintSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.GROWTH,
            dimension=SignalDimension.COST,
            summary='ROI > 20%',
            rigidity=Rigidity.FIRM,
        )
        s.clean()


# =============================================================================
# RIGIDITY FIELD
# =============================================================================

class TestConstraintRigidity:

    def test_firm_rigidity(self, account, activity, user_a):
        s = ConstraintSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.GROWTH,
            dimension=SignalDimension.COST,
            summary='ROI > 20%',
            rigidity=Rigidity.FIRM,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.rigidity == Rigidity.FIRM

    def test_flexible_rigidity(self, account, activity, user_a):
        s = ConstraintSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.OPS,
            dimension=SignalDimension.TIME,
            summary='Ideally before Q3',
            rigidity=Rigidity.FLEXIBLE,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.rigidity == Rigidity.FLEXIBLE


# =============================================================================
# TARGET DEPARTMENT — optional FK
# =============================================================================

class TestConstraintTargetDepartment:

    def test_with_department(self, account, activity, department, user_a):
        s = ConstraintSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.GROWTH,
            dimension=SignalDimension.COST,
            summary='ROI validated by Finance',
            rigidity=Rigidity.FIRM,
            target_department=department,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.target_department_id == department.id

    def test_without_department(self, account, activity, user_a):
        s = ConstraintSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.TECH,
            dimension=SignalDimension.RISK,
            summary='Security audit required',
            rigidity=Rigidity.FIRM,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.target_department_id is None


# =============================================================================
# LIFECYCLE
# =============================================================================

class TestConstraintSignalLifecycle:

    def test_manual_source_auto_validated(self, account, activity, user_a):
        s = ConstraintSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.GROWTH,
            dimension=SignalDimension.COST,
            summary='ROI > 20%',
            rigidity=Rigidity.FIRM,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        assert s.status == SignalStatus.VALIDATED
        assert s.confidence is None

    def test_llm_extracted_starts_pending(self, account, activity, user_a):
        s = ConstraintSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.OPS,
            dimension=SignalDimension.TIME,
            summary='Deployment before Q3',
            rigidity=Rigidity.FLEXIBLE,
            source=SignalSource.LLM_EXTRACTED,
            confidence=0.9,
        )
        s.save(user=user_a, client_id=account.client_id)
        assert s.status == SignalStatus.PENDING


# =============================================================================
# CACHE INVALIDATION — signals AND clusters
# =============================================================================

class TestConstraintSignalCacheInvalidation:

    @pytest.mark.django_db(transaction=True)
    def test_save_invalidates_both_tags(
        self, account, activity, user_a,
        cache_invalidation_calls,
    ):
        s = ConstraintSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.GROWTH,
            dimension=SignalDimension.COST,
            summary='ROI > 20%',
            rigidity=Rigidity.FIRM,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)

        client_str = str(account.client_id)
        signal_tags = [
            ns for cid, ns in cache_invalidation_calls if cid == client_str
        ]
        assert SIGNALS_CACHE_TAG in signal_tags
        assert SIGNAL_CLUSTERS_CACHE_TAG in signal_tags
