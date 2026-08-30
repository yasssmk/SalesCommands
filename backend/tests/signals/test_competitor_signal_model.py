# backend/tests/signals/test_competitor_signal_model.py
"""
Model-level invariants for CompetitorSignal.

Cloned on tests/signals/test_constraint_signal_model.py — same discipline,
adapted to the detached competitor pattern. The anchor test exercises the
REAL creation path (SignalManager.create(signal_type='competitor')); the
rest cover the model invariants (shadow-override, canonical_key detach,
name normalisation, clean(), lifecycle).
"""

import pytest
from django.core.exceptions import FieldDoesNotExist, ValidationError

from app_modules.signals.constants import (
    SignalSource,
    SignalStatus,
)
from app_modules.signals.models import CompetitorSignal
from app_modules.signals.services.signal_manager import SignalManager


pytestmark = pytest.mark.django_db


# =============================================================================
# REAL-PATH CREATION — SignalManager.create(signal_type='competitor')
# =============================================================================

class TestCompetitorSignalCreateRealPath:

    def test_create_via_signal_manager(self, account, activity, user_a):
        signal = SignalManager.create(
            data={
                'signal_type':     'competitor',
                'account':         account,
                'source_activity': activity,
                'source':          SignalSource.MANUAL,
                'competitor_name': 'Acme Corp',
                'summary':         'Prospect evaluating Acme as primary alternative',
            },
            user=user_a,
            client_id=account.client_id,
        )
        signal.refresh_from_db()
        assert isinstance(signal, CompetitorSignal)
        assert signal.competitor_name == 'Acme Corp'
        assert signal.summary == 'Prospect evaluating Acme as primary alternative'
        assert signal.status == SignalStatus.VALIDATED
        assert signal.canonical_key is None
        assert signal.competitor_name_normalized == 'acme corp'


# =============================================================================
# SHADOW OVERRIDES
# =============================================================================

class TestCompetitorSignalShadowOverride:

    def test_signal_category_field_does_not_exist_on_meta(self):
        with pytest.raises(FieldDoesNotExist):
            CompetitorSignal._meta.get_field('signal_category')

    def test_signal_category_class_attr_is_none(self):
        assert CompetitorSignal.signal_category is None


# =============================================================================
# CANONICAL KEY — detached (always None)
# =============================================================================

class TestCompetitorSignalCanonicalKeyDetached:

    def test_canonical_key_none_on_create(self, account, activity, user_a):
        s = CompetitorSignal(
            account=account,
            source_activity=activity,
            competitor_name='Acme Corp',
            summary='Evaluating Acme',
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.canonical_key is None

    def test_canonical_key_stays_none_on_resave(self, account, activity, user_a):
        s = CompetitorSignal(
            account=account,
            source_activity=activity,
            competitor_name='Acme Corp',
            summary='Evaluating Acme',
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        assert s.canonical_key is None

        s.summary = 'Now the frontrunner'
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.canonical_key is None


# =============================================================================
# NAME NORMALISATION — competitor_name_normalized derived in save()
# =============================================================================

class TestCompetitorNameNormalized:

    def test_normalized_lower_trim_collapse(self, account, activity, user_a):
        s = CompetitorSignal(
            account=account,
            source_activity=activity,
            competitor_name='  Acme   Corp ',
            summary='Evaluating Acme',
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.competitor_name == '  Acme   Corp '
        assert s.competitor_name_normalized == 'acme corp'

    def test_normalized_recomputed_on_resave(self, account, activity, user_a):
        s = CompetitorSignal(
            account=account,
            source_activity=activity,
            competitor_name='Acme',
            summary='Evaluating Acme',
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        assert s.competitor_name_normalized == 'acme'

        s.competitor_name = 'Globex INC'
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.competitor_name_normalized == 'globex inc'


# =============================================================================
# CLEAN() — source_activity required
# =============================================================================

class TestCompetitorSignalClean:

    def test_clean_raises_without_source_activity(self, account):
        s = CompetitorSignal(
            account=account,
            competitor_name='Acme Corp',
            summary='Evaluating Acme',
        )
        with pytest.raises(ValidationError) as exc_info:
            s.clean()
        assert 'source_activity' in exc_info.value.message_dict

    def test_clean_passes_with_source_activity(self, account, activity):
        s = CompetitorSignal(
            account=account,
            source_activity=activity,
            competitor_name='Acme Corp',
            summary='Evaluating Acme',
        )
        s.clean()


# =============================================================================
# LIFECYCLE
# =============================================================================

class TestCompetitorSignalLifecycle:

    def test_manual_source_auto_validated(self, account, activity, user_a):
        s = CompetitorSignal(
            account=account,
            source_activity=activity,
            competitor_name='Acme Corp',
            summary='Evaluating Acme',
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        assert s.status == SignalStatus.VALIDATED
        assert s.confidence is None

    def test_llm_extracted_starts_pending(self, account, activity, user_a):
        s = CompetitorSignal(
            account=account,
            source_activity=activity,
            competitor_name='Acme Corp',
            summary='Evaluating Acme',
            source=SignalSource.LLM_EXTRACTED,
            confidence=0.9,
        )
        s.save(user=user_a, client_id=account.client_id)
        assert s.status == SignalStatus.PENDING
