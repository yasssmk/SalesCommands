# app_modules/signals/services/signal_cluster_service.py
"""
SignalClusterService — aggregate signals into canonical clusters.

A cluster is the set of signals sharing the same canonical_key on a
given account. The canonical_key format depends on the signal type:

    Pain        — "pain:<SignalWhat>:<SignalDimension>"
    Objective   — "objective:<SignalWhat>:<SignalDimension>"
    Impact      — "impact:<SignalWhat>:<SignalDimension>"
    TechStack   — "techstack:<TechCatalog.id>"

A Pain cluster corresponds to a distinct pain diagnosis at an account,
regardless of which contact reported it or when. The same logic
applies to Objective, Impact, and TechStack on their respective
canonical identities.

Pain, Objective, and Impact share the same canonical-axes mechanism
(what × dimension). A cluster identified by (what, dimension) on an
account can therefore have three parallel cluster perspectives — Pain
(the diagnosis), Objective (the target), and Impact (the proof). The
three perspectives are stored, scored, and rendered independently;
cross-perspective consolidation (e.g. "show me everything happening
at OPS × TIME") is a frontend concern, not a service one.

Supported signal types
----------------------
list_clusters_for_account accepts either a single signal_type string
or a list. Pain, Objective, Impact, and TechStack all produce real
clusters today. Any other signal_type value is rejected by the guard
as "not supported".

What the service does
---------------------
  1. Loads concrete signals for an account (VALIDATED + PENDING;
     REJECTED excluded entirely).
  2. Groups them by canonical_key.
  3. For each group, computes consolidated stats:
       - confirmation_count    (VALIDATED members only)
       - distinct_contacts_count (derived from
                                  source_activity.contacts m2m)
       - type-specific aggregations
         (Pain:      max_scope_level
          Objective: max_scope_level + target dates
          Impact:    max_scope_level
          TechStack: lifecycle + scope_summary + renewal proximity)
  4. Computes lifecycle (first_observed_at, last_confirmed_at,
     freshness_status) with the active-DC exception (a cluster on
     an open decision cycle is never STALE — clamped to DORMANT).
  5. Derives cluster status (VALIDATED | PENDING + has_pending_signals
     + pending_count).
  6. Delegates priority scoring to signal_priority_service.
  7. Marks clusters as archived by cross-referencing
     SignalClusterArchival.
  8. Optionally filters the cluster list to a specific decision_cycle.

What the service does NOT do
----------------------------
  - It does not write anything.
  - It does not paginate (acceptable for <100 clusters per account).
  - It does not cache — callers are responsible for any caching layer.

Output shape
------------
list_clusters_for_account returns a list of dicts. get_cluster_detail
returns the same dict structure plus a 'members' key with the raw
concrete signal instances (the serializer is responsible for turning
those into JSON).

Each cluster dict contains:

    {
        # Identity
        'canonical_key':        'pain:OPS:TIME',
        'signal_type':          'pain' | 'objective' | 'impact' | 'tech_stack',
        'what':                 'OPS',     # null on TechStack
        'what_display':         'Operations / Process',
        'dimension':            'TIME',    # null on TechStack
        'dimension_display':    'Time / Speed',
        'summary':              '...',     # consolidated summary

        # Corroboration & breadth
        'confirmation_count':      2,
        'distinct_contacts_count': 2,

        # Status
        'status':               'VALIDATED' | 'PENDING',
        'has_pending_signals':  True,
        'pending_count':        1,

        # Lifecycle
        'first_observed_at':    datetime | None,
        'last_confirmed_at':    datetime | None,
        'freshness_status':     'FRESH' | 'DORMANT' | 'STALE' | None,

        # Objective-specific (neutral defaults on other types)
        'max_scope_level':       'BUSINESS' | ... | None,
        'target_dates':          [<iso-date>, ...],
        'has_target_date_soon':  bool,

        # TechStack-specific (neutral defaults on other types)
        'tech_catalog_entry':    {...} | None,
        'lifecycle':             {...} | None,
        'scope_summary':         {...} | None,
        'has_renewal_soon':      bool,
        'related_pain_clusters': [{...}, ...],

        # Priority
        'priority_score':   85,
        'priority_bucket':  'HIGH',

        # Linking
        'decision_cycle_ids':  [uuid, ...],
        'campaign_ids':        [uuid, ...],

        # Archival
        'is_archived':      False,
    }
"""

from collections import defaultdict
from datetime import timedelta

from django.db.models import Prefetch
from django.utils import timezone

from app_modules.decision_cycles.constants import CycleOutcome, TERMINAL_OUTCOMES
from core.error_messages import SignalErrorMessages
from core.exceptions import StandardizedValidationError

from ..constants import (
    FreshnessStatus,
    FRESHNESS_FRESH_DAYS,
    FRESHNESS_DORMANT_DAYS,
    ScopeLevel,
    SignalClusterType,
    SignalStatus,
)
from ..models import ImpactSignal, ObjectiveSignal, PainSignal, SignalClusterArchival, TechStackSignal
from .signal_priority_service import (
    OBJECTIVE_TARGET_DATE_SOON_DAYS,
    bucket_from_score,
    compute_impact_priority_score,
    compute_objective_priority_score,
    compute_pain_priority_score,
    compute_techstack_priority_score,
)

# Ordering used to determine the "max observed" scope level on a cluster.
# BUSINESS > DEPARTMENT > PERSONAL — the strongest evidence wins.
# Used by Pain, Objective, and Impact cluster builders to compute
# max_scope_level across the cluster's VALIDATED members.
_SCOPE_LEVEL_RANK = {
    ScopeLevel.PERSONAL:   1,
    ScopeLevel.DEPARTMENT: 2,
    ScopeLevel.BUSINESS:   3,
}


