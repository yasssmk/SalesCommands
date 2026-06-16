# backend/tests/signals/test_people_signal_model.py
"""
Model-level invariants for PeopleSignal.

Covers:
  * Shadow-overrides (signal_category)
  * canonical_key forced to None (non-clustering)
  * clean() requires source_activity + at least one target
  * MANUAL → VALIDATED auto, LLM_EXTRACTED → PENDING auto
  * Cache invalidation: SIGNALS_CACHE_TAG only
"""

import pytest
from django.core.exceptions import FieldDoesNotExist, ValidationError

from app_modules.signals.constants import (
    SIGNAL_CLUSTERS_CACHE_TAG,
    SIGNALS_CACHE_TAG,
    InfluenceLevel,
    PeopleRole,
    SignalSource,
    SignalStatus,
)
from app_modules.signals.models import PeopleSignal


pytestmark = pytest.mark.django_db


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def department(db):
    from app_modules.core_modules.models import StandardDepartment
    dept, _ = StandardDepartment.objects.get_or_create(name='Sales')
    return dept


# =============================================================================
# SHADOW OVERRIDES
# =============================================================================

class TestPeopleSignalShadowOverride:

    def test_signal_category_field_does_not_exist_on_meta(self):
        with pytest.raises(FieldDoesNotExist):
            PeopleSignal._meta.get_field('signal_category')

    def test_signal_category_class_attr_is_none(self):
        assert PeopleSignal.signal_category is None


# =============================================================================
# CANONICAL KEY — never populated
# =============================================================================

class TestPeopleSignalCanonicalKey:

    def test_canonical_key_remains_none_after_manual_save(
        self, account, activity, contact, user_a,
    ):
        s = PeopleSignal(
            account=account,
            source_activity=activity,
            role=PeopleRole.CHAMPION,
            target_contact=contact,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.canonical_key is None

    def test_canonical_key_remains_none_after_llm_save(
        self, account, activity, contact, user_a,
    ):
        s = PeopleSignal(
            account=account,
            source_activity=activity,
            role=PeopleRole.ECONOMIC_BUYER,
            target_contact=contact,
            source=SignalSource.LLM_EXTRACTED,
            confidence=0.85,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.canonical_key is None


# =============================================================================
# CLEAN() — source_activity + at least one target required
# =============================================================================

class TestPeopleSignalClean:

    def test_clean_raises_without_source_activity_for_llm(self, account, contact):
        """LLM-sourced signals always require source_activity."""
        s = PeopleSignal(
            account=account,
            source=SignalSource.LLM_EXTRACTED,
            role=PeopleRole.CHAMPION,
            target_contact=contact,
        )
        with pytest.raises(ValidationError) as exc_info:
            s.clean()
        assert 'source_activity' in exc_info.value.message_dict

    def test_clean_raises_manual_without_activity_or_cycle(self, account, contact):
        """MANUAL without source_activity AND without decision_cycle → error."""
        s = PeopleSignal(
            account=account,
            source=SignalSource.MANUAL,
            role=PeopleRole.CHAMPION,
            target_contact=contact,
        )
        with pytest.raises(ValidationError) as exc_info:
            s.clean()
        assert 'source_activity' in exc_info.value.message_dict

    def test_clean_passes_manual_with_decision_cycle(
        self, account, decision_cycle, contact,
    ):
        """MANUAL + decision_cycle anchor (no source_activity) → valid."""
        s = PeopleSignal(
            account=account,
            source=SignalSource.MANUAL,
            decision_cycle=decision_cycle,
            role=PeopleRole.CHAMPION,
            target_contact=contact,
        )
        s.clean()

    def test_clean_raises_without_any_target(self, account, activity):
        s = PeopleSignal(
            account=account,
            source_activity=activity,
            role=PeopleRole.INFLUENCER,
        )
        with pytest.raises(ValidationError) as exc_info:
            s.clean()
        assert 'target_contact' in exc_info.value.message_dict

    def test_clean_passes_with_contact_only(self, account, activity, contact):
        s = PeopleSignal(
            account=account,
            source_activity=activity,
            role=PeopleRole.CHAMPION,
            target_contact=contact,
        )
        s.clean()

    def test_clean_passes_with_department_only(
        self, account, activity, department,
    ):
        s = PeopleSignal(
            account=account,
            source_activity=activity,
            role=PeopleRole.ECONOMIC_BUYER,
            target_department=department,
        )
        s.clean()

    def test_clean_passes_with_both_targets(
        self, account, activity, contact, department,
    ):
        s = PeopleSignal(
            account=account,
            source_activity=activity,
            role=PeopleRole.DECISION_MAKER,
            target_contact=contact,
            target_department=department,
        )
        s.clean()


# =============================================================================
# LIFECYCLE — MANUAL auto-VALIDATED, LLM → PENDING
# =============================================================================

class TestPeopleSignalLifecycle:

    def test_manual_source_auto_validated(
        self, account, activity, contact, user_a,
    ):
        s = PeopleSignal(
            account=account,
            source_activity=activity,
            role=PeopleRole.CHAMPION,
            target_contact=contact,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        assert s.status == SignalStatus.VALIDATED
        assert s.confidence is None

    def test_manual_dc_level_auto_validated(
        self, account, decision_cycle, contact, user_a,
    ):
        """MANUAL + decision_cycle (no source_activity) → VALIDATED."""
        s = PeopleSignal(
            account=account,
            decision_cycle=decision_cycle,
            role=PeopleRole.ECONOMIC_BUYER,
            target_contact=contact,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        assert s.status == SignalStatus.VALIDATED
        assert s.confidence is None
        assert s.source_activity_id is None
        assert s.decision_cycle_id == decision_cycle.id

    def test_llm_extracted_starts_pending(
        self, account, activity, contact, user_a,
    ):
        s = PeopleSignal(
            account=account,
            source_activity=activity,
            role=PeopleRole.BLOCKER,
            target_contact=contact,
            source=SignalSource.LLM_EXTRACTED,
            confidence=0.7,
        )
        s.save(user=user_a, client_id=account.client_id)
        assert s.status == SignalStatus.PENDING


# =============================================================================
# CACHE INVALIDATION — signals only, never clusters
# =============================================================================

class TestPeopleSignalCacheInvalidation:

    @pytest.mark.django_db(transaction=True)
    def test_save_invalidates_signals_tag_only(
        self, account, activity, contact, user_a,
        cache_invalidation_calls,
    ):
        s = PeopleSignal(
            account=account,
            source_activity=activity,
            role=PeopleRole.END_USER,
            target_contact=contact,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)

        client_str = str(account.client_id)
        signal_tags = [
            ns for cid, ns in cache_invalidation_calls if cid == client_str
        ]
        assert SIGNALS_CACHE_TAG in signal_tags
        assert SIGNAL_CLUSTERS_CACHE_TAG not in signal_tags
