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
# NESTED HELPERS — `by_level` breakdown  (detail-only, Wave A)
# =============================================================================
#
# These serializers type the per-ScopeLevel breakdown produced by
# SignalClusterService._aggregate_by_level and exposed on cluster detail
# only. See the service docstring for the authoritative shape definition.
#
# The breakdown dict is keyed dynamically (department / contact UUIDs),
# so DictField(child=…) is the right DRF primitive here — a nested
# Serializer with fixed keys would not fit.
# =============================================================================


class _ByLevelDepartmentRefSerializer(serializers.Serializer):
    """
    Compact Department reference embedded inside a DEPARTMENT bucket.

    Produced by SignalClusterService._aggregate_by_level as
    {'id': <uuid>, 'name': <display-label>}.
    """
    id   = serializers.CharField()
    name = serializers.CharField()


class _ByLevelContactRefSerializer(serializers.Serializer):
    """
    Compact Contact reference embedded inside a PERSONAL bucket.

    Produced by SignalClusterService._aggregate_by_level.
    job_title is allowed to be null for contacts without one.
    """
    id         = serializers.CharField()
    first_name = serializers.CharField(allow_null=True, allow_blank=True)
    last_name  = serializers.CharField(allow_null=True, allow_blank=True)
    job_title  = serializers.CharField(allow_null=True, allow_blank=True)


class _ByLevelBusinessEntrySerializer(serializers.Serializer):
    """
    BUSINESS bucket payload — always present, even with zero impacts.

    Shape: { impact_count, parent_pain_ids: [<pain_uuid>, ...] }.
    """
    impact_count    = serializers.IntegerField()
    parent_pain_ids = serializers.ListField(child=serializers.CharField())


class _ByLevelDepartmentEntrySerializer(serializers.Serializer):
    """
    One DEPARTMENT bucket entry — one entry per impacted department.

    Shape:
      {
        impact_count,
        parent_pain_ids: [<pain_uuid>, ...],
        department: {id, name},
      }
    """
    impact_count    = serializers.IntegerField()
    parent_pain_ids = serializers.ListField(child=serializers.CharField())
    department      = _ByLevelDepartmentRefSerializer()


class _ByLevelPersonalEntrySerializer(serializers.Serializer):
    """
    One PERSONAL bucket entry — one entry per impacted contact.

    Shape:
      {
        impact_count,
        parent_pain_ids: [<pain_uuid>, ...],
        contact: {id, first_name, last_name, job_title},
      }
    """
    impact_count    = serializers.IntegerField()
    parent_pain_ids = serializers.ListField(child=serializers.CharField())
    contact         = _ByLevelContactRefSerializer()


class _ByLevelSerializer(serializers.Serializer):
    """
    Top-level `by_level` payload — per-ScopeLevel breakdown of the
    cluster's VALIDATED PainImpacts.

    Keys:
      BUSINESS   — single entry (always present, may be zero).
      DEPARTMENT — dict keyed by <department_uuid>.
      PERSONAL   — dict keyed by <contact_uuid>.

    See SignalClusterService._aggregate_by_level for the generator
    docstring and the semantics of `parent_pain_ids`.
    """
    BUSINESS   = _ByLevelBusinessEntrySerializer()
    DEPARTMENT = serializers.DictField(
        child=_ByLevelDepartmentEntrySerializer(),
    )
    PERSONAL   = serializers.DictField(
        child=_ByLevelPersonalEntrySerializer(),
    )


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

    Type-specific fields
    --------------------
    Some fields are only meaningful for one signal type but always emitted
    by the service for shape symmetry:
      - Pain-specific:      human_impacts, metrics, max_impact_level,
                            impacted_contacts_count
      - Objective-specific: max_scope_level, target_dates,
                            has_target_date_soon
    Cross-type clusters carry neutral values (empty list, null, false, 0)
    for the fields that don't apply to them. The unified cluster UI reads
    these neutral values without needing to branch on signal_type.
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

    # --- Pain-specific impact aggregation ---
    # Always present in the payload. Empty / null for non-Pain clusters.
    human_impacts    = _HumanImpactEntrySerializer(many=True)
    metrics          = serializers.ListField(child=serializers.CharField())
    max_impact_level = serializers.CharField(allow_null=True)

    # --- Objective-specific aggregation  ---
    # Always present in the payload. Empty / null / false for non-Objective
    # clusters.
    #
    # max_scope_level      — highest ScopeLevel observed across VALIDATED
    #                        Objective members (BUSINESS / DEPARTMENT /
    #                        PERSONAL). Drives the scope chip on the
    #                        Objective cluster card.
    # target_dates         — sorted ISO yyyy-mm-dd list across VALIDATED
    #                        members (duplicates kept — frontend dedupes
    #                        if needed).
    # has_target_date_soon — true if at least one VALIDATED member has a
    #                        target_date within OBJECTIVE_TARGET_DATE_SOON_DAYS
    #                        from today. Used by the priority scorer
    #                        and by the UI urgency badge.
    max_scope_level      = serializers.CharField(allow_null=True)
    target_dates         = serializers.ListField(child=serializers.CharField())
    has_target_date_soon = serializers.BooleanField()

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

    Extends the list payload with:
      - members : full PainSignalDetailSerializer payload, nested
                  impacts included.
      - by_level: per-ScopeLevel breakdown of the cluster's VALIDATED
                  PainImpacts (Wave A enrichment, detail-only).

    Only Pain clusters are rendered today — the `members` field is
    therefore explicitly bound to PainSignalDetailSerializer. Adding
    another cluster type later will require branching on signal_type;
    kept hardcoded for now to avoid premature abstraction.
    """

    members  = PainSignalDetailSerializer(many=True, read_only=True)
    by_level = _ByLevelSerializer(read_only=True)