# backend/tests/signals/test_cluster_service_techstack.py
"""
TechStack read-time clustering (Cluster Tech Stack sprint, sub-step 2).

SignalClusterService now aggregates TechStackSignal into clusters keyed on
`tech_name_normalized` — NOT on a stored canonical_key (TechStack has none).
The grouping is 100% derived at read time: nothing about membership is
stored, so editing a signal's tech_name (which re-derives its normalised key
on save) regroups it on the very next fetch with no other action.

These tests drive the REAL service the views call
(SignalClusterService.list_clusters_for_account / get_cluster_detail), and
the real cluster serializers, so they exercise the exact aggregation path a
surface would hit — no shortcut.

What they prove:
  * two signals with the same normalised name -> one cluster (signal_count=2);
  * two different normalised names -> two clusters;
  * three spellings of one tool -> one cluster of three members (the
    non-vacuity target: re-key the grouping on id and this goes red);
  * the EDIT scenario — the read-time proof: two clusters ("HubSpot" /
    "HubSpot CRM"), re-save one to "HubSpot", refetch -> one cluster, with NO
    other action. Red if membership were stored anywhere;
  * the unified cluster contract is emitted with neutral values on the keys
    TechStack has no field for (what/dimension/departments/scope/target/…),
    and it serialises through the shared cluster serializers unchanged;
  * members serialise through the existing TechStackSignalListSerializer;
  * the query count is bounded and constant regardless of signal/cluster count.
"""

import pytest

from django.db import connection
from django.test.utils import CaptureQueriesContext

from app_modules.signals.constants import (
    PriorityBucket,
    SignalSource,
    SignalStatus,
)
from app_modules.signals.models import TechStackSignal
from app_modules.signals.serializers import (
    SignalClusterDetailSerializer,
    SignalClusterListSerializer,
)
from app_modules.signals.services import SignalClusterService


pytestmark = pytest.mark.django_db


# =============================================================================
# HELPERS
# =============================================================================

def _mk_tech(account, activity, user_a, tech_name, *,
             source=SignalSource.MANUAL, **extra):
    """
    Create + persist a TechStackSignal. MANUAL source lands VALIDATED (the
    BaseSignal create rule); pass source=LLM_EXTRACTED for a PENDING member.
    tech_name_normalized is derived by the model's save().
    """
    sig = TechStackSignal(
        account=account,
        source_activity=activity,
        tech_name=tech_name,
        source=source,
        **extra,
    )
    sig.save(user=user_a, client_id=account.client_id)
    return sig


def _list_tech(account, **kwargs):
    return SignalClusterService.list_clusters_for_account(
        account_id=account.id,
        signal_type='tech_stack',
        **kwargs,
    )


# =============================================================================
# GROUPING — same normalised name collapses; different names stay apart
# =============================================================================

class TestTechClusterGrouping:

    def test_two_signals_same_normalized_form_one_cluster(
        self, account, activity, user_a,
    ):
        # "HubSpot" and "Hubspot" both normalise to "hubspot".
        _mk_tech(account, activity, user_a, 'HubSpot')
        _mk_tech(account, activity, user_a, 'Hubspot')

        clusters = _list_tech(account)

        assert len(clusters) == 1
        cluster = clusters[0]
        assert cluster['canonical_key'] == 'hubspot'
        assert cluster['signal_type'] == 'tech_stack'
        assert cluster['signal_count'] == 2
        # The headline is the reference member's RAW display name (most recent
        # VALIDATED), not the normalised key. Both raw names are valid display
        # forms of the tool; the most recent one created here is "Hubspot".
        assert cluster['summary'] == 'Hubspot'

    def test_two_different_normalized_form_two_clusters(
        self, account, activity, user_a,
    ):
        _mk_tech(account, activity, user_a, 'HubSpot')
        _mk_tech(account, activity, user_a, 'Salesforce')

        clusters = _list_tech(account)

        assert len(clusters) == 2
        assert sorted(c['canonical_key'] for c in clusters) == [
            'hubspot', 'salesforce',
        ]
        assert all(c['signal_count'] == 1 for c in clusters)

    def test_three_spellings_of_one_tool_form_one_cluster(
        self, account, activity, user_a,
    ):
        # NON-VACUITY TARGET: re-key the grouping on id (instead of
        # tech_name_normalized) in signal_cluster_service and this fails.
        _mk_tech(account, activity, user_a, 'Salesforce')
        _mk_tech(account, activity, user_a, 'salesforce')
        _mk_tech(account, activity, user_a, '  Salesforce  ')

        clusters = _list_tech(account)

        assert len(clusters) == 1
        assert clusters[0]['signal_count'] == 3
        assert clusters[0]['canonical_key'] == 'salesforce'


# =============================================================================
# THE READ-TIME PROOF — editing tech_name regroups on the next fetch
# =============================================================================

