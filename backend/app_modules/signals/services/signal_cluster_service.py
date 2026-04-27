# app_modules/signals/services/signal_cluster_service.py
"""
SignalClusterService — aggregate signals into canonical clusters.

A cluster is the set of signals sharing the same canonical_key on a
given account. For Pain, canonical_key is
    "pain:<SignalWhat>:<SignalDimension>"
so a cluster corresponds to a distinct pain diagnosis at an account,
regardless of which contact reported it or when. The same canonical
structure will apply to Objective in Wave B —
"objective:<SignalWhat>:<SignalDimension>".

Supported signal types
----------------------
Wave A expanded the signature of list_clusters_for_account to accept
either a single signal_type string or a list. Pain clusters are fully
computed; Objective is accepted at the API surface but yields an empty
result until the Objective port lands in Wave B. All other signal types
(People / TechStack) are rejected by the guard as "not supported".

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
  - It does not cache (Sprint 4).
  - It does not cluster PeopleSignal / TechStackSignal.
  - It does not compute ObjectiveSignal clusters yet — accepted as input
    since Wave A, activated in Wave B.

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
from ..models import ObjectiveSignal, PainImpact, PainSignal, SignalClusterArchival
from .signal_priority_service import (
    OBJECTIVE_TARGET_DATE_SOON_DAYS,
    bucket_from_score,
    compute_objective_priority_score,
    compute_pain_priority_score,
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
        # in Sprint 2; Objective joined in Wave B. Both produce real
        # clusters; the guard above rejects any other type.
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

        # _assert_signal_types_supported guarantees we never reach here.

    # =========================================================================
    # GUARD
    # =========================================================================

    # Signal types the cluster service currently accepts at its API
    # surface. Pain yields real clusters; Objective is accepted but
    # returns empty results until Wave B activates the port.
    _SUPPORTED_CLUSTER_TYPES = frozenset({
        SignalClusterType.PAIN.value,
        SignalClusterType.OBJECTIVE.value,
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
            # signal_type. Mirror of the Pain-compat keys emitted by
            # _build_objective_cluster (human_impacts=[], metrics=[],
            # max_impact_level=None).
            'max_scope_level':       None,
            'target_dates':          [],
            'has_target_date_soon':  False,

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