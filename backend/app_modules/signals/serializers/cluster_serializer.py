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
                (Pain members carry nested impacts — Detail is required)
  objective   → ObjectiveSignalListSerializer
                (no nested entity to drill into; List payload is enough
                 for the cluster member surface)
  tech_stack  → TechStackSignalListSerializer
                (catalog entry + lifecycle stats already on the List
                 payload; Detail would only add corroboration_count
                 which is not consumed by the cluster drawer member
                 cards)

The dispatch lives inside `get_members` as a SerializerMethodField so
the cluster payload stays a plain dict and the routing is centralised
in one place. Adding a new signal type means adding one entry to the
serializer map.

Scope notes
-----------
- Human impacts and metrics are aggregated lists of primitives, not
  nested model instances — no sub-serializer needed.
- by_level (Pain only) and all_observations (TechStack only) are
  independent payloads exposed via SerializerMethodField for
  consistency with members type-aware behaviour.
"""

from rest_framework import serializers

from .pain_serializer import PainSignalDetailSerializer
from .objective_serializer import ObjectiveSignalListSerializer
from .tech_stack_serializer import TechStackSignalListSerializer


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
# NESTED HELPERS — TechStack cluster payload (Sprint TechStack)
# =============================================================================
#
# These serializers type the TechStack-specific structures emitted by
# SignalClusterService._build_techstack_cluster. They are referenced by
# both List and Detail serializers below.
#
# Shape contracts authoritative source: SignalClusterService — these
# serializers mirror the dicts the service produces.
# =============================================================================


class _TechCatalogRefSerializer(serializers.Serializer):
    """
    Compact catalog payload exposed on TechStack cluster identity.

    Produced by _build_techstack_cluster as:
      {
        'id':                    <uuid_str>,
        'company_name':          <str>,
        'product_name':          <str>,
        'is_competitor':         <bool>,
        'is_integration_target': <bool>,
      }

    Emitted as None on Pain / Objective clusters (TechStack-compat key).
    """
    id                    = serializers.CharField()
    company_name          = serializers.CharField()
    product_name          = serializers.CharField()
    is_competitor         = serializers.BooleanField()
    is_integration_target = serializers.BooleanField()


class _TechStackLifecycleSerializer(serializers.Serializer):
    """
    Consolidated lifecycle stats for a TechStack cluster.

    Produced by _consolidate_techstack_lifecycle. All fields nullable
    except is_discontinued (BooleanField, default False).

    Field semantics:
      - usage_start_year:  EARLIEST observed value (when did the
                            account START using this tool)
      - renewal_date:      LATEST observation that set the field
                            (most recent rep update is truth)
      - cost_description:  LATEST observation that set the field
      - is_discontinued:   value of the most recent observation
      - discontinued_date: LATEST observation that set the field

    Emitted with all neutral values on Pain / Objective clusters
    (TechStack-compat key).
    """
    usage_start_year  = serializers.IntegerField(allow_null=True)
    renewal_date      = serializers.CharField(allow_null=True, allow_blank=True)
    cost_description  = serializers.CharField(allow_null=True, allow_blank=True)
    is_discontinued   = serializers.BooleanField()
    discontinued_date = serializers.CharField(allow_null=True, allow_blank=True)


class _TechStackDepartmentRefSerializer(serializers.Serializer):
    """
    Compact department reference inside scope_summary.departments_using.

    Produced by _compute_techstack_scope_summary.
    """
    id   = serializers.CharField()
    name = serializers.CharField()


class _TechStackScopeSummarySerializer(serializers.Serializer):
    """
    Scope summary for a TechStack cluster.

    Produced by _compute_techstack_scope_summary. Drives the
    "Used company-wide" / "Used by Sales, Marketing" UI labels.

    Emitted with all neutral values on Pain / Objective clusters.
    """
    is_company_wide   = serializers.BooleanField()
    departments_using = _TechStackDepartmentRefSerializer(many=True)
    summary_text      = serializers.CharField(allow_null=True, allow_blank=True)


class _RelatedPainClusterRefSerializer(serializers.Serializer):
    """
    One Pain cluster cross-reference inside related_pain_clusters.

    Produced by _compute_related_pain_clusters as:
      {
        'canonical_key':       'pain:TECH:TIME',
        'summary':             <str>,
        'confirmation_count':  <int>,
      }

    Note: priority_bucket is intentionally NOT included. Computing it
    would require loading PainImpacts for every cross-referenced Pain
    cluster, which would multiply query cost on TechStack listing.
    Frontend can fetch the full Pain cluster detail via
    /clusters/<canonical_key>/?signal_type=pain when bucket is needed.
    """
    canonical_key      = serializers.CharField()
    summary            = serializers.CharField(allow_null=True, allow_blank=True)
    confirmation_count = serializers.IntegerField()


# =============================================================================
# NESTED HELPER — TechStack lifecycle observation (detail drill-down)
# =============================================================================
#
# `all_observations` is a dict keyed by lifecycle field name, each value
# a list of observation entries. The exact shape per entry depends on
# the field's Python type (int / date / str / bool), so we use a single
# generic entry serializer with a `value` field typed loosely.
#
# Detail-only — list responses do not include all_observations.
# =============================================================================


class _TechStackObservationEntrySerializer(serializers.Serializer):
    """
    One observation entry inside a per-field list of `all_observations`.

    Shape (produced by _compute_techstack_lifecycle_observations):
      {
        'value':              <int | str | bool>,  # field-type-dependent
        'signal_id':          <uuid_str>,
        'source_activity_id': <uuid_str | None>,
        'observed_at':        <ISO-datetime str>,
      }

    `value` is intentionally untyped (JSONField) — different lifecycle
    fields carry different scalar types:
      - usage_start_year   : int
      - renewal_date       : ISO-date str
      - cost_description   : str
      - is_discontinued    : bool
      - discontinued_date  : ISO-date str

    Forcing a single Python type would either lose information (e.g.
    serialising 2019 as the string "2019") or force a dict-of-lists
    with N×5 declared serializers. The JSONField passthrough is the
    right primitive here.
    """
    value              = serializers.JSONField()
    signal_id          = serializers.CharField()
    source_activity_id = serializers.CharField(allow_null=True, allow_blank=True)
    observed_at        = serializers.CharField()


class _TechStackAllObservationsSerializer(serializers.Serializer):
    """
    Detail-only drill-down: per-lifecycle-field observation lists for a
    TechStack cluster.

    Keys mirror the `lifecycle` consolidated dict: each field's
    aggregated value is backed by a list of every VALIDATED observation
    that set it, ordered by `observed_at` DESC.

    Frontend usage: render the consolidated value (from `lifecycle`) as
    the headline, with an "n other observations" affordance that drills
    into the matching key here.
    """
    usage_start_year  = _TechStackObservationEntrySerializer(many=True)
    renewal_date      = _TechStackObservationEntrySerializer(many=True)
    cost_description  = _TechStackObservationEntrySerializer(many=True)
    is_discontinued   = _TechStackObservationEntrySerializer(many=True)
    discontinued_date = _TechStackObservationEntrySerializer(many=True)

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

    # --- TechStack-specific aggregation (Sprint TechStack) ---
    # Always present in the payload across all signal types — populated
    # for TechStack clusters, neutral / null on Pain and Objective. The
    # unified cluster UI reads these without needing to branch on
    # signal_type.
    #
    # tech_catalog_entry      — compact catalog reference (TechStack only)
    # lifecycle               — consolidated lifecycle stats (TechStack only,
    #                           neutral defaults elsewhere)
    # scope_summary           — usage scope narrative (TechStack only,
    #                           neutral defaults elsewhere)
    # has_renewal_soon        — true if a contract renewal falls within
    #                           TECHSTACK_RENEWAL_SOON_DAYS (TechStack only,
    #                           false elsewhere)
    # related_pain_clusters   — Pain clusters cross-referencing this catalog
    #                           entry on the same account (TechStack only,
    #                           empty list elsewhere)
    #
    # Defensive `required=False` + neutral `default=...`: cluster dicts
    # may omit these keys entirely when produced by older code paths or
    # cached fragments (e.g. clusters built before TechStack joined the
    # unified payload contract). The serializer stays tolerant to such
    # shape drift to avoid 500s during transitions.
    tech_catalog_entry    = _TechCatalogRefSerializer(
        allow_null=True, required=False, default=None,
    )
    lifecycle             = _TechStackLifecycleSerializer(
        required=False, default=None, allow_null=True,
    )
    scope_summary         = _TechStackScopeSummarySerializer(
        required=False, default=None, allow_null=True,
    )
    has_renewal_soon      = serializers.BooleanField(
        required=False, default=False,
    )
    related_pain_clusters = _RelatedPainClusterRefSerializer(
        many=True, required=False, default=list,
    )


# =============================================================================
# DETAIL SERIALIZER
# =============================================================================

class SignalClusterDetailSerializer(SignalClusterListSerializer):
    """
    Output serializer for the cluster detail endpoint.

    Extends the list payload with three type-aware fields, each rendered
    only when relevant:

      - members          : member signal instances, type-dispatched
                           based on cluster.signal_type. See the
                           module-level docstring for the dispatch map.
      - by_level         : per-ScopeLevel breakdown of the cluster's
                           VALIDATED PainImpacts. Only meaningful for
                           Pain clusters; emitted as None on Objective
                           and TechStack.
      - all_observations : per-lifecycle-field observation lists. Only
                           meaningful for TechStack clusters; emitted
                           as None on Pain and Objective.

    Each of the three fields is a SerializerMethodField so the routing
    stays explicit and type-safe. Adding a new signal type to members
    rendering is a one-line addition to _MEMBER_SERIALIZER_MAP.

    Sprint TechStack — fix
    ----------------------
    Before this fix, members was hardcoded on PainSignalDetailSerializer.
    The cluster Detail endpoint therefore returned 500 for Objective and
    TechStack clusters whose members couldn't be serialised by a Pain
    serializer (different field set; AttributeError on `obj.what`,
    `obj.summary`, etc.). The dispatch below restores per-type rendering.
    """

    members          = serializers.SerializerMethodField()
    by_level         = serializers.SerializerMethodField()
    all_observations = serializers.SerializerMethodField()

    # -------------------------------------------------------------------------
    # MEMBER DISPATCH MAP
    # -------------------------------------------------------------------------
    #
    # Map cluster signal_type → concrete serializer for member rendering.
    # Lazy-resolved at call time inside get_members to keep the import
    # graph minimal at module load.
    #
    # Pain uses Detail because PainCard needs nested impacts — those
    # only ship in the Detail payload. Objective and TechStack use List
    # since their cluster member cards do not consume the heavier
    # Detail-only fields (corroboration_count, audit users, etc.).
    @staticmethod
    def _get_member_serializer_class(signal_type):
        if signal_type == 'pain':
            return PainSignalDetailSerializer
        if signal_type == 'objective':
            return ObjectiveSignalListSerializer
        if signal_type == 'tech_stack':
            return TechStackSignalListSerializer
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
        (PainSignal / ObjectiveSignal / TechStackSignal) — never a mix.
        """
        members = cluster.get('members', []) or []
        signal_type = cluster.get('signal_type')
        serializer_class = self._get_member_serializer_class(signal_type)
        return serializer_class(
            members,
            many=True,
            context=self.context,
        ).data

    def get_by_level(self, cluster):
        """
        Pain-only: per-ScopeLevel breakdown.

        Returns None for non-Pain clusters and for Pain clusters that
        do not carry the breakdown (defensive — the service does emit
        the key, but malformed cached fragments can drift).
        """
        if cluster.get('signal_type') != 'pain':
            return None
        by_level = cluster.get('by_level')
        if not by_level:
            return None
        return _ByLevelSerializer(by_level, context=self.context).data

    def get_all_observations(self, cluster):
        """
        TechStack-only: per-lifecycle-field observation lists.

        Returns None for non-TechStack clusters and for TechStack
        clusters that do not carry the observation map.
        """
        if cluster.get('signal_type') != 'tech_stack':
            return None
        all_obs = cluster.get('all_observations')
        if not all_obs:
            return None
        return _TechStackAllObservationsSerializer(
            all_obs, context=self.context,
        ).data