class TestReadTimeRegrouping:

    def test_editing_tech_name_merges_two_clusters_on_next_fetch(
        self, account, activity, user_a,
    ):
        """
        Two distinct clusters ("HubSpot" / "HubSpot CRM"); after correcting
        the second signal's name to "HubSpot", a plain refetch must show ONE
        cluster — no membership recompute call, no stored linkage touched.
        This is the test that would be RED if cluster membership were stored.
        """
        _mk_tech(account, activity, user_a, 'HubSpot')
        second = _mk_tech(account, activity, user_a, 'HubSpot CRM')

        before = _list_tech(account)
        assert len(before) == 2
        assert sorted(c['canonical_key'] for c in before) == [
            'hubspot', 'hubspot crm',
        ]

        # The user removes the "CRM" descriptor. save() re-derives the
        # normalised key — the ONLY action taken.
        second.tech_name = 'HubSpot'
        second.save(user=user_a, client_id=account.client_id)
        assert second.tech_name_normalized == 'hubspot'

        after = _list_tech(account)
        assert len(after) == 1
        assert after[0]['canonical_key'] == 'hubspot'
        assert after[0]['signal_count'] == 2


# =============================================================================
# CONTRACT — unified cluster shape with neutral values, serialises cleanly
# =============================================================================

class TestTechClusterContract:

    def test_neutral_values_on_inapplicable_keys(
        self, account, activity, user_a,
    ):
        _mk_tech(account, activity, user_a, 'Notion')
        cluster = _list_tech(account)[0]

        # Canonical axes have no meaning for tech -> neutral (allow_null).
        assert cluster['what'] is None
        assert cluster['what_display'] is None
        assert cluster['dimension'] is None
        assert cluster['dimension_display'] is None
        # No subject-department / scope / target-date axes on TechStack.
        assert cluster['departments'] == []
        assert cluster['max_scope_level'] is None
        assert cluster['target_dates'] == []
        assert cluster['has_target_date_soon'] is False
        # No campaign FK on TechStack (shadow-overridden to None).
        assert cluster['campaign_ids'] == []
        # No priority model for tech -> neutral floor.
        assert cluster['priority_score'] == 0
        assert cluster['priority_bucket'] == PriorityBucket.LOW

    def test_cluster_list_serializer_renders_tech_cluster(
        self, account, activity, user_a,
    ):
        _mk_tech(account, activity, user_a, 'Slack')
        clusters = _list_tech(account)

        # The shared cluster serializer must render a tech cluster with no
        # new field and no error.
        data = SignalClusterListSerializer(clusters, many=True).data
        assert len(data) == 1
        assert data[0]['signal_type'] == 'tech_stack'
        assert data[0]['canonical_key'] == 'slack'
        assert data[0]['what'] is None

    def test_validated_and_pending_counts(
        self, account, activity, user_a,
    ):
        # Two validated + one pending mention of the same tool.
        _mk_tech(account, activity, user_a, 'Jira')
        _mk_tech(account, activity, user_a, 'jira')
        _mk_tech(account, activity, user_a, 'JIRA',
                 source=SignalSource.LLM_EXTRACTED)  # PENDING

        cluster = _list_tech(account)[0]
        assert cluster['signal_count'] == 3
        assert cluster['confirmation_count'] == 2
        assert cluster['pending_count'] == 1
        assert cluster['has_pending_signals'] is True
        assert cluster['status'] == SignalStatus.VALIDATED


# =============================================================================
# DETAIL — members via the existing tech list serializer
# =============================================================================

class TestTechClusterDetail:

    def test_detail_returns_members_through_tech_serializer(
        self, account, activity, user_a,
    ):
        _mk_tech(account, activity, user_a, 'Salesforce', is_competitor=True)
        _mk_tech(account, activity, user_a, 'salesforce')

        detail = SignalClusterService.get_cluster_detail(
            account_id=account.id,
            canonical_key='salesforce',
            signal_type='tech_stack',
        )
        assert detail['signal_count'] == 2
        assert len(detail['members']) == 2

        data = SignalClusterDetailSerializer(detail).data
        members = data['members']
        assert len(members) == 2
        # The tech member serializer exposes identity + qualification.
        assert {'tech_name', 'is_competitor', 'is_integration',
                'is_to_replace'} <= set(members[0].keys())
        assert any(m['is_competitor'] for m in members)

    def test_detail_unknown_key_raises(self, account, activity, user_a):
        from core.exceptions import StandardizedValidationError
        _mk_tech(account, activity, user_a, 'Salesforce')
        with pytest.raises(StandardizedValidationError):
            SignalClusterService.get_cluster_detail(
                account_id=account.id,
                canonical_key='does-not-exist',
                signal_type='tech_stack',
            )


# =============================================================================
# N+1 — bounded, constant query count regardless of signal / cluster count
# =============================================================================

class TestTechClusterQueryCount:

    def _count_list_queries(self, account):
        with CaptureQueriesContext(connection) as ctx:
            # Force full evaluation (the service returns a plain list).
            _list_tech(account)
        return len(ctx)

    def test_query_count_is_constant_as_data_grows(
        self, account, activity, user_a, contact, contact_extra,
    ):
        # Small dataset: 2 signals, 1 cluster, one contact on the activity.
        activity.contacts.add(contact)
        _mk_tech(account, activity, user_a, 'HubSpot')
        _mk_tech(account, activity, user_a, 'hubspot')
        small = self._count_list_queries(account)

        # Larger dataset: more signals, more clusters, more contacts.
        activity.contacts.add(contact_extra)
        _mk_tech(account, activity, user_a, 'Salesforce')
        _mk_tech(account, activity, user_a, 'salesforce')
        _mk_tech(account, activity, user_a, 'Slack')
        _mk_tech(account, activity, user_a, 'Notion')
        large = self._count_list_queries(account)

        # No N+1: adding signals / clusters / contacts does not add queries.
        assert small == large
        # And the bound is small (signals + contacts prefetch), not per-member.
        assert large <= 4


