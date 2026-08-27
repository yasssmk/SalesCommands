# backend/tests/signals/test_cluster_service_techstack_removed.py
"""
History of TechStack in the clustering mechanism.

S10 removed TechStack from clustering entirely. The Cluster Tech Stack
sprint (sub-step 2) re-added it — but keyed on `tech_name_normalized`
computed at read time, NOT on a stored canonical_key. This file keeps the
two invariants that survived that reversal:

  * Pain / Objective / Impact remain accepted (regression guard).
  * TechStackSignal.save() still does NOT compute a canonical_key — the
    read-time grouping key is tech_name_normalized, and storing a
    canonical_key would reintroduce stored membership. THIS is why the edit
    scenario works; see test_cluster_service_techstack.py for the read-time
    grouping behaviour itself.

The obsolete "tech_stack is rejected" guard has been flipped to assert the
type is now accepted (empty list when no signals are seeded).
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

# =============================================================================
# GUARD — tech_stack now ACCEPTED at the service surface (was rejected in S10)
# =============================================================================

class TestTechStackClusterTypeAccepted:

    def test_list_accepts_tech_stack(self, account):
        # No signals seeded -> empty list, no raise. The point is the guard
        # accepts the type now (S10 rejected it).
        result = SignalClusterService.list_clusters_for_account(
            account_id=account.id,
            signal_type='tech_stack',
        )
        assert result == []

    def test_detail_unknown_tech_key_raises_not_found_not_unsupported(
        self, account,
    ):
        # tech_stack is a supported type, so a missing cluster raises the
        # NOT_FOUND business error (empty members), not a "type unsupported"
        # rejection. Either way it raises StandardizedValidationError; the
        # distinction is asserted in test_cluster_service_techstack.py.
        with pytest.raises(StandardizedValidationError):
            SignalClusterService.get_cluster_detail(
                account_id=account.id,
                canonical_key='no-such-tool-%s' % uuid.uuid4(),
                signal_type='tech_stack',
            )

    def test_mixed_list_with_tech_stack_is_accepted(self, account):
        # A CSV/list request mixing a supported axis type with tech_stack is
        # now honoured (both are supported); no signals -> empty list.
        result = SignalClusterService.list_clusters_for_account(
            account_id=account.id,
            signal_type=['pain', 'tech_stack'],
        )
        assert result == []


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
        self, account, activity, user_a,
    ):
        signal = TechStackSignal(
            account=account,
            source_activity=activity,
            tech_name='Salesforce',
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
            tech_name='HubSpot',
            source=SignalSource.LLM_EXTRACTED,
        )
        signal.save(user=user_a, client_id=account.client_id)
        assert signal.canonical_key is None


# =============================================================================
# COMPAT KEYS — dead TechStack-compat keys stripped from Pain/Impact clusters
# =============================================================================

_TECHSTACK_COMPAT_KEYS = (
    'lifecycle',
    'scope_summary',
    'has_renewal_soon',
    'related_pain_clusters',
)


class TestTechStackCompatKeysStripped:
    """
    After removing TechStack from clustering, the neutral TechStack-compat
    keys must no longer be emitted by the Pain / Impact cluster builders,
    and the cluster serializers must no longer declare them (nor the
    detail-only `all_observations`).
    """

    @pytest.fixture
    def pain_cluster(self, account, activity, user_a):
        from app_modules.signals.models import PainSignal
        from app_modules.signals.constants import SignalWhat, SignalDimension
        pain = PainSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.OPS,
            dimension=SignalDimension.TIME,
            summary='Reporting is slow',
            source_quote='it takes hours every week',
            source=SignalSource.MANUAL,
        )
        pain.save(user=user_a, client_id=account.client_id)
        clusters = SignalClusterService.list_clusters_for_account(
            account_id=account.id,
            signal_type='pain',
        )
        assert len(clusters) == 1
        return clusters[0]

    def test_builder_dict_omits_compat_keys(self, pain_cluster):
        for key in _TECHSTACK_COMPAT_KEYS:
            assert key not in pain_cluster

    def test_list_serializer_omits_compat_keys(self, pain_cluster):
        from app_modules.signals.serializers import SignalClusterListSerializer
        data = SignalClusterListSerializer(pain_cluster).data
        for key in _TECHSTACK_COMPAT_KEYS:
            assert key not in data

    def test_detail_serializer_omits_all_observations(self, account, pain_cluster):
        from app_modules.signals.serializers import SignalClusterDetailSerializer
        detail = SignalClusterService.get_cluster_detail(
            account_id=account.id,
            canonical_key=pain_cluster['canonical_key'],
            signal_type='pain',
        )
        data = SignalClusterDetailSerializer(detail).data
        assert 'all_observations' not in data
        for key in _TECHSTACK_COMPAT_KEYS:
            assert key not in data
