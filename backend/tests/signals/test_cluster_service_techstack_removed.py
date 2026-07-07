# backend/tests/signals/test_cluster_service_techstack_removed.py
"""
Tests for the removal of TechStack from the clustering mechanism.

Product decision: TechStack is NOT clusterable. These tests lock in
that:
  * SignalClusterService rejects 'tech_stack' at its API surface (list
    and detail), including inside a mixed signal_type list.
  * Pain / Objective / Impact remain accepted (regression guard).
  * TechStackSignal.save() no longer computes a canonical_key.

The cluster service has no dedicated test suite prior to this change;
this file is the first.
"""

import uuid

import pytest

from app_modules.signals.constants import SignalSource
from app_modules.signals.models import TechStackSignal
from app_modules.signals.services import SignalClusterService
from core.exceptions import StandardizedValidationError


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


# =============================================================================
# GUARD — tech_stack rejected at the service surface
# =============================================================================

class TestTechStackClusterTypeRejected:

    def test_list_rejects_tech_stack(self, account):
        with pytest.raises(StandardizedValidationError):
            SignalClusterService.list_clusters_for_account(
                account_id=account.id,
                signal_type='tech_stack',
            )

    def test_detail_rejects_tech_stack(self, account):
        with pytest.raises(StandardizedValidationError):
            SignalClusterService.get_cluster_detail(
                account_id=account.id,
                canonical_key='techstack:%s' % uuid.uuid4(),
                signal_type='tech_stack',
            )

    def test_mixed_list_containing_tech_stack_rejected(self, account):
        # A CSV/list request that mixes a supported type with tech_stack
        # must still be rejected — the guard is strict, no silent drop.
        with pytest.raises(StandardizedValidationError):
            SignalClusterService.list_clusters_for_account(
                account_id=account.id,
                signal_type=['pain', 'tech_stack'],
            )


# =============================================================================
# REGRESSION — clusterable types still accepted
# =============================================================================

class TestClusterableTypesStillAccepted:

    @pytest.mark.parametrize('signal_type', ['pain', 'objective', 'impact'])
    def test_supported_types_do_not_raise(self, account, signal_type):
        result = SignalClusterService.list_clusters_for_account(
            account_id=account.id,
            signal_type=signal_type,
        )
        # No signals seeded — an empty list is the correct, non-raising
        # outcome. The point is the guard accepts the type.
        assert result == []


# =============================================================================
# MODEL — canonical_key no longer computed on TechStackSignal
# =============================================================================

class TestTechStackNoCanonicalKey:

    def test_save_with_catalog_entry_leaves_canonical_key_none(
        self, account, activity, tech_catalog_entry, user_a,
    ):
        signal = TechStackSignal(
            account=account,
            source_activity=activity,
            tech_catalog_entry=tech_catalog_entry,
            source=SignalSource.MANUAL,
        )
        signal.save(user=user_a, client_id=account.client_id)
        assert signal.canonical_key is None

    def test_save_without_catalog_entry_leaves_canonical_key_none(
        self, account, activity, user_a,
    ):
        # PENDING LLM-extracted, unmatched tool: no catalog FK.
        signal = TechStackSignal(
            account=account,
            source_activity=activity,
            tech_catalog_entry=None,
            source=SignalSource.LLM_EXTRACTED,
        )
        signal.save(user=user_a, client_id=account.client_id)
        assert signal.canonical_key is None
