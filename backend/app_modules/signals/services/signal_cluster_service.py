# app_modules/signals/services/signal_cluster_service.py
"""
SignalClusterService — aggregate signals into canonical clusters.

A cluster is the set of signals sharing the same canonical_key on a
given account. For Pain in Sprint 2, canonical_key is
    "pain:<WHAT>:<DIMENSION>"
so a cluster corresponds to a distinct pain diagnosis at an account,
regardless of which contact reported it or when.

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

What the service does NOT do
----------------------------
  - It does not write anything.
  - It does not paginate (MVP — acceptable for <100 clusters per account).
  - It does not cache (Sprint 4).
  - It does not cluster PeopleSignal / ObjectiveSignal / TechStackSignal
    — the dispatch on signal_type is a guard for Sprint 2 scope.

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
    ImpactLevel,
    SignalClusterType,
    SignalStatus,
)
from ..models import PainImpact, PainSignal, SignalClusterArchival
from .signal_priority_service import (
    bucket_from_score,
    compute_pain_priority_score,
)


# Ordering used to determine the "max observed" impact level on a cluster.
# BUSINESS > DEPARTMENT > PERSONAL — the strongest evidence wins.
_IMPACT_LEVEL_RANK = {
    ImpactLevel.PERSONAL:   1,
    ImpactLevel.DEPARTMENT: 2,
    ImpactLevel.BUSINESS:   3,
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
        signal_type: str = SignalClusterType.PAIN,
        *,
        decision_cycle_id=None,
        include_archived: bool = False,
    ) -> list:
        """
        Return all clusters for an account, grouped by canonical_key.

        Args:
            account_id:         UUID of the account.
            signal_type:        Cluster signal type. Only 'pain' is
                                supported in Sprint 2 — others raise.
            decision_cycle_id:  Optional UUID. When provided, only clusters
                                having at least one member signal linked
                                to that decision cycle are returned.
            include_archived:   When False (default), archived clusters
                                are excluded from the result. When True,
                                archived clusters are returned with
                                is_archived=True.

        Returns:
            List of cluster dicts, sorted by priority_score DESC.

        Raises:
            StandardizedValidationError if signal_type is not supported.
        """
        cls._assert_pain_only(signal_type)

        signals = cls._fetch_pain_signals(
            account_id=account_id,
            decision_cycle_id=decision_cycle_id,
        )
        grouped = cls._group_by_canonical_key(signals)

        archived_keys = cls._get_archived_keys(account_id, signal_type)

        clusters = []
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
        plus an additional 'members' key holding the PainSignal instances
        (with their impacts prefetched). The calling serializer turns
        members into JSON.

        Args:
            account_id:     UUID of the account.
            canonical_key:  Cluster identifier (e.g. 'pain:OPS:TIME').
            signal_type:    Cluster signal type. Only 'pain' supported.

        Returns:
            Cluster dict with a 'members' key.

        Raises:
            StandardizedValidationError if signal_type is unsupported,
            or if no signals exist for the given (account, canonical_key).
        """
        cls._assert_pain_only(signal_type)

        if not canonical_key:
            raise StandardizedValidationError(
                SignalErrorMessages.CLUSTER_CANONICAL_KEY_REQUIRED
            )

        members = list(
            cls._fetch_pain_signals(account_id=account_id)
            .filter(canonical_key=canonical_key)
        )

        if not members:
            raise StandardizedValidationError(
                SignalErrorMessages.CLUSTER_NOT_FOUND
            )

        cluster = cls._build_pain_cluster(canonical_key, members)

        archived_keys = cls._get_archived_keys(account_id, signal_type)
        cluster['is_archived'] = canonical_key in archived_keys
        cluster['members'] = members

        return cluster

    # =========================================================================
    # GUARD
    # =========================================================================

    @classmethod
    def _assert_pain_only(cls, signal_type: str) -> None:
        """Reject signal types not aggregated in Sprint 2."""
        if signal_type != SignalClusterType.PAIN:
            raise StandardizedValidationError(
                SignalErrorMessages.CLUSTER_SIGNAL_TYPE_INVALID.format(
                    signal_type=signal_type,
                )
            )

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

            # Impacts
            'human_impacts':     human_impacts,
            'metrics':           metrics,
            'max_impact_level':  max_level,

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
          max_level:          ImpactLevel value (or None) — highest
                              observed rank per _IMPACT_LEVEL_RANK
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
                rank = _IMPACT_LEVEL_RANK.get(impact.level, 0)
                if rank > max_rank:
                    max_rank = rank
                    max_level_value = impact.level

        human_impacts = [
            {'type': impact_type, 'count': count}
            for impact_type, count in human_counter.most_common()
        ]

        return human_impacts, metrics, impacted_contacts, max_level_value

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