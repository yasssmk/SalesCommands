# app_modules/signals/services/signal_cluster_service.py
"""
SignalClusterService — aggregate signals into canonical clusters.

A cluster is the set of signals sharing the same canonical_key on a
given account. The canonical_key format depends on the signal type:

    Pain        — "pain:<SignalWhat>:<SignalDimension>"
    Objective   — "objective:<SignalWhat>:<SignalDimension>"
    Impact      — "impact:<SignalWhat>:<SignalDimension>"

A Pain cluster corresponds to a distinct pain diagnosis at an account,
regardless of which contact reported it or when. The same logic
applies to Objective and Impact on their respective canonical
identities.

TechStack is NOT clustered (product decision) — it is not handled by
this service; TechStack observations are read as a flat, catalog-
grouped list elsewhere.

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
or a list. Pain, Objective, and Impact produce real clusters. Any
other signal_type value (including tech_stack — not clusterable) is
rejected by the guard as "not supported".

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
          Impact:    max_scope_level)
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
        'signal_type':          'pain' | 'objective' | 'impact',
        'what':                 'OPS',
        'what_display':         'Operations / Process',
        'dimension':            'TIME',
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
from ..models import ImpactSignal, ObjectiveSignal, PainSignal, SignalClusterArchival
from .signal_priority_service import (
    OBJECTIVE_TARGET_DATE_SOON_DAYS,
    bucket_from_score,
    compute_impact_priority_score,
    compute_objective_priority_score,
    compute_pain_priority_score,
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
                                'impact') or a list/tuple of strings for
                                mixed queries.
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
                       Impact) — turned into JSON by the calling
                       serializer.

        Args:
            account_id:     UUID of the account.
            canonical_key:  Cluster identifier (e.g. 'pain:OPS:TIME').
            signal_type:    Cluster signal type — single string
                            ('pain', 'objective', or 'impact').

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

        # Dispatch per signal type. Pain, Objective, and Impact produce
        # real cluster detail payloads.
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

        # _assert_signal_types_supported guarantees we never reach here.

    # =========================================================================
    # GUARD
    # =========================================================================

    # Signal types the cluster service accepts at its API surface. Pain,
    # Objective, and Impact share the same canonical-axes mechanism
    # (what × dimension). TechStack is intentionally NOT here: it is not
    # clusterable (product decision), so any request for tech_stack
    # clusters is rejected by _assert_signal_types_supported.
    _SUPPORTED_CLUSTER_TYPES = frozenset({
        SignalClusterType.PAIN.value,
        SignalClusterType.OBJECTIVE.value,
        SignalClusterType.IMPACT.value,
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
                # Join path for the cluster `departments` aggregate — avoids
                # one query per member when reading member.target_department.
                'target_department',
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
        product rule as Pain / Objective).

        ImpactSignal carries no Impact-specific FK (no equivalent to
        Objective's target_contact / target_department).
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
                # Join path for the cluster `departments` aggregate.
                'target_department',
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
    # BUILD — per Pain cluster
    # =========================================================================

    @classmethod
    def _build_pain_cluster(cls, canonical_key: str, members: list) -> dict:
        """
        Build the Pain cluster dict from a list of PainSignal members.

        `members` includes VALIDATED and PENDING signals for the same
        canonical_key on the same account. REJECTED are not in `members`.

        Output shape — aligned with Objective and Impact on shared keys
        (identity, corroboration, status, lifecycle, priority, archival).
        Pain-specific additions beyond the common keys:
          - max_scope_level (the layer at which the pain is felt, read
                              directly from PainSignal.scope_level)

        Objective-compat keys are emitted with neutral values so the
        unified cluster serializer can render any cluster type uniformly
        without branching on signal_type.

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
        # carry a source_contact FK. Mirrors Objective / Impact.
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

            # Temporal density — raw facts (count + covered period), NOT a
            # composite score. period_start/period_end mirror the lifecycle
            # window; span_days is the whole-day difference between them.
            'signal_count':  len(members),
            'period_start':  first_observed_at,
            'period_end':    last_confirmed_at,
            'span_days':     cls._compute_span_days(
                first_observed_at, last_confirmed_at,
            ),

            # Departments involved — distinct target_department across members
            # (factual list of {id, name}; empty when all members are BUSINESS).
            'departments':   cls._compute_departments(members),

            # Scope (shared shape with Objective and Impact via
            # max_scope_level key)
            'max_scope_level': max_scope_level,

            # Objective-compat keys — neutral values for type-agnostic
            # frontend rendering.
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
        # derived from activity.contacts. Mirrors Pain / Impact.
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

            # Temporal density — raw facts (count + covered period), NOT a
            # composite score. period_start/period_end mirror the lifecycle
            # window; span_days is the whole-day difference between them.
            'signal_count':  len(members),
            'period_start':  first_observed_at,
            'period_end':    last_confirmed_at,
            'span_days':     cls._compute_span_days(
                first_observed_at, last_confirmed_at,
            ),

            # Departments involved — distinct target_department across members
            # (factual list of {id, name}; empty when all members are BUSINESS).
            'departments':   cls._compute_departments(members),

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
        # carry a source_contact FK. Mirrors Pain / Objective.
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

            # Temporal density — raw facts (count + covered period), NOT a
            # composite score. period_start/period_end mirror the lifecycle
            # window; span_days is the whole-day difference between them.
            'signal_count':  len(members),
            'period_start':  first_observed_at,
            'period_end':    last_confirmed_at,
            'span_days':     cls._compute_span_days(
                first_observed_at, last_confirmed_at,
            ),

            # Departments involved — distinct target_department across members
            # (factual list of {id, name}; empty when all members are BUSINESS).
            'departments':   cls._compute_departments(members),

            # Scope (shared shape with Pain and Objective via
            # max_scope_level key)
            'max_scope_level': max_scope_level,

            # Objective-compat keys — Impact has no target_date concept.
            # Emitted as neutral values for type-agnostic frontend
            # rendering.
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

    @staticmethod
    def _compute_departments(members: list) -> list:
        """
        Distinct target_department values across the cluster's members, as a
        factual list of compact {id, name} dicts (NOT a score). Members with
        no department (BUSINESS scope) do not contribute. Order is stable and
        deterministic: departments appear in order of first appearance
        (oldest member first), independent of the fetch ordering.

        Reuses the compact target_department shape used by the signal
        serializers ({id: str, name: display}). N+1-safe: target_department is
        select_related in every cluster fetch, so no extra query per member.
        """
        seen = set()
        departments = []
        for member in sorted(members, key=lambda m: m.created_at):
            dept = member.target_department
            if dept is None:
                continue
            if dept.id in seen:
                continue
            seen.add(dept.id)
            departments.append({
                'id':   str(dept.id),
                'name': dept.get_name_display(),
            })
        return departments

    @staticmethod
    def _compute_span_days(period_start, period_end) -> int:
        """
        Factual number of days covered by the cluster: the whole-day
        difference between the earliest and the latest observation.

        This is a raw fact (period_end - period_start), NOT a weighted
        score. It is 0 for a single-signal cluster, for a same-day
        cluster, and whenever either endpoint is missing (no VALIDATED
        member, so no confirmed observation window to measure).

        Reuses the period endpoints already produced by
        _compute_lifecycle — no extra query, no re-derivation from the
        members.
        """
        if period_start is None or period_end is None:
            return 0
        return (period_end - period_start).days

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
