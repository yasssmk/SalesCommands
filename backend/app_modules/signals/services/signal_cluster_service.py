# app_modules/signals/services/signal_cluster_service.py
"""
SignalClusterService — aggregate signals into canonical clusters.

A cluster is the set of signals sharing the same canonical_key on a
given account. For Pain, canonical_key is
    "pain:<SignalWhat>:<SignalDimension>"
so a cluster corresponds to a distinct pain diagnosis at an account,
regardless of which contact reported it or when. The same canonical
structure applies to Objective since Wave B —
"objective:<SignalWhat>:<SignalDimension>" — and to TechStack since
Sprint TechStack — "techstack:<TechCatalog.id>".

Supported signal types
----------------------
list_clusters_for_account accepts either a single signal_type string
or a list. The three concrete signal types — Pain, Objective, and
TechStack — all produce real clusters today. Any other signal_type
value is rejected by the guard as "not supported".

What the service does
---------------------
  1. Loads PainSignals for an account (VALIDATED + PENDING; REJECTED
     excluded entirely).
  2. Groups them by canonical_key.
  3. For each group, computes consolidated stats:
       - confirmation_count    (VALIDATED members only)
       - distinct_contacts_count
       - impacted_contacts_count
       - human_impacts aggregation (from PainImpacts of VALIDATED members)
       - metrics list (from PainImpacts of VALIDATED members)
  4. Computes lifecycle (first_observed_at, last_confirmed_at,
     freshness_status) with the active-DC exception.
  5. Derives cluster status (VALIDATED + has_pending_signals + pending_count).
  6. Delegates priority scoring to signal_priority_service.
  7. Marks clusters as archived by cross-referencing
     SignalClusterArchival.
  8. Optionally filters the cluster list to a specific decision_cycle.
  9. Detail-only: computes a per-scope-level breakdown (`by_level`) of
     the cluster's PainImpacts — shape is documented on
     get_cluster_detail below. Not emitted in list responses to keep
     payloads bounded.

What the service does NOT do
----------------------------
  - It does not write anything.
  - It does not paginate (MVP — acceptable for <100 clusters per account).
  - It does not cache 

Output shape
------------
list_clusters_for_account returns a list of dicts. get_cluster_detail
returns the same dict structure plus a 'members' key with the raw
PainSignal instances (the serializer is responsible for turning those
into JSON).

Each cluster dict contains:

    {
        # Identity
        'canonical_key':        'pain:OPS:TIME',
        'signal_type':          'pain',
        'what':                 'OPS',
        'what_display':         'Operations / Process',
        'dimension':            'TIME',
        'dimension_display':    'Time / Speed',
        'summary':              '...',     # consolidated summary

        # Corroboration & breadth
        'confirmation_count':      2,
        'distinct_contacts_count': 2,
        'impacted_contacts_count': 3,

        # Status
        'status':               'VALIDATED' | 'PENDING',
        'has_pending_signals':  True,
        'pending_count':        1,

        # Lifecycle
        'first_observed_at':    datetime | None,
        'last_confirmed_at':    datetime | None,
        'freshness_status':     'FRESH' | 'DORMANT' | 'STALE' | None,

        # Impact aggregation (Pain-specific)
        'human_impacts': [
            {'type': 'FRUSTRATION', 'count': 2},
            {'type': 'OVERLOAD',    'count': 1},
        ],
        'metrics': [
            '120k$/year',
            '15h/week',
        ],
        'max_impact_level': 'BUSINESS' | 'DEPARTMENT' | 'PERSONAL' | None,

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

from collections import Counter, defaultdict
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
from ..models import ObjectiveSignal, PainImpact, PainSignal, SignalClusterArchival, TechStackSignal
from .signal_priority_service import (
    OBJECTIVE_TARGET_DATE_SOON_DAYS,
    bucket_from_score,
    compute_objective_priority_score,
    compute_pain_priority_score,
    compute_techstack_priority_score,
)

# Ordering used to determine the "max observed" scope level on a cluster.
# BUSINESS > DEPARTMENT > PERSONAL — the strongest evidence wins.
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
                                single string ('pain' / 'objective') or a
                                list/tuple of strings for mixed queries.
                                Pain produces real clusters; Objective is
                                accepted but returns no clusters until
                                Wave B activates the port.
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
            not in the supported set (currently {'pain', 'objective'}).
        """
        requested_types = cls._assert_signal_types_supported(signal_type)

        clusters: list = []

        # Dispatch per signal_type. Pain was the only active cluster type
        # in Sprint 2; Objective joined in Wave B; TechStack joined in
        # Sprint TechStack. All three produce real clusters; the guard
        # above rejects any other type.
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
    # INTERNAL — Pain-specific listing (factored out of the dispatch loop)
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
        future signal types (Objective in Wave B) can plug in via their
        own _list_*_clusters_for_account helper without touching the
        Pain logic.
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
    # INTERNAL — Objective-specific listing (Wave B)
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

        Mirror of _list_pain_clusters_for_account but scoped to
        ObjectiveSignal. The shape of the returned cluster dict is the
        same as Pain's, minus Pain-specific keys (impacts aggregation,
        max_impact_level, human_impacts, metrics). See
        _build_objective_cluster for the exact output shape.
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
    # INTERNAL — TechStack-specific listing (Sprint TechStack)
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
        Return a single cluster with its member signals and per-scope-level
        breakdown.

        The cluster dict has the same shape as in list_clusters_for_account
        plus:
          - `members`: PainSignal instances (impacts prefetched) — turned
                       into JSON by the calling serializer.
          - `by_level`: per-ScopeLevel breakdown of this cluster's
                        validated PainImpacts. See _aggregate_by_level
                        below for the exact shape.

        The Wave A-introduced `by_level` key is detail-only. It is not
        emitted by list endpoints to keep list payloads bounded.

        Args:
            account_id:     UUID of the account.
            canonical_key:  Cluster identifier (e.g. 'pain:OPS:TIME').
            signal_type:    Cluster signal type — single string. 'pain'
                            yields real data; 'objective' is accepted at
                            the API surface but raises CLUSTER_NOT_FOUND
                            until Wave B activates it. Other types are
                            rejected by the guard.

        Returns:
            Cluster dict with `members` and `by_level` keys.

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

        # Dispatch per signal type. Both Pain and Objective produce real
        # cluster detail payloads since Wave B.
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

            # Detail-only enrichment: per-scope-level breakdown of the
            # cluster's PainImpacts. Computed from the VALIDATED members
            # already loaded above — no extra DB hit.
            validated_members = [
                m for m in members if m.status == SignalStatus.VALIDATED
            ]
            cluster['by_level'] = cls._aggregate_by_level(validated_members)

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

            # No by_level aggregation for Objective — the scope_level
            # is stored directly on each member and already surfaced
            # through the cluster's max_scope_level stat. PainImpact-style
            # per-scope breakdown has no equivalent here.

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
            # members only (consistent with Pain/Objective). See
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
    # surface. Pain and Objective produce real clusters; TechStack is
    # activated since Sprint TechStack and follows the same canonical
    # cluster pattern (canonical_key = "techstack:<catalog_entry_id>"
    # on an account).
    _SUPPORTED_CLUSTER_TYPES = frozenset({
        SignalClusterType.PAIN.value,
        SignalClusterType.OBJECTIVE.value,
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
        Base queryset for cluster aggregation.

        Includes VALIDATED and PENDING signals (REJECTED excluded as per
        product decision). Prefetches impacts of VALIDATED parents only —
        impacts of PENDING / REJECTED parents do not contribute to
        cluster stats.

        Note on the prefetch filter: PainImpact has no status field; the
        filter is on the parent Pain's status. The prefetch_related below
        loads impacts regardless, and the aggregation layer
        (_aggregate_impacts) filters them at runtime using the member's
        status. This keeps the query simple and avoids a subquery.
        """
        qs = (
            PainSignal.objects
            .filter(
                account_id=account_id,
                status__in=(SignalStatus.VALIDATED, SignalStatus.PENDING),
            )
            .select_related(
                'source_activity',  # nested in cluster member payload via
                                    # PainSignalDetailSerializer
                'source_contact',
                'decision_cycle',
                'campaign',
            )
            .prefetch_related(
                Prefetch(
                    'impacts',
                    queryset=PainImpact.objects.select_related(
                        'impacted_department',
                        'impacted_contact',
                    ),
                ),
                # ActivityCompactSerializer (nested inside each cluster
                # member) reads source_activity.contacts — prefetch keeps
                # the cluster detail at a bounded query count.
                'source_activity__contacts',
            )
        )

        if decision_cycle_id:
            qs = qs.filter(decision_cycle_id=decision_cycle_id)

        return qs
    
    @classmethod
    def _fetch_objective_signals(cls, *, account_id, decision_cycle_id=None):
        """
        Base queryset for Objective cluster aggregation (Wave B).

        Includes VALIDATED and PENDING signals (REJECTED excluded — same
        product rule as Pain).

        Unlike Pain, Objective has no child `impacts` relation — scope
        and target are stored directly on the model. The only prefetch
        needed is source_activity.contacts so that
        ActivityCompactSerializer (nested inside each cluster member
        detail payload) resolves without additional queries.
        """
        qs = (
            ObjectiveSignal.objects
            .filter(
                account_id=account_id,
                status__in=(SignalStatus.VALIDATED, SignalStatus.PENDING),
            )
            .select_related(
                'source_activity',
                'source_contact',
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
    def _fetch_techstack_signals(cls, *, account_id, decision_cycle_id=None):
        """
        Base queryset for TechStack cluster aggregation (Sprint TechStack).

        Includes VALIDATED and PENDING signals (REJECTED excluded — same
        product rule as Pain/Objective).

        Unlike Pain (which has the impacts child relation) and Objective
        (which carries scope/target on the model), TechStack signals are
        flat: every lifecycle field (usage_start_year, renewal_date,
        cost_description, is_discontinued, discontinued_date, notes)
        lives directly on the model. No prefetched child relation needed.

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
    # BUILD — per cluster
    # =========================================================================

    @classmethod
    def _build_pain_cluster(cls, canonical_key: str, members: list) -> dict:
        """
        Build the cluster dict from a list of PainSignal members.

        `members` includes VALIDATED and PENDING signals for the same
        canonical_key on the same account. REJECTED are not in `members`.
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
        distinct_contacts_count = len({
            m.source_contact_id for m in validated if m.source_contact_id
        })

        # --- Impacts aggregation (VALIDATED parents only) ---
        human_impacts, metrics, impacted_contacts, max_level = (
            cls._aggregate_impacts(validated)
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
            'has_human_impact':        bool(human_impacts),
            'max_impact_level':        max_level,
            'has_metric':              bool(metrics),
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
            'impacted_contacts_count': len(impacted_contacts),

            # Status
            'status':              status_value,
            'has_pending_signals': has_pending,
            'pending_count':       pending_count,

            # Lifecycle
            'first_observed_at': first_observed_at,
            'last_confirmed_at': last_confirmed_at,
            'freshness_status':  freshness,

            # Pain-specific impact aggregation
            'human_impacts':     human_impacts,
            'metrics':           metrics,
            'max_impact_level':  max_level,

            # Objective-compat keys — Pain has no scope_level / target_date
            # concepts. Emitted as neutral values so the unified cluster
            # serializer can render any cluster type without branching on
            # signal_type.
            'max_scope_level':       None,
            'target_dates':          [],
            'has_target_date_soon':  False,

            # TechStack-compat keys — Pain has no catalog FK / lifecycle
            # stats / scope summary / renewal urgency / related-pain
            # cross-references. Emitted as neutral values so the unified
            # cluster serializer can render any cluster type uniformly.
            # See _build_techstack_cluster for the populated shape.
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
    # BUILD — per Objective cluster  (Wave B)
    # =========================================================================

    @classmethod
    def _build_objective_cluster(cls, canonical_key: str, members: list) -> dict:
        """
        Build the Objective cluster dict from a list of ObjectiveSignal
        members.

        `members` includes VALIDATED and PENDING signals for the same
        canonical_key on the same account. REJECTED are not in `members`.

        Output shape — intentionally aligned with Pain on all shared keys
        so the frontend cluster renderer can remain type-agnostic for
        common fields. Objective-specific additions:
          - max_scope_level     (instead of Pain's max_impact_level)
          - target_dates        (list of ISO date strings, VALIDATED only)
          - has_target_date_soon (bool — drives priority bonus)

        Objective-specific omissions (vs Pain):
          - human_impacts, metrics, impacted_contacts_count — these are
            Pain/Impact concepts with no equivalent on Objective. Fields
            still present as empty/None for cluster renderer uniformity.
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
        distinct_contacts_count = len({
            m.source_contact_id for m in validated if m.source_contact_id
        })

        # --- Max scope level observed across VALIDATED members ---
        # Objective reads scope_level directly from the model (no
        # PainImpact indirection). We pick the highest-ranked scope
        # present across validated members.
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
            # Pain-compat key — Objective has no impact concept; fixed 0
            # so the frontend cluster renderer stays type-agnostic.
            'impacted_contacts_count': 0,

            # Status
            'status':              status_value,
            'has_pending_signals': has_pending,
            'pending_count':       pending_count,

            # Lifecycle
            'first_observed_at': first_observed_at,
            'last_confirmed_at': last_confirmed_at,
            'freshness_status':  freshness,

            # Scope (Objective-specific)
            'max_scope_level': max_scope_level,

            # Target date signals (Objective-specific)
            'target_dates':           target_dates,
            'has_target_date_soon':   has_target_date_soon,

            # Pain-compat keys — empty/None so the cluster renderer can
            # share code across signal types without special-casing.
            'human_impacts':    [],
            'metrics':          [],
            'max_impact_level': None,

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
    # BUILD — per TechStack cluster (Sprint TechStack)
    # =========================================================================

    @classmethod
    def _build_techstack_cluster(cls, canonical_key: str, members: list) -> dict:
        """
        Build the TechStack cluster dict from a list of TechStackSignal members.

        `members` includes VALIDATED and PENDING signals for the same
        canonical_key on the same account. REJECTED are not in `members`.

        Output shape — aligned with Pain/Objective on shared keys
        (identity, corroboration, status, lifecycle, priority, archival)
        and enriched with TechStack-specific consolidated stats:
          - tech_catalog_entry payload (compact catalog reference)
          - lifecycle: usage_start_year (earliest), renewal_date (latest),
                       cost_description (latest), is_discontinued (latest),
                       discontinued_date (latest)
          - scope_summary: {is_company_wide, departments_using, summary_text}
          - related_pain_clusters: enriched list of Pain clusters that
                                   reference the same TechCatalog entry
                                   on this account

        Pain/Objective-compat keys (emitted as neutral values for
        type-agnostic frontend rendering):
          - human_impacts=[], metrics=[], max_impact_level=None,
            impacted_contacts_count=0
          - max_scope_level=None, target_dates=[], has_target_date_soon=False

        Decision cycle / campaign linking (Pain/Objective parity):
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
        # We use BaseSignal.created_at like Pain/Objective do. The
        # active-DC clamp is computed by traversing source_activity →
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
        # Stats consumed by compute_techstack_priority_score (added in Phase 7).
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
            # Pain-compat key — TechStack has no impact concept.
            'impacted_contacts_count': 0,

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
            # Output of _consolidate_techstack_lifecycle:
            #   {
            #     'usage_start_year':   <int | None>,
            #     'renewal_date':       <ISO-date | None>,
            #     'cost_description':   <str | None>,
            #     'is_discontinued':    <bool>,
            #     'discontinued_date':  <ISO-date | None>,
            #   }
            'lifecycle': consolidated_lifecycle,

            # =================================================================
            # SCOPE SUMMARY (consolidated from VALIDATED members)
            # =================================================================
            # Output of _compute_techstack_scope_summary:
            #   {
            #     'is_company_wide':    <bool>,
            #     'departments_using':  [{id, name}, ...],
            #     'summary_text':       <str | None>,
            #   }
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
            # PAIN-COMPAT KEYS (neutral values for type-agnostic rendering)
            # =================================================================
            'human_impacts':    [],
            'metrics':          [],
            'max_impact_level': None,

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
    # AGGREGATE IMPACTS (VALIDATED parents only)
    # =========================================================================

    @staticmethod
    def _aggregate_impacts(validated_signals: list):
        """
        Aggregate PainImpacts across a cluster's VALIDATED member Pains.

        Returns a 4-tuple:
          human_impacts:      list of {type, count} sorted by count DESC
          metrics:            list of non-empty metric strings
          impacted_contacts:  set of contact IDs (PERSONAL impacts +
                              any impact carrying impacted_contact — but
                              since PainImpact.clean() forbids
                              impacted_contact outside PERSONAL, this
                              resolves to PERSONAL contacts only)
          max_level:          ScopeLevel value (or None) — highest
                              observed rank per _SCOPE_LEVEL_RANK
        """
        human_counter = Counter()
        metrics = []
        impacted_contacts = set()
        max_rank = 0
        max_level_value = None

        for signal in validated_signals:
            for impact in signal.impacts.all():
                # Human impact counter
                if impact.human_impact:
                    human_counter[impact.human_impact] += 1

                # Metric list
                if impact.metric and impact.metric.strip():
                    metrics.append(impact.metric.strip())

                # Impacted contact
                if impact.impacted_contact_id:
                    impacted_contacts.add(impact.impacted_contact_id)

                # Max level
                rank = _SCOPE_LEVEL_RANK.get(impact.level, 0)
                if rank > max_rank:
                    max_rank = rank
                    max_level_value = impact.level

        human_impacts = [
            {'type': impact_type, 'count': count}
            for impact_type, count in human_counter.most_common()
        ]

        return human_impacts, metrics, impacted_contacts, max_level_value

    # =========================================================================
    # AGGREGATE BY LEVEL — detail payload only (Wave A)
    # =========================================================================

    @classmethod
    def _aggregate_by_level(cls, validated_signals: list) -> dict:
        """
        Per-ScopeLevel breakdown of the cluster's VALIDATED PainImpacts.

        Emitted only on cluster detail (never in list) — see
        get_cluster_detail. The breakdown answers the question "at what
        organisational layers is this pain documented, and by which
        parent Pain observations?" without forcing the UI to crawl
        members × impacts.

        Shape
        -----
            {
                "BUSINESS": {
                    "impact_count": N,
                    "parent_pain_ids": [<pain_uuid>, ...],
                },
                "DEPARTMENT": {
                    "<department_uuid>": {
                        "impact_count": N,
                        "parent_pain_ids": [<pain_uuid>, ...],
                        "department": {"id": ..., "name": ...},
                    },
                    ...
                },
                "PERSONAL": {
                    "<contact_uuid>": {
                        "impact_count": N,
                        "parent_pain_ids": [<pain_uuid>, ...],
                        "contact": {
                            "id": ..., "first_name": ..., "last_name": ...,
                            "job_title": ...,
                        },
                    },
                    ...
                },
            }

        Semantics of `parent_pain_ids`
        ------------------------------
        Within a given bucket entry (BUSINESS | DEPARTMENT[dept] |
        PERSONAL[contact]), `parent_pain_ids` lists only the parent Pain
        observations that actually produced an impact at that bucket.
        Example: contact Marie with 2 PERSONAL impacts, one on Pain A
        and one on Pain B in the same cluster → parent_pain_ids = ['A', 'B'].
        This yields an actionable "impacted-by-N-pains" signal on the UI.

        Empty buckets
        -------------
        - `BUSINESS` is always present (impact_count may be 0 with
          an empty parent_pain_ids list) so the UI can render the
          three scope buckets uniformly.
        - `DEPARTMENT` / `PERSONAL` dicts are populated only with keys
          for which at least one impact was recorded — no empty entries.

        Performance
        -----------
        Reads from the same impacts already prefetched by
        _fetch_pain_signals (via `source_activity__contacts` prefetch
        unrelated — this one uses `impacts` prefetch). Zero additional
        DB queries.
        """
        business_entry = {
            'impact_count': 0,
            'parent_pain_ids': [],
        }
        department_entries: dict = {}
        personal_entries: dict = {}

        # Track ordered uniqueness for parent_pain_ids per bucket so the
        # output preserves the natural member order (most recent first,
        # per _fetch_pain_signals default ordering) without duplicates.
        business_seen: set = set()
        department_seen: dict = {}
        personal_seen: dict = {}

        for signal in validated_signals:
            parent_pid = str(signal.id)

            for impact in signal.impacts.all():
                if impact.level == ScopeLevel.BUSINESS:
                    business_entry['impact_count'] += 1
                    if parent_pid not in business_seen:
                        business_seen.add(parent_pid)
                        business_entry['parent_pain_ids'].append(parent_pid)

                elif impact.level == ScopeLevel.DEPARTMENT:
                    dept = impact.impacted_department
                    if not dept:
                        # Defensive — clean() guarantees this is set, but
                        # we skip silently rather than emit a broken key.
                        continue
                    dept_id = str(dept.id)

                    entry = department_entries.get(dept_id)
                    if entry is None:
                        entry = {
                            'impact_count': 0,
                            'parent_pain_ids': [],
                            'department': {
                                'id': dept_id,
                                'name': (
                                    dept.get_name_display()
                                    if hasattr(dept, 'get_name_display')
                                    else str(dept)
                                ),
                            },
                        }
                        department_entries[dept_id] = entry
                        department_seen[dept_id] = set()

                    entry['impact_count'] += 1
                    if parent_pid not in department_seen[dept_id]:
                        department_seen[dept_id].add(parent_pid)
                        entry['parent_pain_ids'].append(parent_pid)

                elif impact.level == ScopeLevel.PERSONAL:
                    contact = impact.impacted_contact
                    if not contact:
                        # Same defensive skip as above.
                        continue
                    contact_id = str(contact.id)

                    entry = personal_entries.get(contact_id)
                    if entry is None:
                        entry = {
                            'impact_count': 0,
                            'parent_pain_ids': [],
                            'contact': {
                                'id': contact_id,
                                'first_name': contact.first_name,
                                'last_name': contact.last_name,
                                'job_title': getattr(
                                    contact, 'job_title', None
                                ),
                            },
                        }
                        personal_entries[contact_id] = entry
                        personal_seen[contact_id] = set()

                    entry['impact_count'] += 1
                    if parent_pid not in personal_seen[contact_id]:
                        personal_seen[contact_id].add(parent_pid)
                        entry['parent_pain_ids'].append(parent_pid)

                # Any other level value is silently ignored; the set of
                # valid levels is enforced upstream by PainImpact.clean().

        return {
            'BUSINESS': business_entry,
            'DEPARTMENT': department_entries,
            'PERSONAL': personal_entries,
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
        was considered but rejected: two Pains confirmed on the same call
        would get identical validated_at timestamps (same audit click),
        which flattens lifecycle signal. created_at reflects when the
        observation entered the system.

        If there is no VALIDATED signal in the cluster, freshness is None
        (no confirmed observation to measure staleness against).

        Active DC exception: if at least one member references a decision
        cycle whose outcome is NULL or ON_HOLD, freshness is clamped to
        DORMANT at worst — never STALE. Rationale: a living deal keeps
        its pain relevant even if the last confirmation is old.
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
    # SCOPE / TARGET-DATE HELPERS — Objective (Wave B)
    # =========================================================================

    @classmethod
    def _compute_max_scope_level(cls, validated_members: list):
        """
        Pick the highest-ranked scope_level across a cluster's VALIDATED
        Objective members.

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
    # (Sprint TechStack)
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
            in Phase 7 (priority bonus).
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
        deal is downgraded to DORMANT — same rule as Pain/Objective).
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

        Priority bucket NOT computed
        ----------------------------
        Computing each Pain cluster's full priority bucket would require
        loading their PainImpacts (used by compute_pain_priority_score).
        That would multiply the query cost. The frontend can fetch full
        Pain cluster detail via /clusters/<canonical_key>/?signal_type=pain
        when it needs the bucket. The cross-reference payload here is
        kept minimal on purpose.

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