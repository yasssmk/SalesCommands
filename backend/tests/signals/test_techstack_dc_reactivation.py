# backend/tests/signals/test_techstack_dc_reactivation.py
"""
Tests for the TechStackSignal decision_cycle reactivation.

The shadow-override `decision_cycle = None` has been removed from
TechStackSignal. The field is now inherited from BaseSignal and can
be set to associate a TechStack observation with a specific deal
(competitor in play) or left null (tool in place at account level).

Covers:
  * decision_cycle field exists on TechStackSignal meta
  * TechStack can be saved with decision_cycle = None (account-level)
  * TechStack can be saved with a decision_cycle FK (deal-level)
  * campaign and signal_category remain shadow-overridden
"""

import pytest
from django.core.exceptions import FieldDoesNotExist

from app_modules.signals.constants import SignalSource
from app_modules.signals.models import TechStackSignal


pytestmark = pytest.mark.django_db


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def tech_catalog_entry(db, client_account_a, user_a):
    from app_modules.tech_catalog.models import TechCatalog
    entry = TechCatalog(
        company_name='Salesforce',
        product_name='Sales Cloud',
    )
    entry.save(user=user_a, client_id=client_account_a.id)
    return entry


@pytest.fixture
def decision_cycle(db, account, user_a):
    from app_modules.decision_cycles.models import DecisionCycle
    dc = DecisionCycle(
        name='Module Consolidation v2',
        account=account,
        is_active=True,
    )
    dc.save(user=user_a, client_id=account.client_id)
    return dc


# =============================================================================
# DECISION CYCLE FIELD — restored from BaseSignal
# =============================================================================

class TestTechStackDecisionCycleRestored:

    def test_decision_cycle_field_exists_on_meta(self):
        field = TechStackSignal._meta.get_field('decision_cycle')
        assert field is not None
        assert field.null is True

    def test_save_without_decision_cycle(
        self, account, activity, tech_catalog_entry, user_a,
    ):
        s = TechStackSignal(
            account=account,
            source_activity=activity,
            tech_catalog_entry=tech_catalog_entry,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.decision_cycle_id is None

    def test_save_with_decision_cycle(
        self, account, activity, tech_catalog_entry, decision_cycle, user_a,
    ):
        s = TechStackSignal(
            account=account,
            source_activity=activity,
            tech_catalog_entry=tech_catalog_entry,
            decision_cycle=decision_cycle,
            source=SignalSource.MANUAL,
        )
        s.save(user=user_a, client_id=account.client_id)
        s.refresh_from_db()
        assert s.decision_cycle_id == decision_cycle.id


# =============================================================================
# REMAINING SHADOW OVERRIDES — campaign + signal_category still None
# =============================================================================

class TestTechStackRemainingOverrides:

    def test_campaign_still_overridden(self):
        assert TechStackSignal.campaign is None
        with pytest.raises(FieldDoesNotExist):
            TechStackSignal._meta.get_field('campaign')

    def test_signal_category_still_overridden(self):
        assert TechStackSignal.signal_category is None
        with pytest.raises(FieldDoesNotExist):
            TechStackSignal._meta.get_field('signal_category')
