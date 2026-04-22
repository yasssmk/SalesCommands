# app_modules/signals/serializers/cluster_serializer.py
"""
Serializers for signal clusters — output of SignalClusterService.

A cluster is not an ORM entity — it is a dict produced on read by
SignalClusterService.list_clusters_for_account / get_cluster_detail.
These serializers therefore extend plain serializers.Serializer, not
ModelSerializer.

Two serializers:
  SignalClusterListSerializer   — cluster payload without members
                                   (used by the /clusters/ listing endpoint)
  SignalClusterDetailSerializer — adds the 'members' field with full Pain
                                   detail including nested impacts
                                   (used by the /clusters/{key}/ endpoint)

Member serialization is delegated to PainSignalDetailSerializer, which
already knows how to render a Pain with its nested impacts. The cluster
detail serializer hands the Pain instances to it via a nested
many=True invocation.

Scope notes
-----------
- Sprint 2 covers Pain only. If another signal type is later supported,
  member serialization will need a signal_type dispatch — until then, it
  is intentionally hardcoded on PainSignalDetailSerializer for clarity.
- Human impacts and metrics are aggregated lists of primitives, not
  nested model instances — no sub-serializer needed.
"""

from rest_framework import serializers

from .pain_serializer import PainSignalDetailSerializer


# =============================================================================
# NESTED HELPER — human impact entry
# =============================================================================

class _HumanImpactEntrySerializer(serializers.Serializer):
    """
    One entry of the aggregated `human_impacts` list.

    Produced by SignalClusterService._aggregate_impacts as
    {'type': <HumanImpact value>, 'count': <int>}.
    """
    type  = serializers.CharField()
    count = serializers.IntegerField()


# =============================================================================
# LIST SERIALIZER
# =============================================================================

class SignalClusterListSerializer(serializers.Serializer):
    """
    Output serializer for the cluster listing endpoint.

    Source is the dict returned by SignalClusterService.list_clusters_for_account.
    The serializer does no transformation beyond typing — the service is
    the sole owner of the cluster shape.

    The `priority_score` field is exposed for debugging purposes; the UI
    is expected to render `priority_bucket` only (product decision).
    """

    # --- Identity ---
    canonical_key     = serializers.CharField()
    signal_type       = serializers.CharField()
    what              = serializers.CharField(allow_null=True)
    what_display      = serializers.CharField(allow_null=True)
    dimension         = serializers.CharField(allow_null=True)
    dimension_display = serializers.CharField(allow_null=True)
    summary           = serializers.CharField(allow_null=True, allow_blank=True)

    # --- Corroboration & breadth ---
    confirmation_count      = serializers.IntegerField()
    distinct_contacts_count = serializers.IntegerField()
    impacted_contacts_count = serializers.IntegerField()

    # --- Status ---
    status              = serializers.CharField()
    has_pending_signals = serializers.BooleanField()
    pending_count       = serializers.IntegerField()

    # --- Lifecycle ---
    first_observed_at = serializers.DateTimeField(allow_null=True)
    last_confirmed_at = serializers.DateTimeField(allow_null=True)
    freshness_status  = serializers.CharField(allow_null=True)

    # --- Impacts ---
    human_impacts    = _HumanImpactEntrySerializer(many=True)
    metrics          = serializers.ListField(child=serializers.CharField())
    max_impact_level = serializers.CharField(allow_null=True)

    # --- Priority ---
    priority_score  = serializers.IntegerField()
    priority_bucket = serializers.CharField()

    # --- Linking ---
    decision_cycle_ids = serializers.ListField(child=serializers.CharField())
    campaign_ids       = serializers.ListField(child=serializers.CharField())

    # --- Archival ---
    is_archived = serializers.BooleanField()


# =============================================================================
# DETAIL SERIALIZER
# =============================================================================

class SignalClusterDetailSerializer(SignalClusterListSerializer):
    """
    Output serializer for the cluster detail endpoint.

    Extends the list payload with the cluster's member signals
    (full PainSignalDetailSerializer payload, nested impacts included).

    Only Pain clusters are rendered in Sprint 2 — the members field is
    therefore explicitly bound to PainSignalDetailSerializer. Adding
    another cluster type later will require branching on signal_type;
    kept hardcoded for now to avoid premature abstraction.
    """

    members = PainSignalDetailSerializer(many=True, read_only=True)