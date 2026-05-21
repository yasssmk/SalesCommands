# app_modules/signals/signals/cache_invalidation.py
"""
Cache invalidation Django signals for the Signals module.

Automatically invalidates the 'signals' and 'signal_clusters' cache tags
when a signal model (PainSignal, ObjectiveSignal, ImpactSignal,
TechStackSignal), a PainImpact, or a SignalClusterArchival is created,
updated, or deleted.

This is a safety net: ViewSets already call invalidate_tag() directly on
every write path. These receivers catch writes made outside a ViewSet
(admin, management commands, direct ORM calls from other services).

Invalidation matrix
-------------------
See app_modules.signals.constants for the canonical matrix. Summary:

  Write on                  signals   signal_clusters
  ---------------------    -------   ---------------
  PainSignal                  ✓             ✓
  ObjectiveSignal             ✓             ✗
  ImpactSignal                ✓             ✓
  TechStackSignal             ✓             ✗
  PainImpact (legacy)         ✓             ✓
  SignalClusterArchival       ✗             ✓   (archival-only)

Cluster-tag invalidation rule
-----------------------------
A signal type busts SIGNAL_CLUSTERS_CACHE_TAG iff it produces clusters
whose aggregated stats (priority_score, freshness_status,
confirmation_count, scope summaries) depend on the write. Pain,
Impact, and PainImpact (legacy) match; Objective and TechStack
clusters exist too but Objective writes don't change anything beyond
the signal itself, and TechStack invalidation is currently scoped to
the signals tag (Sprint TechStack decision — to revisit if cluster
caches diverge).

Signal control
--------------
Each receiver checks are_signals_disabled() before executing. Prevents N
signal calls during bulk operations wrapped in disable_signals() /
disable_signals_with_invalidation().
"""

import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.cache_utils import are_signals_disabled, invalidate_tag

from ..constants import SIGNAL_CLUSTERS_CACHE_TAG, SIGNALS_CACHE_TAG

logger = logging.getLogger(__name__)


# =============================================================================
# HELPERS — invalidation after transaction commit
# =============================================================================

def _invalidate_signals_after_commit(client_id: str) -> None:
    """
    Invalidate the 'signals' cache tag after transaction commit.

    Defers invalidation to after commit when inside an atomic block,
    ensuring the cache is only busted once the DB write is durable.
    """
    if not client_id:
        return

    def _do_invalidate():
        try:
            invalidate_tag(client_id, SIGNALS_CACHE_TAG)
            logger.info(
                "signals_cache_invalidated",
                extra={
                    'client_id': str(client_id),
                    'namespace': SIGNALS_CACHE_TAG,
                },
            )
        except Exception as exc:
            logger.warning(
                "signals_cache_invalidation_failed",
                extra={
                    'client_id': str(client_id),
                    'namespace': SIGNALS_CACHE_TAG,
                    'error': str(exc),
                },
                exc_info=False,
            )

    if transaction.get_connection().in_atomic_block:
        transaction.on_commit(_do_invalidate)
    else:
        _do_invalidate()


def _invalidate_clusters_after_commit(client_id: str) -> None:
    """
    Invalidate the 'signal_clusters' cache tag after transaction commit.

    Called in addition to _invalidate_signals_after_commit for any write
    that affects cluster membership or aggregated cluster stats (Pain +
    PainImpact), or called alone for SignalClusterArchival writes.
    """
    if not client_id:
        return

    def _do_invalidate():
        try:
            invalidate_tag(client_id, SIGNAL_CLUSTERS_CACHE_TAG)
            logger.info(
                "signal_clusters_cache_invalidated",
                extra={
                    'client_id': str(client_id),
                    'namespace': SIGNAL_CLUSTERS_CACHE_TAG,
                },
            )
        except Exception as exc:
            logger.warning(
                "signal_clusters_cache_invalidation_failed",
                extra={
                    'client_id': str(client_id),
                    'namespace': SIGNAL_CLUSTERS_CACHE_TAG,
                    'error': str(exc),
                },
                exc_info=False,
            )

    if transaction.get_connection().in_atomic_block:
        transaction.on_commit(_do_invalidate)
    else:
        _do_invalidate()


# =============================================================================
# PAIN SIGNAL — invalidates 'signals' AND 'signal_clusters'
# =============================================================================

@receiver(post_save, sender='module_signals.PainSignal')
def invalidate_on_pain_save(sender, instance, **kwargs):
    """
    Invalidate both signal and cluster caches when a PainSignal is saved.

    Cluster membership, priority_score, freshness_status, and
    confirmation_count all derive from the set of PainSignals sharing a
    canonical_key on an account — so any write here must bust cluster
    caches.
    """
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if not client_id:
        return
    _invalidate_signals_after_commit(str(client_id))
    _invalidate_clusters_after_commit(str(client_id))