class SignalClusterService:
    """
    Stateless read service for signal cluster aggregation.

    All public methods are classmethods — no instance required.
    No writes, no caching. Callers (views, serializers) are responsible
    for any caching layer.
    """

    # =========================================================================
    # PUBLIC — LIST
    # =========================================================================

    @classmethod
    def list_clusters_for_account(
        cls,
        account_id,
        signal_type=SignalClusterType.PAIN,
        *,
        decision_cycle_id=None,
        include_archived: bool = False,
    ) -> list:
        """
        Return all clusters for an account, grouped by canonical_key.

        Args:
            account_id:         UUID of the account.
            signal_type:        Cluster signal type — accepts either a
                                single string ('pain' / 'objective' /
                                'impact' / 'tech_stack') or a list/tuple
                                of strings for mixed queries.
            decision_cycle_id:  Optional UUID. When provided, only clusters
                                having at least one member signal linked
                                to that decision cycle are returned.
            include_archived:   When False (default), archived clusters
                                are excluded from the result. When True,
                                archived clusters are returned with
                                is_archived=True.

        Returns:
            List of cluster dicts, sorted by priority_score DESC. Ties
            are broken by the most recent confirmation so equally-scored
            clusters surface the freshest first.

        Raises:
            StandardizedValidationError if any requested signal_type is
            not in the supported set.
        """
        requested_types = cls._assert_signal_types_supported(signal_type)

        clusters: list = []

        for stype in requested_types:
            if stype == SignalClusterType.PAIN:
                clusters.extend(
                    cls._list_pain_clusters_for_account(
                        account_id=account_id,
                        decision_cycle_id=decision_cycle_id,
                        include_archived=include_archived,
                    )
                )
                continue
            if stype == SignalClusterType.OBJECTIVE:
                clusters.extend(
                    cls._list_objective_clusters_for_account(
                        account_id=account_id,
                        decision_cycle_id=decision_cycle_id,
                        include_archived=include_archived,
                    )
                )
                continue
            if stype == SignalClusterType.IMPACT:
                clusters.extend(
                    cls._list_impact_clusters_for_account(
                        account_id=account_id,
                        decision_cycle_id=decision_cycle_id,
                        include_archived=include_archived,
                    )
                )
                continue
            if stype == SignalClusterType.TECH_STACK:
                clusters.extend(
                    cls._list_techstack_clusters_for_account(
                        account_id=account_id,
                        decision_cycle_id=decision_cycle_id,
                        include_archived=include_archived,
                    )
                )
                continue
            # _assert_signal_types_supported guarantees no other type
            # reaches this loop — the guard is the single source of truth.

        # Sort by priority score, descending. Ties are broken by most
        # recent confirmation so equally-scored clusters surface the
        # freshest first.
        clusters.sort(
            key=lambda c: (
                c['priority_score'],
                c['last_confirmed_at'] or timezone.datetime.min,
            ),
            reverse=True,
        )
        return clusters

    # -------------------------------------------------------------------------
    # INTERNAL — Pain-specific listing
    # -------------------------------------------------------------------------

    @classmethod
    def _list_pain_clusters_for_account(
        cls,
        *,
        account_id,
        decision_cycle_id=None,
        include_archived: bool = False,
    ) -> list:
        """
        Pain-specific cluster computation for list_clusters_for_account.

        Factored out so the top-level dispatch loop stays readable and
        future signal types can plug in via their own
        _list_*_clusters_for_account helper without touching the Pain
        logic.
        """
        signals = cls._fetch_pain_signals(
            account_id=account_id,
            decision_cycle_id=decision_cycle_id,
        )
        grouped = cls._group_by_canonical_key(signals)

        archived_keys = cls._get_archived_keys(
            account_id,
            SignalClusterType.PAIN,
        )

        clusters: list = []
        for canonical_key, members in grouped.items():
            if canonical_key is None:
                # Signals without a canonical_key cannot form a cluster —
                # defensive skip (should not occur for Pain since save()
                # always computes it, but safe for future signal types).
                continue

            cluster = cls._build_pain_cluster(canonical_key, members)
            cluster['is_archived'] = canonical_key in archived_keys

            if cluster['is_archived'] and not include_archived:
                continue

            clusters.append(cluster)

        return clusters

    # -------------------------------------------------------------------------
    # INTERNAL — Objective-specific listing
    # -------------------------------------------------------------------------

    @classmethod
    def _list_objective_clusters_for_account(
        cls,
        *,
        account_id,
        decision_cycle_id=None,
        include_archived: bool = False,
    ) -> list:
        """
        Objective-specific cluster computation for list_clusters_for_account.

        Mirror of _list_pain_clusters_for_account scoped to
        ObjectiveSignal. The cluster shape adds target-date stats
        (target_dates, has_target_date_soon) on top of the common
        canonical-axes payload.
        """
        signals = cls._fetch_objective_signals(
            account_id=account_id,
            decision_cycle_id=decision_cycle_id,
        )
        grouped = cls._group_by_canonical_key(signals)

        archived_keys = cls._get_archived_keys(
            account_id,
            SignalClusterType.OBJECTIVE,
        )

        clusters: list = []
        for canonical_key, members in grouped.items():
            if canonical_key is None:
                # Signals without a canonical_key cannot form a cluster.
                # Defensive skip — ObjectiveSignal.save() always computes
                # canonical_key when both what and dimension are set, and
                # both are required fields on the model.
                continue

            cluster = cls._build_objective_cluster(canonical_key, members)
            cluster['is_archived'] = canonical_key in archived_keys

            if cluster['is_archived'] and not include_archived:
                continue

            clusters.append(cluster)

        return clusters

    # -------------------------------------------------------------------------
    # INTERNAL — Impact-specific listing
    # -------------------------------------------------------------------------

    @classmethod
    def _list_impact_clusters_for_account(
        cls,
        *,
        account_id,
        decision_cycle_id=None,
        include_archived: bool = False,
    ) -> list:
        """
        Impact-specific cluster computation for list_clusters_for_account.

        Mirror of _list_objective_clusters_for_account. ImpactSignal
        shares the same canonical-axes mechanism (what × dimension) as
        Pain and Objective, with scope_level as a direct field on the
        model. ImpactSignal carries no target_date concept — the
        Impact cluster shape mirrors Objective's minus target-date
        aggregation.
        """
        signals = cls._fetch_impact_signals(
            account_id=account_id,
            decision_cycle_id=decision_cycle_id,
        )
        grouped = cls._group_by_canonical_key(signals)

        archived_keys = cls._get_archived_keys(
            account_id,
            SignalClusterType.IMPACT,
        )

        clusters: list = []
        for canonical_key, members in grouped.items():
            if canonical_key is None:
                # Defensive skip — ImpactSignal.save() always computes
                # canonical_key when both what and dimension are set,
                # and both are required fields on the model.
                continue

            cluster = cls._build_impact_cluster(canonical_key, members)
            cluster['is_archived'] = canonical_key in archived_keys

            if cluster['is_archived'] and not include_archived:
                continue

            clusters.append(cluster)

        return clusters

    # -------------------------------------------------------------------------
    # INTERNAL — TechStack-specific listing
    # -------------------------------------------------------------------------

    @classmethod
    def _list_techstack_clusters_for_account(
        cls,
        *,
        account_id,
        decision_cycle_id=None,
        include_archived: bool = False,
    ) -> list:
        """
        TechStack-specific cluster computation for list_clusters_for_account.

        Mirror of _list_pain_clusters_for_account / _list_objective_clusters_for_account
        but scoped to TechStackSignal.

        decision_cycle_id filter
        ------------------------
        TechStackSignal has no direct decision_cycle FK — the field is
        shadow-overridden because a tool's existence at an account is
        account-level intelligence, not deal-level. However, the deal
        context can be inferred via the source Activity, which carries
        its own decision_cycle FK.

        When decision_cycle_id is provided, this method filters signals
        where source_activity.decision_cycle matches. Signals with no
        source_activity are excluded from the DC-filtered result — see
        _fetch_techstack_signals docstring for the SQL semantics.

        Behaviour: a cluster appears in the DC-filtered list as long as
        AT LEAST ONE of its observations was captured in that DC's
        context. The cluster identity itself remains
        canonical_key="techstack:<catalog_id>" — a tool is account-level,
        not deal-level.
        """
        signals = cls._fetch_techstack_signals(
            account_id=account_id,
            decision_cycle_id=decision_cycle_id,
        )
        grouped = cls._group_by_canonical_key(signals)

        archived_keys = cls._get_archived_keys(
            account_id,
            SignalClusterType.TECH_STACK,
        )

        clusters: list = []
        for canonical_key, members in grouped.items():
            if canonical_key is None:
                # Signals without a canonical_key cannot form a cluster.
                # Defensive skip — TechStackSignal.save() always computes
                # canonical_key when tech_catalog_entry is set, and the
                # FK is required at the model level.
                continue

            cluster = cls._build_techstack_cluster(canonical_key, members)
            cluster['is_archived'] = canonical_key in archived_keys

            if cluster['is_archived'] and not include_archived:
                continue

            clusters.append(cluster)

        return clusters

    # =========================================================================
    # PUBLIC — DETAIL
    # =========================================================================

    @classmethod
    def get_cluster_detail(
        cls,
        account_id,
        canonical_key: str,
        signal_type: str = SignalClusterType.PAIN,
    ) -> dict:
        """
        Return a single cluster with its member signals.

        The cluster dict has the same shape as in list_clusters_for_account
        plus:
          - `members`: concrete signal instances (Pain / Objective /
                       Impact / TechStack) — turned into JSON by the
                       calling serializer.

        TechStack additionally carries `all_observations` — a per-field
        observation drill-down — see _compute_techstack_lifecycle_observations.

        Args:
            account_id:     UUID of the account.
            canonical_key:  Cluster identifier (e.g. 'pain:OPS:TIME').
            signal_type:    Cluster signal type — single string
                            ('pain', 'objective', 'impact', or
                            'tech_stack').

        Returns:
            Cluster dict with `members` key.

        Raises:
            StandardizedValidationError if signal_type is unsupported,
            or if no signals exist for the given (account, canonical_key).
        """

        # A detail is always one cluster → one signal_type. We reuse the
        # generic supported-types guard but insist on a single value here.
        normalised = cls._assert_signal_types_supported(signal_type)
        if len(normalised) != 1:
            # Defensive — the caller should never send a list to detail.
            raise StandardizedValidationError(
                SignalErrorMessages.CLUSTER_SIGNAL_TYPE_INVALID.format(
                    signal_type=signal_type,
                )
            )
        resolved_type = normalised[0]

        if not canonical_key:
            raise StandardizedValidationError(
                SignalErrorMessages.CLUSTER_CANONICAL_KEY_REQUIRED
            )

        # Dispatch per signal type. Pain, Objective, Impact, and
        # TechStack all produce real cluster detail payloads.
        if resolved_type == SignalClusterType.PAIN:
            members = list(
                cls._fetch_pain_signals(account_id=account_id)
                .filter(canonical_key=canonical_key)
            )

            if not members:
                raise StandardizedValidationError(
                    SignalErrorMessages.CLUSTER_NOT_FOUND
                )

            cluster = cls._build_pain_cluster(canonical_key, members)

            archived_keys = cls._get_archived_keys(account_id, resolved_type)
            cluster['is_archived'] = canonical_key in archived_keys
            cluster['members'] = members

            return cluster

        if resolved_type == SignalClusterType.OBJECTIVE:
            members = list(
                cls._fetch_objective_signals(account_id=account_id)
                .filter(canonical_key=canonical_key)
            )

            if not members:
                raise StandardizedValidationError(
                    SignalErrorMessages.CLUSTER_NOT_FOUND
                )

            cluster = cls._build_objective_cluster(canonical_key, members)

            archived_keys = cls._get_archived_keys(account_id, resolved_type)
            cluster['is_archived'] = canonical_key in archived_keys
            cluster['members'] = members

            return cluster

        if resolved_type == SignalClusterType.IMPACT:
            members = list(
                cls._fetch_impact_signals(account_id=account_id)
                .filter(canonical_key=canonical_key)
            )

            if not members:
                raise StandardizedValidationError(
                    SignalErrorMessages.CLUSTER_NOT_FOUND
                )

            cluster = cls._build_impact_cluster(canonical_key, members)

            archived_keys = cls._get_archived_keys(account_id, resolved_type)
            cluster['is_archived'] = canonical_key in archived_keys
            cluster['members'] = members

            return cluster

        if resolved_type == SignalClusterType.TECH_STACK:
            members = list(
                cls._fetch_techstack_signals(account_id=account_id)
                .filter(canonical_key=canonical_key)
            )

            if not members:
                raise StandardizedValidationError(
                    SignalErrorMessages.CLUSTER_NOT_FOUND
                )

            cluster = cls._build_techstack_cluster(canonical_key, members)

            archived_keys = cls._get_archived_keys(account_id, resolved_type)
            cluster['is_archived'] = canonical_key in archived_keys
            cluster['members'] = members

            # TechStack-specific drill-down: per-field observation lists
            # exposed under `all_observations`, computed from VALIDATED
            # members only (consistent with Pain/Objective/Impact). See
            # _compute_techstack_lifecycle_observations for the shape.
            validated_members = [
                m for m in members if m.status == SignalStatus.VALIDATED
            ]
            cluster['all_observations'] = (
                cls._compute_techstack_lifecycle_observations(validated_members)
            )

            return cluster

        # _assert_signal_types_supported guarantees we never reach here.

    # =========================================================================
    # GUARD
    # =========================================================================

    # Signal types the cluster service currently accepts at its API
    # surface. Pain, Objective, and Impact share the same canonical-
    # axes mechanism (what × dimension); TechStack follows a distinct
    # canonical pattern (canonical_key = "techstack:<catalog_entry_id>")
    # anchored to the tenant tech catalog rather than the (what,
    # dimension) pair.
    _SUPPORTED_CLUSTER_TYPES = frozenset({
        SignalClusterType.PAIN.value,
        SignalClusterType.OBJECTIVE.value,
        SignalClusterType.IMPACT.value,
        SignalClusterType.TECH_STACK.value,
    })

    @classmethod
    def _assert_signal_types_supported(cls, signal_type) -> list:
        """
        Normalise a signal_type input to a list of supported type values.

        Accepts:
          - a single string / SignalClusterType member
          - a list / tuple of strings

        Rejects anything outside _SUPPORTED_CLUSTER_TYPES with a single
        StandardizedValidationError identifying the first offending
        value. The guard is intentionally strict — silently dropping
        unknown types would make API mistakes invisible.

        Returns:
            A list of supported type values in the caller's order,
            deduplicated while preserving order (useful when a caller
            passes the same type twice by accident, e.g.
            ?signal_type=pain,pain).
        """
        # Normalise to list
        if isinstance(signal_type, (list, tuple)):
            requested = list(signal_type)
        else:
            requested = [signal_type]

        # Coerce enum members to their string value for comparison and
        # downstream use (we store string values everywhere in the dicts).
        normalised: list = []
        seen = set()
        for item in requested:
            value = (
                item.value if isinstance(item, SignalClusterType) else item
            )
            if value not in cls._SUPPORTED_CLUSTER_TYPES:
                raise StandardizedValidationError(
                    SignalErrorMessages.CLUSTER_SIGNAL_TYPE_INVALID.format(
                        signal_type=value,
                    )
                )
            if value not in seen:
                seen.add(value)
                normalised.append(value)

        if not normalised:
            # Empty list or None → treat as invalid.
            raise StandardizedValidationError(
                SignalErrorMessages.CLUSTER_SIGNAL_TYPE_INVALID.format(
                    signal_type=signal_type,
                )
            )

        return normalised

    # =========================================================================
    # FETCH
    # =========================================================================

    @classmethod
    def _fetch_pain_signals(cls, *, account_id, decision_cycle_id=None):
        """
        Base queryset for Pain cluster aggregation.

        Includes VALIDATED and PENDING signals (REJECTED excluded as
        per product decision).

        select_related coverage:
          - source_activity  : nested in cluster member payload via
                                PainSignalDetailSerializer; also the
                                join path for distinct_contacts_count
                                (derived from activity.contacts m2m).
          - decision_cycle   : exposed inside the source_context block.
          - campaign         : same.

        prefetch coverage:
          - source_activity.contacts (m2m): used by both
            ActivityCompactSerializer (nested in member detail) and the
            distinct_contacts_count computation in _build_pain_cluster.
        """
        qs = (
            PainSignal.objects
            .filter(
                account_id=account_id,
                status__in=(SignalStatus.VALIDATED, SignalStatus.PENDING),
            )
            .select_related(
                'source_activity',
                'decision_cycle',
                'campaign',
            )
            .prefetch_related(
                'source_activity__contacts',
            )
        )

        if decision_cycle_id:
            qs = qs.filter(decision_cycle_id=decision_cycle_id)

        return qs

    @classmethod
    def _fetch_objective_signals(cls, *, account_id, decision_cycle_id=None):
        """
        Base queryset for Objective cluster aggregation.

        Includes VALIDATED and PENDING signals (REJECTED excluded — same
        product rule as Pain).

        Unlike Pain, Objective has no child relation — scope and target
        are stored directly on the model. The only prefetch needed is
        source_activity.contacts so that ActivityCompactSerializer
        (nested inside each cluster member detail payload) resolves
        without additional queries.
        """
        qs = (
            ObjectiveSignal.objects
            .filter(
                account_id=account_id,
                status__in=(SignalStatus.VALIDATED, SignalStatus.PENDING),
            )
            .select_related(
                # source_activity is the join path for
                # distinct_contacts_count via the activity.contacts m2m.
                'source_activity',
                # Objective-specific FKs (the OWNER of the objective,
                # not the source — distinct concept).
                'target_contact',
                'target_department',
                'decision_cycle',
                'campaign',
            )
            .prefetch_related(
                'source_activity__contacts',
            )
        )

        if decision_cycle_id:
            qs = qs.filter(decision_cycle_id=decision_cycle_id)

        return qs

    @classmethod
    def _fetch_impact_signals(cls, *, account_id, decision_cycle_id=None):
        """
        Base queryset for Impact cluster aggregation.

        Includes VALIDATED and PENDING signals (REJECTED excluded — same
        product rule as Pain / Objective / TechStack).

        ImpactSignal carries no Impact-specific FK (no equivalent to
        Pain's related_techstack, Objective's target_contact /
        target_department, or TechStack's tech_catalog_entry).
        Impact-specific data (impact_type, scope_level, metric_text,
        human_impact) are scalar fields requiring no relational preload.

        select_related coverage:
          - source_activity  : nested in cluster member payload via
                                ImpactSignalListSerializer; also the
                                join path for distinct_contacts_count
                                (derived from activity.contacts m2m).
          - decision_cycle   : exposed inside the source_context block.
          - campaign         : same.

        prefetch coverage:
          - source_activity.contacts (m2m): used by both
            ActivityCompactSerializer (nested in member detail) and the
            distinct_contacts_count computation in _build_impact_cluster.
        """
        qs = (
            ImpactSignal.objects
            .filter(
                account_id=account_id,
                status__in=(SignalStatus.VALIDATED, SignalStatus.PENDING),
            )
            .select_related(
                'source_activity',
                'decision_cycle',
                'campaign',
            )
            .prefetch_related(
                'source_activity__contacts',
            )
        )

        if decision_cycle_id:
            qs = qs.filter(decision_cycle_id=decision_cycle_id)

        return qs

    @classmethod
    def _fetch_techstack_signals(cls, *, account_id, decision_cycle_id=None):
        """
        Base queryset for TechStack cluster aggregation.

        Includes VALIDATED and PENDING signals (REJECTED excluded — same
        product rule as Pain / Objective / Impact).

        Unlike Pain (which previously had a child relation) and Objective
        / Impact (which carry scope/target on the model), TechStack
        signals are flat: every lifecycle field (usage_start_year,
        renewal_date, cost_description, is_discontinued,
        discontinued_date, notes) lives directly on the model. No
        prefetched child relation needed.

        Select_related coverage:
          - tech_catalog_entry  : reference for canonical_key + compact
                                  catalog payload exposed in the cluster
                                  identity (company_name, product_name).
                                  Hot path — every cluster build calls
                                  reference.tech_catalog_entry.
          - usage_department    : exposed in scope_summary aggregation
                                  ("Used by Sales, Marketing"). Often
                                  null but cheap to prefetch.
          - source_activity     : nested in cluster member detail payload
                                  via TechStackSignalDetailSerializer
                                  (mirror of Pain/Objective handling), AND
                                  used as the join path for the
                                  decision_cycle_id filter (see below).

        decision_cycle_id filter
        ------------------------
        TechStackSignal does NOT carry a direct decision_cycle FK — that
        field is shadow-overridden because a tool is account-level, not
        deal-level. However, the deal context can be inferred via the
        source Activity: each Activity carries a decision_cycle FK, so a
        TechStack signal anchored to an activity inherits that activity's
        decision cycle context indirectly.

        When decision_cycle_id is provided, we filter on
        source_activity__decision_cycle_id. Semantics:

          "Return TechStack signals captured during a conversation
           belonging to this decision cycle."

        Signals with source_activity=NULL are EXCLUDED when the filter
        is active (the JOIN condition fails — same behaviour as a SQL
        INNER JOIN through a nullable FK). This is the desired
        behaviour: an externally-researched TechStack signal with no
        activity has no DC context to match on.

        Performance
        -----------
        The traversal goes through Activity.decision_cycle, which is
        indexed via Activity's `act_sequence_order_idx` composite index
        (decision_cycle is the leading column). The added JOIN cost is
        negligible at expected volumes (<100 TechStack signals per
        account).

        Cluster filtering note
        ----------------------
        This filter applies at the SIGNAL level. A cluster is then
        formed from the surviving signals. A cluster therefore appears
        in the DC-filtered list as long as AT LEAST ONE of its
        observations was captured in that DC's context. The cluster
        identity stays canonical_key="techstack:<catalog_id>".
        """
        qs = (
            TechStackSignal.objects
            .filter(
                account_id=account_id,
                status__in=(SignalStatus.VALIDATED, SignalStatus.PENDING),
            )
            .select_related(
                'tech_catalog_entry',
                'usage_department',
                'source_activity',
            )
            .prefetch_related(
                # ActivityCompactSerializer (nested inside each cluster
                # member detail payload) reads source_activity.contacts —
                # prefetch keeps the cluster detail at a bounded query
                # count regardless of member count.
                'source_activity__contacts',
            )
        )

        if decision_cycle_id:
            # Indirect filter via Activity.decision_cycle — see docstring
            # for the semantics. Signals without source_activity are
            # excluded when the filter is active.
            qs = qs.filter(source_activity__decision_cycle_id=decision_cycle_id)

        return qs

    # =========================================================================
    # GROUP
    # =========================================================================

    @staticmethod
    def _group_by_canonical_key(signals) -> dict:
        """Group signals by canonical_key. Iterates once."""
        buckets: dict = defaultdict(list)
        for signal in signals:
            buckets[signal.canonical_key].append(signal)
        return dict(buckets)

    # =========================================================================
    # ARCHIVAL LOOKUP
    # =========================================================================

    @classmethod
    def _get_archived_keys(cls, account_id, signal_type: str) -> set:
        """
        Return the set of canonical_keys currently archived for this
        account & signal_type.

        A cluster is archived when a row exists with
        unarchived_at IS NULL. Historical rows (unarchived_at set) are
        ignored.
        """
        return set(
            SignalClusterArchival.objects
            .filter(
                account_id=account_id,
                signal_type=signal_type,
                unarchived_at__isnull=True,
            )
            .values_list('canonical_key', flat=True)
        )

    # =========================================================================
    # BUILD — per Pain cluster
    # =========================================================================

    @classmethod
    def _build_pain_cluster(cls, canonical_key: str, members: list) -> dict:
        """
        Build the Pain cluster dict from a list of PainSignal members.

        `members` includes VALIDATED and PENDING signals for the same
        canonical_key on the same account. REJECTED are not in `members`.

        Output shape — aligned with Objective, Impact, and TechStack on
        shared keys (identity, corroboration, status, lifecycle,
        priority, archival). Pain-specific additions beyond the common
        keys:
          - max_scope_level (the layer at which the pain is felt, read
                              directly from PainSignal.scope_level)

        Objective-compat and TechStack-compat keys are emitted with
        neutral values so the unified cluster serializer can render
        any cluster type uniformly without branching on signal_type.

        Cluster identity:
          The reference signal (most recent VALIDATED, else most
          recent member) carries the canonical axes (what, dimension)
          and the headline summary.
        """
        validated = [m for m in members if m.status == SignalStatus.VALIDATED]
        pending   = [m for m in members if m.status == SignalStatus.PENDING]

        # Pick a reference signal for the canonical axes and the summary.
        # Preference: most recent VALIDATED, else most recent PENDING.
        # `members` are ordered by _fetch_pain_signals default ordering
        # ('-created_at'), so the first match wins.
        reference = validated[0] if validated else members[0]

        # --- Stats: corroboration & breadth ---
        confirmation_count = len(validated)

        # distinct_contacts_count is computed across source_activity.contacts
        # (m2m). Contacts who participated in the source conversation are
        # derived from activity.contacts — the signal itself does not
        # carry a source_contact FK. Mirrors Objective / Impact / TechStack.
        distinct_contacts: set = set()
        for signal in validated:
            if signal.source_activity_id and signal.source_activity:
                for contact in signal.source_activity.contacts.all():
                    distinct_contacts.add(contact.id)
        distinct_contacts_count = len(distinct_contacts)

        # --- Scope: pick the highest-ranked scope_level across VALIDATED ---
        # Mirrors _compute_max_scope_level used by Objective and Impact.
        # Falls back to the reference signal's scope_level when no
        # VALIDATED member exists (defensive — Pain.scope_level has a
        # model-level default so the field is always populated).
        max_scope_level = cls._compute_max_scope_level(validated) if validated else reference.scope_level

        # --- Lifecycle ---
        has_active_dc = cls._cluster_has_active_dc(members)
        first_observed_at, last_confirmed_at, freshness = (
            cls._compute_lifecycle(validated, has_active_dc)
        )

        # --- Cluster status ---
        status_value = SignalStatus.VALIDATED if validated else SignalStatus.PENDING
        has_pending = bool(pending)
        pending_count = len(pending)

        # --- Priority ---
        stats_for_priority = {
            'confirmation_count':      confirmation_count,
            'distinct_contacts_count': distinct_contacts_count,
            'freshness_status':        freshness,
            'max_scope_level':         max_scope_level,
        }
        score = compute_pain_priority_score(stats_for_priority)
        bucket = bucket_from_score(score)

        # --- Linking ---
        decision_cycle_ids = sorted({
            str(m.decision_cycle_id) for m in members if m.decision_cycle_id
        })
        campaign_ids = sorted({
            str(m.campaign_id) for m in members if m.campaign_id
        })

        return {
            # Identity
            'canonical_key':     canonical_key,
            'signal_type':       SignalClusterType.PAIN.value,
            'what':              reference.what,
            'what_display':      reference.get_what_display(),
            'dimension':         reference.dimension,
            'dimension_display': reference.get_dimension_display(),
            'summary':           reference.summary,

            # Corroboration & breadth
            'confirmation_count':      confirmation_count,
            'distinct_contacts_count': distinct_contacts_count,

            # Status
            'status':              status_value,
            'has_pending_signals': has_pending,
            'pending_count':       pending_count,

            # Lifecycle
            'first_observed_at': first_observed_at,
            'last_confirmed_at': last_confirmed_at,
            'freshness_status':  freshness,

            # Scope (shared shape with Objective and Impact via
            # max_scope_level key)
            'max_scope_level': max_scope_level,

            # Objective-compat keys — neutral values for type-agnostic
            # frontend rendering.
            'target_dates':          [],
            'has_target_date_soon':  False,

            # TechStack-compat keys — neutral values for type-agnostic
            # rendering. See _build_techstack_cluster for the populated
            # shape on TechStack clusters.
            'tech_catalog_entry':    None,
            'lifecycle':             {
                'usage_start_year':   None,
                'renewal_date':       None,
                'cost_description':   None,
                'is_discontinued':    False,
                'discontinued_date':  None,
            },
            'scope_summary':         {
                'is_company_wide':   False,
                'departments_using': [],
                'summary_text':      None,
            },
            'has_renewal_soon':      False,
            'related_pain_clusters': [],

            # Priority
            'priority_score':  score,
            'priority_bucket': bucket,

            # Linking
            'decision_cycle_ids': decision_cycle_ids,
            'campaign_ids':       campaign_ids,

            # Archival — default False, overridden by caller if applicable
            'is_archived': False,
        }

    # =========================================================================
    # BUILD — per Objective cluster
    # =========================================================================

    @classmethod
    def _build_objective_cluster(cls, canonical_key: str, members: list) -> dict:
        """
        Build the Objective cluster dict from a list of ObjectiveSignal
        members.

        `members` includes VALIDATED and PENDING signals for the same
        canonical_key on the same account. REJECTED are not in `members`.

        Output shape — intentionally aligned with Pain and Impact on all
        shared keys so the frontend cluster renderer can remain
        type-agnostic for common fields. Objective-specific additions:
          - max_scope_level
          - target_dates        (list of ISO date strings, VALIDATED only)
          - has_target_date_soon (bool — drives priority bonus)
        """
        validated = [m for m in members if m.status == SignalStatus.VALIDATED]
        pending   = [m for m in members if m.status == SignalStatus.PENDING]

        # Pick a reference signal for axes + summary.
        # Preference: most recent VALIDATED, else most recent PENDING.
        # Members are ordered by _fetch_objective_signals default ordering
        # ('-created_at'), so the first match wins.
        reference = validated[0] if validated else members[0]

        # --- Stats: corroboration & breadth ---
        confirmation_count = len(validated)

        # distinct_contacts_count is computed across source_activity.contacts
        # (m2m). Contacts who participated in the source conversation are
        # derived from activity.contacts. Mirrors Pain / Impact / TechStack.
        #
        # Note: target_contact (PERSONAL scope) is a distinct concept on
        # Objective — it captures who OWNS the objective, not who reported
        # it. It is not consumed in this stat by design.
        distinct_contacts: set = set()
        for signal in validated:
            if signal.source_activity_id and signal.source_activity:
                for contact in signal.source_activity.contacts.all():
                    distinct_contacts.add(contact.id)
        distinct_contacts_count = len(distinct_contacts)

        # --- Max scope level observed across VALIDATED members ---
        # Objective reads scope_level directly from the model. We pick
        # the highest-ranked scope present across validated members.
        max_scope_level = cls._compute_max_scope_level(validated)

        # --- Target date proximity ---
        # True if at least one VALIDATED member has target_date within
        # OBJECTIVE_TARGET_DATE_SOON_DAYS from today.
        target_dates, has_target_date_soon = cls._compute_target_date_stats(
            validated
        )

        # --- Lifecycle ---
        has_active_dc = cls._cluster_has_active_dc(members)
        first_observed_at, last_confirmed_at, freshness = (
            cls._compute_lifecycle(validated, has_active_dc)
        )

        # --- Cluster status ---
        status_value = SignalStatus.VALIDATED if validated else SignalStatus.PENDING
        has_pending = bool(pending)
        pending_count = len(pending)

        # --- Priority ---
        stats_for_priority = {
            'confirmation_count':      confirmation_count,
            'distinct_contacts_count': distinct_contacts_count,
            'freshness_status':        freshness,
            'max_scope_level':         max_scope_level,
            'has_target_date_soon':    has_target_date_soon,
        }
        score = compute_objective_priority_score(stats_for_priority)
        bucket = bucket_from_score(score)

        # --- Linking ---
        decision_cycle_ids = sorted({
            str(m.decision_cycle_id) for m in members if m.decision_cycle_id
        })
        campaign_ids = sorted({
            str(m.campaign_id) for m in members if m.campaign_id
        })

        return {
            # Identity
            'canonical_key':     canonical_key,
            'signal_type':       SignalClusterType.OBJECTIVE.value,
            'what':              reference.what,
            'what_display':      reference.get_what_display(),
            'dimension':         reference.dimension,
            'dimension_display': reference.get_dimension_display(),
            'summary':           reference.summary,

            # Corroboration & breadth
            'confirmation_count':      confirmation_count,
            'distinct_contacts_count': distinct_contacts_count,

            # Status
            'status':              status_value,
            'has_pending_signals': has_pending,
            'pending_count':       pending_count,

            # Lifecycle
            'first_observed_at': first_observed_at,
            'last_confirmed_at': last_confirmed_at,
            'freshness_status':  freshness,

            # Scope (shared shape with Pain and Impact via max_scope_level key)
            'max_scope_level': max_scope_level,

            # Target date signals (Objective-specific)
            'target_dates':           target_dates,
            'has_target_date_soon':   has_target_date_soon,

            # Priority
            'priority_score':  score,
            'priority_bucket': bucket,

            # Linking
            'decision_cycle_ids': decision_cycle_ids,
            'campaign_ids':       campaign_ids,

            # Archival — default False, overridden by caller if applicable
            'is_archived': False,
        }

    # =========================================================================
    # BUILD — per Impact cluster
    # =========================================================================

    @classmethod
    def _build_impact_cluster(cls, canonical_key: str, members: list) -> dict:
        """
        Build the Impact cluster dict from a list of ImpactSignal members.

        `members` includes VALIDATED and PENDING signals for the same
        canonical_key on the same account. REJECTED are not in `members`.

        Output shape — aligned with Pain and Objective on every shared
        key (identity, corroboration, status, lifecycle, scope, priority,
        archival). Impact carries no target_date concept (impacts are
        observed states, not scheduled outcomes), so target-date keys
        are emitted with neutral defaults — same stance Pain takes
        toward Objective-specific fields.

        TechStack-compat keys are emitted with neutral values so the
        unified cluster serializer can render any cluster type
        uniformly without branching on signal_type.

        Cluster identity:
          The reference signal (most recent VALIDATED, else most recent
          member) carries the canonical axes (what, dimension) and the
          headline summary.

        Note on impact_type, metric_text, human_impact:
          These are per-member axes consumed by the member serializer
          (ImpactSignalListSerializer). They are NOT aggregated at the
          cluster level — the cluster identity is built from
          (what × dimension) only. Two impacts on the same
          canonical_key with different impact_types (e.g. one FINANCIAL,
          one HUMAN) coexist in the same cluster, each preserving its
          own classification on the member card. This is the
          intentional design — clustering captures
          "what × dimension at this account", individual impact_types
          are observation-level metadata.
        """
        validated = [m for m in members if m.status == SignalStatus.VALIDATED]
        pending   = [m for m in members if m.status == SignalStatus.PENDING]

        # Pick a reference signal for axes + summary.
        # Preference: most recent VALIDATED, else most recent PENDING.
        # Members are ordered by _fetch_impact_signals default ordering
        # ('-created_at'), so the first match wins.
        reference = validated[0] if validated else members[0]

        # --- Stats: corroboration & breadth ---
        confirmation_count = len(validated)

        # distinct_contacts_count is computed across source_activity.contacts
        # (m2m). Contacts who participated in the source conversation are
        # derived from activity.contacts — the signal itself does not
        # carry a source_contact FK. Mirrors Pain / Objective / TechStack.
        distinct_contacts: set = set()
        for signal in validated:
            if signal.source_activity_id and signal.source_activity:
                for contact in signal.source_activity.contacts.all():
                    distinct_contacts.add(contact.id)
        distinct_contacts_count = len(distinct_contacts)

        # --- Max scope level across VALIDATED members ---
        # Mirrors Objective: scope_level is a required field on
        # ImpactSignal (no model-level default), so every member
        # contributes a non-null value. Falls back to the reference
        # signal's scope_level when no VALIDATED member exists
        # (PENDING-only cluster — defensive).
        max_scope_level = (
            cls._compute_max_scope_level(validated)
            if validated else reference.scope_level
        )

        # --- Lifecycle ---
        has_active_dc = cls._cluster_has_active_dc(members)
        first_observed_at, last_confirmed_at, freshness = (
            cls._compute_lifecycle(validated, has_active_dc)
        )

        # --- Cluster status ---
        status_value = SignalStatus.VALIDATED if validated else SignalStatus.PENDING
        has_pending = bool(pending)
        pending_count = len(pending)

        # --- Priority ---
        stats_for_priority = {
            'confirmation_count':      confirmation_count,
            'distinct_contacts_count': distinct_contacts_count,
            'freshness_status':        freshness,
            'max_scope_level':         max_scope_level,
        }
        score = compute_impact_priority_score(stats_for_priority)
        bucket = bucket_from_score(score)

        # --- Linking ---
        decision_cycle_ids = sorted({
            str(m.decision_cycle_id) for m in members if m.decision_cycle_id
        })
        campaign_ids = sorted({
            str(m.campaign_id) for m in members if m.campaign_id
        })

        return {
            # Identity
            'canonical_key':     canonical_key,
            'signal_type':       SignalClusterType.IMPACT.value,
            'what':              reference.what,
            'what_display':      reference.get_what_display(),
            'dimension':         reference.dimension,
            'dimension_display': reference.get_dimension_display(),
            'summary':           reference.summary,

            # Corroboration & breadth
            'confirmation_count':      confirmation_count,
            'distinct_contacts_count': distinct_contacts_count,

            # Status
            'status':              status_value,
            'has_pending_signals': has_pending,
            'pending_count':       pending_count,

            # Lifecycle
            'first_observed_at': first_observed_at,
            'last_confirmed_at': last_confirmed_at,
            'freshness_status':  freshness,

            # Scope (shared shape with Pain and Objective via
            # max_scope_level key)
            'max_scope_level': max_scope_level,

            # Objective-compat keys — Impact has no target_date concept.
            # Emitted as neutral values for type-agnostic frontend
            # rendering.
            'target_dates':          [],
            'has_target_date_soon':  False,

            # TechStack-compat keys — neutral values for type-agnostic
            # rendering. See _build_techstack_cluster for the populated
            # shape on TechStack clusters.
            'tech_catalog_entry':    None,
            'lifecycle':             {
                'usage_start_year':   None,
                'renewal_date':       None,
                'cost_description':   None,
                'is_discontinued':    False,
                'discontinued_date':  None,
            },
            'scope_summary':         {
                'is_company_wide':   False,
                'departments_using': [],
                'summary_text':      None,
            },
            'has_renewal_soon':      False,
            'related_pain_clusters': [],

            # Priority
            'priority_score':  score,
            'priority_bucket': bucket,

            # Linking
            'decision_cycle_ids': decision_cycle_ids,
            'campaign_ids':       campaign_ids,

            # Archival — default False, overridden by caller if applicable
            'is_archived': False,
        }

    # =========================================================================
    # BUILD — per TechStack cluster
    # =========================================================================

    @classmethod
    def _build_techstack_cluster(cls, canonical_key: str, members: list) -> dict:
        """
        Build the TechStack cluster dict from a list of TechStackSignal members.

        `members` includes VALIDATED and PENDING signals for the same
        canonical_key on the same account. REJECTED are not in `members`.

        Output shape — aligned with Pain / Objective / Impact on shared
        keys (identity, corroboration, status, lifecycle, priority,
        archival) and enriched with TechStack-specific consolidated
        stats:
          - tech_catalog_entry payload (compact catalog reference)
          - lifecycle: usage_start_year (earliest), renewal_date (latest),
                       cost_description (latest), is_discontinued (latest),
                       discontinued_date (latest)
          - scope_summary: {is_company_wide, departments_using, summary_text}
          - related_pain_clusters: enriched list of Pain clusters that
                                   reference the same TechCatalog entry
                                   on this account

        Decision cycle / campaign linking (Pain / Objective / Impact parity):
          decision_cycle_ids and campaign_ids are derived via the
          source_activity FK chain (since TechStackSignal has no direct
          decision_cycle / campaign FK — shadow-overridden). This makes
          deal-context filtering possible while keeping TechStack
          identity account-level.
        """
        validated = [m for m in members if m.status == SignalStatus.VALIDATED]
        pending   = [m for m in members if m.status == SignalStatus.PENDING]

        # Pick a reference signal for the catalog entry payload.
        # Preference: most recent VALIDATED, else most recent global.
        # Members are ordered by '-created_at' from _fetch_techstack_signals.
        reference = validated[0] if validated else members[0]

        # --- Stats: corroboration & breadth ---
        confirmation_count = len(validated)

        # `distinct_contacts_count` is computed across source_activity.contacts
        # since TechStackSignal has no source_contact FK (shadow-override).
        # Each VALIDATED signal contributes its activity's contacts.
        distinct_contacts: set = set()
        for signal in validated:
            if signal.source_activity_id and signal.source_activity:
                for contact in signal.source_activity.contacts.all():
                    distinct_contacts.add(contact.id)
        distinct_contacts_count = len(distinct_contacts)

        # --- Lifecycle stats consolidation (VALIDATED only) ---
        consolidated_lifecycle = cls._consolidate_techstack_lifecycle(validated)

        # --- Scope summary (VALIDATED only) ---
        scope_summary = cls._compute_techstack_scope_summary(validated)

        # --- Cluster lifecycle: first/last/freshness ---
        # We use BaseSignal.created_at like Pain / Objective / Impact do.
        # The active-DC clamp is computed by traversing source_activity →
        # decision_cycle (TechStack has no direct decision_cycle FK).
        has_active_dc = cls._techstack_cluster_has_active_dc(members)
        first_observed_at, last_confirmed_at, freshness = (
            cls._compute_lifecycle(validated, has_active_dc)
        )

        # --- Cluster status ---
        status_value = SignalStatus.VALIDATED if validated else SignalStatus.PENDING
        has_pending = bool(pending)
        pending_count = len(pending)

        # --- Renewal-soon flag (drives priority bonus + UI urgency badge) ---
        has_renewal_soon = cls._compute_techstack_renewal_soon(validated)

        # --- Cross-references with Pain clusters ---
        # Account-scoped. Catalog entry resolved from the reference signal.
        related_pain_clusters = cls._compute_related_pain_clusters(
            account_id=reference.account_id,
            tech_catalog_entry_id=reference.tech_catalog_entry_id,
        )

        # --- Priority ---
        stats_for_priority = {
            'confirmation_count':         confirmation_count,
            'distinct_contacts_count':    distinct_contacts_count,
            'distinct_departments_count': len(scope_summary['departments_using']),
            'related_pain_count':         len(related_pain_clusters),
            'is_competitor':              bool(
                reference.tech_catalog_entry
                and reference.tech_catalog_entry.is_competitor
            ),
            'is_integration_target':      bool(
                reference.tech_catalog_entry
                and reference.tech_catalog_entry.is_integration_target
            ),
            'has_renewal_soon':           has_renewal_soon,
            'is_discontinued':            bool(consolidated_lifecycle.get('is_discontinued')),
            'freshness_status':           freshness,
        }
        score = compute_techstack_priority_score(stats_for_priority)
        bucket = bucket_from_score(score)

        # --- Linking via source_activity (no direct DC/campaign FK) ---
        decision_cycle_ids = sorted({
            str(m.source_activity.decision_cycle_id)
            for m in members
            if m.source_activity_id
            and m.source_activity
            and m.source_activity.decision_cycle_id
        })
        campaign_ids = sorted({
            str(m.source_activity.campaign_id)
            for m in members
            if m.source_activity_id
            and m.source_activity
            and m.source_activity.campaign_id
        })

        # --- Catalog payload (compact — drives identity display) ---
        tech_catalog_entry_payload = None
        if reference.tech_catalog_entry:
            entry = reference.tech_catalog_entry
            tech_catalog_entry_payload = {
                'id':                    str(entry.id),
                'company_name':          entry.company_name,
                'product_name':          entry.product_name,
                'is_competitor':         entry.is_competitor,
                'is_integration_target': entry.is_integration_target,
            }

        return {
            # =================================================================
            # IDENTITY
            # =================================================================
            'canonical_key':     canonical_key,
            'signal_type':       SignalClusterType.TECH_STACK.value,
            # TechStack has no what/dimension axes — emitted as None for
            # frontend-renderer compatibility.
            'what':              None,
            'what_display':      None,
            'dimension':         None,
            'dimension_display': None,
            # `summary` is the catalog entry's product display name on
            # TechStack clusters — there is no narrative summary on the
            # signal itself. Frontend renders this as the cluster card
            # title.
            'summary': (
                str(reference.tech_catalog_entry)
                if reference.tech_catalog_entry
                else None
            ),

            # =================================================================
            # TECHSTACK-SPECIFIC IDENTITY
            # =================================================================
            'tech_catalog_entry': tech_catalog_entry_payload,

            # =================================================================
            # CORROBORATION & BREADTH
            # =================================================================
            'confirmation_count':      confirmation_count,
            'distinct_contacts_count': distinct_contacts_count,

            # =================================================================
            # STATUS
            # =================================================================
            'status':              status_value,
            'has_pending_signals': has_pending,
            'pending_count':       pending_count,

            # =================================================================
            # LIFECYCLE (cluster-level — first/last/freshness)
            # =================================================================
            'first_observed_at': first_observed_at,
            'last_confirmed_at': last_confirmed_at,
            'freshness_status':  freshness,

            # =================================================================
            # TECHSTACK LIFECYCLE STATS (consolidated from VALIDATED members)
            # =================================================================
            'lifecycle': consolidated_lifecycle,

            # =================================================================
            # SCOPE SUMMARY (consolidated from VALIDATED members)
            # =================================================================
            'scope_summary': scope_summary,

            # =================================================================
            # RENEWAL URGENCY (drives priority + UI badge)
            # =================================================================
            'has_renewal_soon': has_renewal_soon,

            # =================================================================
            # CROSS-REFERENCES — Pain clusters that reference this catalog
            # entry on the same account
            # =================================================================
            'related_pain_clusters': related_pain_clusters,

            # =================================================================
            # OBJECTIVE-COMPAT KEYS (neutral values for type-agnostic rendering)
            # =================================================================
            'max_scope_level':       None,
            'target_dates':          [],
            'has_target_date_soon':  False,

            # =================================================================
            # PRIORITY
            # =================================================================
            'priority_score':  score,
            'priority_bucket': bucket,

            # =================================================================
            # LINKING (via source_activity — TechStack has no direct FKs)
            # =================================================================
            'decision_cycle_ids': decision_cycle_ids,
            'campaign_ids':       campaign_ids,

            # =================================================================
            # ARCHIVAL — default False, overridden by caller if applicable
            # =================================================================
            'is_archived': False,
        }

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    @classmethod
    def _compute_lifecycle(
        cls,
        validated_signals: list,
        has_active_dc: bool,
    ):
        """
        Derive first_observed_at, last_confirmed_at, freshness_status.

        Uses BaseSignal.created_at as the timestamp anchor. validated_at
        was considered but rejected: two signals confirmed on the same
        call would get identical validated_at timestamps (same audit
        click), which flattens lifecycle signal. created_at reflects
        when the observation entered the system.

        If there is no VALIDATED signal in the cluster, freshness is None
        (no confirmed observation to measure staleness against).

        Active DC exception: if at least one member references a decision
        cycle whose outcome is NULL or ON_HOLD, freshness is clamped to
        DORMANT at worst — never STALE. Rationale: a living deal keeps
        its pain / objective / impact relevant even if the last
        confirmation is old.
        """
        if not validated_signals:
            return None, None, None

        timestamps = [s.created_at for s in validated_signals]
        first = min(timestamps)
        last = max(timestamps)

        age_days = (timezone.now() - last).days

        if age_days < FRESHNESS_FRESH_DAYS:
            freshness = FreshnessStatus.FRESH
        elif age_days < FRESHNESS_DORMANT_DAYS:
            freshness = FreshnessStatus.DORMANT
        else:
            freshness = FreshnessStatus.STALE

        # Active-DC clamp
        if freshness == FreshnessStatus.STALE and has_active_dc:
            freshness = FreshnessStatus.DORMANT

        return first, last, freshness

    # =========================================================================
    # SCOPE / TARGET-DATE HELPERS
    # =========================================================================

    @classmethod
    def _compute_max_scope_level(cls, validated_members: list):
        """
        Pick the highest-ranked scope_level across a cluster's VALIDATED
        members.

        Used by Pain, Objective, and Impact cluster builders — all three
        signal types carry scope_level as a direct field on the model.
        The helper is type-agnostic: it reads signal.scope_level on
        every member regardless of the concrete class.

        BUSINESS > DEPARTMENT > PERSONAL per _SCOPE_LEVEL_RANK.

        Returns:
            ScopeLevel value or None if no VALIDATED member.
        """
        max_rank = 0
        max_level = None
        for signal in validated_members:
            rank = _SCOPE_LEVEL_RANK.get(signal.scope_level, 0)
            if rank > max_rank:
                max_rank = rank
                max_level = signal.scope_level
        return max_level

    @classmethod
    def _compute_target_date_stats(cls, validated_members: list):
        """
        Compute target-date aggregation for a cluster's VALIDATED
        Objective members.

        Returns a 2-tuple:
          target_dates:          sorted list of ISO yyyy-mm-dd strings
                                 for all members with a non-null
                                 target_date (duplicates kept — the
                                 frontend can dedupe if needed)
          has_target_date_soon:  True if at least one member's
                                 target_date is within
                                 OBJECTIVE_TARGET_DATE_SOON_DAYS from
                                 today (used by the priority scorer)
        """
        today = timezone.now().date()
        soon_cutoff = today + timedelta(days=OBJECTIVE_TARGET_DATE_SOON_DAYS)

        target_dates: list = []
        has_soon = False

        for signal in validated_members:
            td = signal.target_date
            if td is None:
                continue
            target_dates.append(td.isoformat())
            if today <= td <= soon_cutoff:
                has_soon = True

        target_dates.sort()
        return target_dates, has_soon

    # =========================================================================
    # ACTIVE DC DETECTION
    # =========================================================================

    @staticmethod
    def _cluster_has_active_dc(members: list) -> bool:
        """
        True if at least one member references a decision cycle whose
        outcome is NULL (open) or ON_HOLD (paused, but alive).

        Terminal outcomes (WON / LOST / NOT_QUALIFIED) do NOT count as
        active. Members without a decision_cycle are ignored.
        """
        for signal in members:
            dc = signal.decision_cycle
            if dc is None:
                continue
            if dc.outcome is None or dc.outcome == CycleOutcome.ON_HOLD:
                return True
        return False

    # =========================================================================
    # TECHSTACK HELPERS — consolidation, scope, renewal, related pains
    # =========================================================================

    @classmethod
    def _consolidate_techstack_lifecycle(cls, validated_members: list) -> dict:
        """
        Consolidate the lifecycle stats from a cluster's VALIDATED
        TechStack members into a single dict.

        Strategy per field
        ------------------
          - usage_start_year   : EARLIEST observed value (semantics:
                                 "since when does the account use this
                                 tool"). The earliest a rep ever heard
                                 wins.
          - renewal_date       : LATEST observation that set the field.
                                 The most recent rep update is the
                                 source of truth for the upcoming
                                 renewal.
          - cost_description   : LATEST observation that set the field.
                                 Same rationale.
          - is_discontinued    : LATEST observation (boolean — always
                                 defined; the most recent rep call wins).
          - discontinued_date  : LATEST observation that set the field.

        Implementation
        --------------
        `validated_members` is ordered '-created_at' by
        _fetch_techstack_signals. For "LATEST" fields, we walk the list
        and take the first non-null value. For `usage_start_year`, we
        compute the min across all non-null values.

        Output shape
        ------------
        Always returns a complete dict with all 5 keys, neutral defaults
        when no observation has set the field:
          {
            'usage_start_year':  <int | None>,
            'renewal_date':      <ISO-date str | None>,
            'cost_description':  <str | None>,
            'is_discontinued':   <bool>,            # default False
            'discontinued_date': <ISO-date str | None>,
          }
        """
        consolidated = {
            'usage_start_year':   None,
            'renewal_date':       None,
            'cost_description':   None,
            'is_discontinued':    False,
            'discontinued_date':  None,
        }

        # `validated_members` is ordered '-created_at': index 0 is the
        # most recent. For "LATEST" fields, the first non-null value we
        # encounter is the answer.
        seen_renewal       = False
        seen_cost          = False
        seen_discontinued  = False  # tracks first non-null is_discontinued
        seen_disc_date     = False

        # For usage_start_year: collect all non-null values to compute min.
        start_years: list = []

        for signal in validated_members:
            # usage_start_year — earliest wins
            if signal.usage_start_year is not None:
                start_years.append(signal.usage_start_year)

            # renewal_date — first non-null going from most recent
            if not seen_renewal and signal.renewal_date is not None:
                consolidated['renewal_date'] = signal.renewal_date.isoformat()
                seen_renewal = True

            # cost_description — first non-empty going from most recent
            if not seen_cost and signal.cost_description and signal.cost_description.strip():
                consolidated['cost_description'] = signal.cost_description.strip()
                seen_cost = True

            # is_discontinued — value of most recent observation
            # Note: BooleanField is always non-null. We take the first
            # signal we see (the most recent) and stop.
            if not seen_discontinued:
                consolidated['is_discontinued'] = bool(signal.is_discontinued)
                seen_discontinued = True

            # discontinued_date — first non-null going from most recent
            if not seen_disc_date and signal.discontinued_date is not None:
                consolidated['discontinued_date'] = signal.discontinued_date.isoformat()
                seen_disc_date = True

        if start_years:
            consolidated['usage_start_year'] = min(start_years)

        return consolidated

    @classmethod
    def _compute_techstack_lifecycle_observations(
        cls,
        validated_members: list,
    ) -> dict:
        """
        Compute the per-field observation list used by the cluster
        detail's `all_observations` drill-down.

        Detail-only — never emitted in list responses (kept bounded).

        Output shape
        ------------
            {
              'usage_start_year': [
                {'value': 2019,
                 'signal_id': <uuid_str>,
                 'source_activity_id': <uuid_str | None>,
                 'observed_at': <ISO-datetime str>},
                ...
              ],
              'renewal_date':      [...],
              'cost_description':  [...],
              'is_discontinued':   [...],
              'discontinued_date': [...],
            }

        Each list contains every VALIDATED observation that SET the
        corresponding field (i.e. non-null / non-empty). Lists are
        ordered by created_at DESC (most recent first), matching the
        input member order.

        For `is_discontinued` (BooleanField, always non-null), we
        include every observation since "False" is a meaningful state
        worth tracing.
        """
        observations: dict = {
            'usage_start_year':   [],
            'renewal_date':       [],
            'cost_description':   [],
            'is_discontinued':    [],
            'discontinued_date':  [],
        }

        for signal in validated_members:
            base_payload = {
                'signal_id':          str(signal.id),
                'source_activity_id': (
                    str(signal.source_activity_id)
                    if signal.source_activity_id else None
                ),
                'observed_at':        signal.created_at.isoformat(),
            }

            if signal.usage_start_year is not None:
                observations['usage_start_year'].append({
                    **base_payload,
                    'value': signal.usage_start_year,
                })
            if signal.renewal_date is not None:
                observations['renewal_date'].append({
                    **base_payload,
                    'value': signal.renewal_date.isoformat(),
                })
            if signal.cost_description and signal.cost_description.strip():
                observations['cost_description'].append({
                    **base_payload,
                    'value': signal.cost_description.strip(),
                })
            # Boolean — always include, "False" is a meaningful trace
            observations['is_discontinued'].append({
                **base_payload,
                'value': bool(signal.is_discontinued),
            })
            if signal.discontinued_date is not None:
                observations['discontinued_date'].append({
                    **base_payload,
                    'value': signal.discontinued_date.isoformat(),
                })

        return observations

    @classmethod
    def _compute_techstack_scope_summary(cls, validated_members: list) -> dict:
        """
        Compute the scope summary across a cluster's VALIDATED members.

        Output shape
        ------------
            {
              'is_company_wide':   <bool>,
              'departments_using': [
                  {'id': <uuid_str>, 'name': <display_str>},
                  ...
              ],
              'summary_text':      <str | None>,
            }

        Rules
        -----
          1. is_company_wide=True if at least one VALIDATED signal has
             usage_scope=COMPANY.
          2. departments_using collects distinct usage_department FKs
             across signals whose usage_scope=DEPARTMENT.
          3. summary_text narrative:
               - "Used company-wide" if is_company_wide
               - else "Used by <Dept1>, <Dept2>" if departments_using non-empty
               - else "Used at team level" if any signal has usage_scope=TEAM
               - else None (no scope information yet, or only UNKNOWN scopes)
        """
        # Lazy import to avoid surfacing UsageScope in the module-level
        # imports — only this helper needs it.
        from ..constants import UsageScope

        is_company_wide = False
        has_team_scope  = False

        # Use ordered dict semantics via dict (Python 3.7+) keyed by
        # department UUID for distinctness while preserving insertion
        # order (most recent observation first since members are
        # ordered '-created_at').
        departments_seen: dict = {}

        for signal in validated_members:
            scope = signal.usage_scope

            if scope == UsageScope.COMPANY:
                is_company_wide = True
                continue

            if scope == UsageScope.DEPARTMENT and signal.usage_department_id:
                dept_id = str(signal.usage_department_id)
                if dept_id not in departments_seen:
                    dept = signal.usage_department
                    departments_seen[dept_id] = {
                        'id':   dept_id,
                        'name': (
                            dept.get_name_display()
                            if hasattr(dept, 'get_name_display')
                            else str(dept)
                        ),
                    }
                continue

            if scope == UsageScope.TEAM:
                has_team_scope = True
                continue

            # UsageScope.UNKNOWN or None — no scope contribution

        departments_using = list(departments_seen.values())

        # Narrative summary
        if is_company_wide:
            summary_text = "Used company-wide"
        elif departments_using:
            dept_names = ", ".join(d['name'] for d in departments_using)
            summary_text = f"Used by {dept_names}"
        elif has_team_scope:
            summary_text = "Used at team level"
        else:
            summary_text = None

        return {
            'is_company_wide':   is_company_wide,
            'departments_using': departments_using,
            'summary_text':      summary_text,
        }

    @classmethod
    def _compute_techstack_renewal_soon(cls, validated_members: list) -> bool:
        """
        Return True if at least one VALIDATED member has a renewal_date
        within TECHSTACK_RENEWAL_SOON_DAYS from today (inclusive).

        Past renewal dates are IGNORED — they no longer represent an
        upcoming urgency. Only future-or-today dates within the window
        count.

        Drives:
          - the `has_renewal_soon` boolean exposed on the cluster
            payload (UI urgency badge);
          - the `has_renewal_soon` input to compute_techstack_priority_score
            (priority bonus).
        """
        # Lazy import — TECHSTACK_RENEWAL_SOON_DAYS lives in constants.py
        # alongside the other thresholds.
        from ..constants import TECHSTACK_RENEWAL_SOON_DAYS

        today       = timezone.now().date()
        soon_cutoff = today + timedelta(days=TECHSTACK_RENEWAL_SOON_DAYS)

        for signal in validated_members:
            rd = signal.renewal_date
            if rd is None:
                continue
            if today <= rd <= soon_cutoff:
                return True

        return False

    @classmethod
    def _techstack_cluster_has_active_dc(cls, members: list) -> bool:
        """
        True if at least one member references (via source_activity) a
        decision cycle whose outcome is NULL (open) or ON_HOLD (paused).

        TechStackSignal has no direct decision_cycle FK — the field is
        shadow-overridden. The deal context is inferred via
        source_activity.decision_cycle. Signals without source_activity
        are skipped.

        Used to clamp cluster freshness (a STALE cluster on an active
        deal is downgraded to DORMANT — same rule as Pain / Objective /
        Impact).
        """
        for signal in members:
            act = signal.source_activity
            if act is None:
                continue
            dc = act.decision_cycle
            if dc is None:
                continue
            if dc.outcome is None or dc.outcome == CycleOutcome.ON_HOLD:
                return True
        return False

    @classmethod
    def _compute_related_pain_clusters(
        cls,
        *,
        account_id,
        tech_catalog_entry_id,
    ) -> list:
        """
        Find Pain clusters on the same account that cross-reference this
        TechCatalog entry via PainSignal.related_techstack.

        Returns an enriched list of cluster summaries:
            [
              {
                'canonical_key':       'pain:TECH:TIME',
                'summary':             '...',
                'confirmation_count':  4,
              },
              ...
            ]
        Sorted by confirmation_count DESC (most-corroborated cluster
        first), then by canonical_key for stable ordering on ties.

        Performance note
        ----------------
        This helper issues one extra SELECT per TechStack cluster being
        built. For large accounts (>100 TechStack clusters), consider
        prefetching at the listing layer in a future optimisation
        sprint. For MVP, the cost is acceptable.

        Args:
            account_id:             UUID of the account.
            tech_catalog_entry_id:  UUID of the TechCatalog entry that
                                    drove the TechStack cluster
                                    (canonical_key = "techstack:<id>").

        Returns:
            list of cluster summary dicts. Empty list if no Pain
            cross-references this catalog entry on the account.
        """
        if not tech_catalog_entry_id:
            return []

        # Pull the cross-referencing Pains. Order by canonical_key first
        # so groupby() yields deterministic groups, then by created_at
        # DESC within each group so the first member of each group is
        # the most recent (its summary becomes the cluster summary).
        related_pains = (
            PainSignal.objects
            .filter(
                account_id=account_id,
                related_techstack_id=tech_catalog_entry_id,
                status=SignalStatus.VALIDATED,
            )
            .order_by('canonical_key', '-created_at')
            .only('id', 'canonical_key', 'summary')
        )

        # Group by canonical_key. Avoid itertools.groupby because we
        # want both count and "most-recent summary" — a single pass is
        # cleaner with an explicit dict.
        groups: dict = {}
        for pain in related_pains:
            key = pain.canonical_key
            if key is None:
                continue  # defensive — shouldn't happen for VALIDATED Pains
            entry = groups.get(key)
            if entry is None:
                groups[key] = {
                    'canonical_key':      key,
                    'summary':            pain.summary,  # first = most recent (queryset ordered '-created_at')
                    'confirmation_count': 1,
                }
            else:
                entry['confirmation_count'] += 1

        # Sort by confirmation_count DESC, then canonical_key for stability.
        return sorted(
            groups.values(),
            key=lambda c: (-c['confirmation_count'], c['canonical_key']),
        )