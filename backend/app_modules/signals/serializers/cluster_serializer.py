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
  SignalClusterDetailSerializer — adds the 'members' field with full
                                   per-type detail
                                   (used by the /clusters/{key}/ endpoint)

Member serialization — type dispatch
------------------------------------
`members` is type-dispatched: the concrete serializer used for each
member is selected based on the cluster's signal_type:

  pain        → PainSignalDetailSerializer
  objective   → ObjectiveSignalListSerializer
  impact      → ImpactSignalListSerializer

The dispatch lives inside `get_members` as a SerializerMethodField so
the cluster payload stays a plain dict and the routing is centralised
in one place. Adding a new signal type means adding one entry to the
serializer map.

Standardised provenance block on members
----------------------------------------
Every member (regardless of signal_type) exposes the standardised
`source_context` block, inherited automatically through
BaseSignalListSerializer / BaseSignalDetailSerializer. The block
carries: activity (compact), contacts (list), decision_cycle,
campaign, decision_step.

Performance note: SignalClusterService fetchers
(_fetch_pain_signals, _fetch_objective_signals, _fetch_impact_signals)
include `prefetch_related('source_activity__contacts')` and
`select_related('source_activity')` to avoid N+1 query loops when the
source_context block is rendered.
"""

from rest_framework import serializers

from .pain_serializer import PainSignalDetailSerializer
from .objective_serializer import ObjectiveSignalListSerializer
from .impact_serializer import ImpactSignalListSerializer


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

    # --- Status ---
    status              = serializers.CharField()
    has_pending_signals = serializers.BooleanField()
    pending_count       = serializers.IntegerField()

    # --- Lifecycle ---
    first_observed_at = serializers.DateTimeField(allow_null=True)
    last_confirmed_at = serializers.DateTimeField(allow_null=True)
    freshness_status  = serializers.CharField(allow_null=True)

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
    #
    # Defensive `required=False` + neutral `default=...`: cluster dicts
    # may omit these keys entirely when produced by older code paths or
    # cached fragments. The unified cluster API contract guarantees a
    # uniform shape across signal types, but the serializer must remain
    # tolerant to evolution and avoid 500s on shape drift.
    max_scope_level      = serializers.CharField(
        allow_null=True, required=False, default=None,
    )
    target_dates         = serializers.ListField(
        child=serializers.CharField(), required=False, default=list,
    )
    has_target_date_soon = serializers.BooleanField(
        required=False, default=False,
    )

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

    Extends the list payload with the type-aware `members` field:

      - members : member signal instances, type-dispatched based on
                  cluster.signal_type. See the module-level docstring
                  for the dispatch map.

    `members` is a SerializerMethodField so the routing stays explicit
    and type-safe. Adding a new signal type to member rendering is a
    one-line addition to _get_member_serializer_class.
    """

    members = serializers.SerializerMethodField()

    # -------------------------------------------------------------------------
    # MEMBER DISPATCH
    # -------------------------------------------------------------------------
    #
    # Map cluster signal_type → concrete serializer for member rendering.
    # Lazy-resolved at call time inside get_members to keep the import
    # graph minimal at module load.
    #
    # Pain uses Detail to expose validated_at / validated_by /
    # requested_by / source_quote / metadata / original_value on cluster
    # member cards. Objective and Impact use List since their cluster
    # member cards do not consume those extras.
    @staticmethod
    def _get_member_serializer_class(signal_type):
        if signal_type == 'pain':
            return PainSignalDetailSerializer
        if signal_type == 'objective':
            return ObjectiveSignalListSerializer
        if signal_type == 'impact':
            return ImpactSignalListSerializer
        # Unknown type — fall back to Pain Detail to mirror the prior
        # implicit default. The shape mismatch will surface at
        # serialisation time as an AttributeError, with a clear stack
        # trace pointing to the unhandled signal_type.
        return PainSignalDetailSerializer

    # -------------------------------------------------------------------------
    # METHOD FIELDS
    # -------------------------------------------------------------------------

    def get_members(self, cluster):
        """
        Render the cluster's member signals through the type-appropriate
        serializer.

        cluster is a dict produced by SignalClusterService.get_cluster_detail.
        Its `members` key holds a list of concrete signal instances
        (PainSignal / ObjectiveSignal / ImpactSignal) — never a mix.
        """
        members = cluster.get('members', []) or []
        signal_type = cluster.get('signal_type')
        serializer_class = self._get_member_serializer_class(signal_type)
        return serializer_class(
            members,
            many=True,
            context=self.context,
        ).data
