# backend/tests/signals/test_constraint_signal_model.py
"""
Model-level invariants for ConstraintSignal.

Covers:
  * Shadow-overrides (signal_category)
  * nature (ConstraintNature) classification axis
  * canonical_key detached — always None (mirror of BlockerSignal)
  * clean() requires source_activity
  * Rigidity field (FIRM / FLEXIBLE)
  * MANUAL → VALIDATED auto, LLM_EXTRACTED → PENDING auto
  * Cache invalidation: SIGNALS_CACHE_TAG + SIGNAL_CLUSTERS_CACHE_TAG
"""

import pytest
from django.core.exceptions import FieldDoesNotExist, ValidationError

from app_modules.signals.constants import (
    ConstraintNature,
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
# NATURE — classification axis
# =============================================================================

class TestConstraintSignalNature:

    def test_nature_persisted(self, account, activity, user_a):
        s = ConstraintSignal(
            account=account,
            source_activity=activity,
            nature=ConstraintNature.TECHNICAL,
            summary='Must integrate with SAP',
            rigidity=Rigidity.FIRM,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.nature == ConstraintNature.TECHNICAL

    def test_nature_choices_cover_expected_kinds(self):
        assert set(ConstraintNature.values) == {
            'FUNCTIONAL', 'TECHNICAL', 'FINANCIAL',
            'CONTRACTUAL', 'OPERATIONAL', 'SECURITY',
        }


# =============================================================================
# CANONICAL KEY — detached (always None)
# =============================================================================

class TestConstraintSignalCanonicalKeyDetached:

    def test_canonical_key_none_even_with_legacy_axes(self, account, activity, user_a):
        # Even if legacy what/dimension are supplied, constraint no longer
        # computes a canonical_key — it is detached from the axes.
        s = ConstraintSignal(
            account=account,
            source_activity=activity,
            nature=ConstraintNature.FINANCIAL,
            what=SignalWhat.GROWTH,
            dimension=SignalDimension.COST,
            summary='ROI > 20% under 18 months',
            rigidity=Rigidity.FIRM,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.canonical_key is None

    def test_canonical_key_none_without_legacy_axes(self, account, activity, user_a):
        s = ConstraintSignal(
            account=account,
            source_activity=activity,
            nature=ConstraintNature.OPERATIONAL,
            summary='Deployment before Q3',
            rigidity=Rigidity.FLEXIBLE,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.canonical_key is None
        assert s.what is None
        assert s.dimension is None

    def test_canonical_key_stays_none_on_resave(self, account, activity, user_a):
        s = ConstraintSignal(
            account=account,
            source_activity=activity,
            nature=ConstraintNature.OPERATIONAL,
            summary='Process must complete in under 2 weeks',
            rigidity=Rigidity.FIRM,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        assert s.canonical_key is None

        s.nature = ConstraintNature.TECHNICAL
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.canonical_key is None


# =============================================================================
# CLEAN() — source_activity required
# =============================================================================

class TestConstraintSignalClean:

    def test_clean_raises_without_source_activity(self, account):
        s = ConstraintSignal(
            account=account,
            nature=ConstraintNature.FINANCIAL,
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
            nature=ConstraintNature.FINANCIAL,
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
            nature=ConstraintNature.FINANCIAL,
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
            nature=ConstraintNature.OPERATIONAL,
            summary='Ideally before Q3',
            rigidity=Rigidity.FLEXIBLE,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.rigidity == Rigidity.FLEXIBLE


# =============================================================================
# TARGET DEPARTMENT — legacy single FK DROPPED (sub-step 1d)
# =============================================================================
# The scope axis is now the multi-department target_departments M2M
# (sub-steps 1a-1c). The legacy single FK target_department is removed here;
# these tests pin its absence and the M2M's presence via _meta.

class TestConstraintTargetDepartmentFKDropped:

    def test_legacy_target_department_fk_is_removed(self):
        with pytest.raises(FieldDoesNotExist):
            ConstraintSignal._meta.get_field('target_department')

    def test_target_departments_m2m_is_present(self):
        field = ConstraintSignal._meta.get_field('target_departments')
        assert field.many_to_many is True


# =============================================================================
# LIFECYCLE
# =============================================================================

class TestConstraintSignalLifecycle:

    def test_manual_source_auto_validated(self, account, activity, user_a):
        s = ConstraintSignal(
            account=account,
            source_activity=activity,
            nature=ConstraintNature.FINANCIAL,
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
            nature=ConstraintNature.OPERATIONAL,
            summary='Deployment before Q3',
            rigidity=Rigidity.FLEXIBLE,
            source=SignalSource.LLM_EXTRACTED,
            confidence=0.9,
        )
        s.save(user=user_a, client_id=account.client_id)
        assert s.status == SignalStatus.PENDING


# =============================================================================
# DOMAIN VALIDITY — a constraint without `what` is NOT invalidated
# =============================================================================

class TestConstraintDomainValidity:

    def test_constraint_without_what_is_domain_valid(self, account, activity, user_a):
        from app_modules.signals.services.signal_manager import SignalManager
        signal = SignalManager.create(
            data={
                'signal_type':     'constraint',
                'account':         account,
                'source_activity': activity,
                'source':          SignalSource.MANUAL,
                'nature':          ConstraintNature.CONTRACTUAL,
                'summary':         'GDPR compliance required',
                'rigidity':        Rigidity.FIRM,
            },
            user=user_a,
            client_id=account.client_id,
        )
        signal.refresh_from_db()
        # No `what` supplied → _flag_invalid_domain early-returns, stays valid.
        assert signal.is_domain_valid is True
        assert signal.what is None
        assert signal.canonical_key is None


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
            nature=ConstraintNature.FINANCIAL,
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