@receiver(post_delete, sender='module_signals.PainSignal')
def invalidate_on_pain_delete(sender, instance, **kwargs):
    """Invalidate both caches when a PainSignal is deleted."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if not client_id:
        return
    _invalidate_signals_after_commit(str(client_id))
    _invalidate_clusters_after_commit(str(client_id))


# =============================================================================
# OBJECTIVE SIGNAL — invalidates 'signals' only
# =============================================================================

@receiver(post_save, sender='module_signals.ObjectiveSignal')
def invalidate_on_objective_save(sender, instance, **kwargs):
    """Invalidate signal caches when an ObjectiveSignal is saved."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if client_id:
        _invalidate_signals_after_commit(str(client_id))


@receiver(post_delete, sender='module_signals.ObjectiveSignal')
def invalidate_on_objective_delete(sender, instance, **kwargs):
    """Invalidate signal caches when an ObjectiveSignal is deleted."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if client_id:
        _invalidate_signals_after_commit(str(client_id))

# =============================================================================
# IMPACT SIGNAL — invalidates 'signals' AND 'signal_clusters'
# =============================================================================
#
# ImpactSignal produces clusters on the same canonical (what × dimension)
# axes as Pain. Cluster membership, priority_score, freshness_status,
# confirmation_count, and max_scope_level all derive from the set of
# ImpactSignals sharing a canonical_key on an account — so any write
# here must bust cluster caches too. Same stance as PainSignal.
# =============================================================================

@receiver(post_save, sender='module_signals.ImpactSignal')
def invalidate_on_impact_save(sender, instance, **kwargs):
    """
    Invalidate both signal and cluster caches when an ImpactSignal is saved.

    Cluster membership, priority_score, freshness_status,
    confirmation_count, and max_scope_level all derive from the set
    of ImpactSignals sharing a canonical_key on an account — so any
    write here must bust cluster caches.
    """
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if not client_id:
        return
    _invalidate_signals_after_commit(str(client_id))
    _invalidate_clusters_after_commit(str(client_id))


@receiver(post_delete, sender='module_signals.ImpactSignal')
def invalidate_on_impact_delete(sender, instance, **kwargs):
    """Invalidate both caches when an ImpactSignal is deleted."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if not client_id:
        return
    _invalidate_signals_after_commit(str(client_id))
    _invalidate_clusters_after_commit(str(client_id))


# =============================================================================
# TECH STACK SIGNAL — invalidates 'signals' only
# =============================================================================

@receiver(post_save, sender='module_signals.TechStackSignal')
def invalidate_on_tech_stack_save(sender, instance, **kwargs):
    """Invalidate signal caches when a TechStackSignal is saved."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if client_id:
        _invalidate_signals_after_commit(str(client_id))


@receiver(post_delete, sender='module_signals.TechStackSignal')
def invalidate_on_tech_stack_delete(sender, instance, **kwargs):
    """Invalidate signal caches when a TechStackSignal is deleted."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if client_id:
        _invalidate_signals_after_commit(str(client_id))


# =============================================================================
# PAIN IMPACT — PIVOT: invalidates 'signals' AND 'signal_clusters'
# =============================================================================
#
# PainImpact has no lifecycle of its own (no BaseSignal inheritance), but
# it is the pivot entity that drives cluster aggregated stats:
#   - human_impacts distribution
#   - metrics list
#   - impacted_contacts_count
#   - max_impact_level
#
# A write on a PainImpact therefore must invalidate BOTH:
#   - 'signals'          — because PainSignal detail reads nest impacts
#   - 'signal_clusters'  — because cluster serializers compute stats
#                          from the parent pain's impacts set
# =============================================================================

@receiver(post_save, sender='module_signals.PainImpact')
def invalidate_on_pain_impact_save(sender, instance, **kwargs):
    """Invalidate both caches when a PainImpact is saved."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if not client_id:
        return
    _invalidate_signals_after_commit(str(client_id))
    _invalidate_clusters_after_commit(str(client_id))


@receiver(post_delete, sender='module_signals.PainImpact')
def invalidate_on_pain_impact_delete(sender, instance, **kwargs):
    """Invalidate both caches when a PainImpact is deleted."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if not client_id:
        return
    _invalidate_signals_after_commit(str(client_id))
    _invalidate_clusters_after_commit(str(client_id))


# =============================================================================
# SIGNAL CLUSTER ARCHIVAL — invalidates 'signal_clusters' only
# =============================================================================
#
# Archive / unarchive toggles only affect cluster visibility in list views
# (the include_archived=false default). They do not change any signal
# data, so the 'signals' tag does not need to be busted — hence the
# single-tag invalidation here.
#
# NB: both archive (create new row) and unarchive (patch unarchived_at)
# flow through post_save. post_delete is wired as a defensive catch in
# case a row is ever removed by an admin or migration.
# =============================================================================

@receiver(post_save, sender='module_signals.SignalClusterArchival')
def invalidate_on_cluster_archival_save(sender, instance, **kwargs):
    """Invalidate cluster caches when an archival row is created/updated."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if client_id:
        _invalidate_clusters_after_commit(str(client_id))


@receiver(post_delete, sender='module_signals.SignalClusterArchival')
def invalidate_on_cluster_archival_delete(sender, instance, **kwargs):
    """Invalidate cluster caches when an archival row is deleted."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if client_id:
        _invalidate_clusters_after_commit(str(client_id))