# =============================================================================
# REGRESSION — adding tech did not disturb the axis-based types
# =============================================================================

class TestAxisTypesUnaffected:

    def test_mixed_list_returns_tech_and_pain_without_raising(
        self, account, activity, user_a,
    ):
        from app_modules.signals.models import PainSignal
        from app_modules.signals.constants import SignalWhat, SignalDimension

        _mk_tech(account, activity, user_a, 'Salesforce')
        pain = PainSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.OPS,
            dimension=SignalDimension.TIME,
            summary='Reporting is slow',
            source_quote='it takes hours',
            source=SignalSource.MANUAL,
        )
        pain.save(user=user_a, client_id=account.client_id)

        clusters = SignalClusterService.list_clusters_for_account(
            account_id=account.id,
            signal_type=['pain', 'tech_stack'],
        )
        types = sorted(c['signal_type'] for c in clusters)
        assert types == ['pain', 'tech_stack']
        # The pain cluster keeps its real canonical_key; tech uses the
        # normalised tool name.
        pain_cluster = next(c for c in clusters if c['signal_type'] == 'pain')
        tech_cluster = next(c for c in clusters if c['signal_type'] == 'tech_stack')
        assert pain_cluster['canonical_key'] == 'pain:OPS:TIME'
        assert tech_cluster['canonical_key'] == 'salesforce'


# =============================================================================
# SORT SENTINEL — timezone-aware (regression for the 500 at :304-308)
# =============================================================================
#
# list_clusters_for_account sorts by (priority_score, last_confirmed_at). On a
# priority_score TIE the secondary key is compared; the None fallback used a
# NAIVE datetime sentinel while last_confirmed_at is timezone-AWARE (derived
# from created_at under USE_TZ=True) -> TypeError: can't compare offset-naive
# and offset-aware datetimes -> HTTP 500.
#
# TechStack forces the tie (priority_score is a hardcoded 0 for every tech
# cluster), so any account with a validated tech cluster AND a pending-only
# tech cluster reproduces it. The defect is in the SORT SENTINEL, shared by
# every signal_type — not in tech; tech is only the minimal trigger. Forcing
# the same aware/None + equal-score pair on pain/objective/impact is not
# feasible: a VALIDATED member always adds corroboration/freshness weight, so a
# validated cluster never ties with a pending-only sibling of the same type.
# The fix at the sentinel line covers those types by construction.


class TestSortSentinelTimezone:

    def test_tied_score_validated_plus_pending_only_tech_sorts_without_500(
        self, account, activity, user_a,
    ):
        """
        Two tech clusters, same priority_score (0):
          - 'Alpha' has a VALIDATED member  -> last_confirmed_at is AWARE.
          - 'Beta'  is PENDING-only          -> last_confirmed_at is None
                                                (falls back to the sentinel).
        The score tie forces the secondary datetime comparison. Before the fix
        (naive sentinel) this raised TypeError inside clusters.sort(); after the
        fix it sorts deterministically and returns both clusters.
        """
        # 'Alpha' — VALIDATED (MANUAL): aware last_confirmed_at.
        _mk_tech(account, activity, user_a, 'Alpha')
        # 'Beta' — PENDING-only (LLM_EXTRACTED): last_confirmed_at is None.
        _mk_tech(account, activity, user_a, 'Beta',
                 source=SignalSource.LLM_EXTRACTED)

        # The real entry point the view calls — must NOT raise.
        clusters = _list_tech(account)

        assert len(clusters) == 2
        keys = sorted(c['canonical_key'] for c in clusters)
        assert keys == ['alpha', 'beta']
        # Both carry the neutral tech priority floor (the tie that triggers the
        # secondary comparison).
        assert all(c['priority_score'] == 0 for c in clusters)

    def test_two_pending_only_tech_clusters_also_sort_without_500(
        self, account, activity, user_a,
    ):
        """
        Both clusters PENDING-only: both last_confirmed_at None -> both hit the
        sentinel, which is then compared to itself. A naive sentinel compares
        fine against a naive sentinel, so this case did NOT crash before the
        fix — it is kept as a guard that the aware sentinel is self-consistent
        and the ordering stays stable.
        """
        _mk_tech(account, activity, user_a, 'Gamma',
                 source=SignalSource.LLM_EXTRACTED)
        _mk_tech(account, activity, user_a, 'Delta',
                 source=SignalSource.LLM_EXTRACTED)

        clusters = _list_tech(account)
        assert len(clusters) == 2
        assert sorted(c['canonical_key'] for c in clusters) == ['delta', 'gamma']
