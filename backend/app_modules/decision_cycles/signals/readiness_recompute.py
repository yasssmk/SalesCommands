# app_modules/decision_cycles/signals/readiness_recompute.py
"""
Auto-recompute readiness_score on DecisionCycle when impacting models change.

Mirrors the pattern in app_modules/signals/signals/cache_invalidation.py:
  - @receiver(post_save / post_delete) with string sender
  - are_signals_disabled() guard
  - transaction.on_commit() for deferred execution

Trigger matrix (from ReadinessScoreService._evaluate_dimensions):

  Model               Dimension(s)
  ----------------    -------------------------
  PainSignal          pain
  ObjectiveSignal     objective
  ImpactSignal        impact
  PeopleSignal        decision_maker, champion
  BlockerSignal       risk
  ConstraintSignal    risk
  DealProduct         solution
  Activity            momentum
"""

import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.cache_utils import are_signals_disabled

logger = logging.getLogger(__name__)


# =============================================================================
# HELPER — resolve DC and recompute after commit
# =============================================================================

def _recompute_after_commit(decision_cycle):
    """Schedule readiness recompute after transaction commit."""
    if decision_cycle is None:
        return

    cycle_id = decision_cycle.pk

    def _do_recompute():
        try:
            from app_modules.decision_cycles.models import DecisionCycle
            from app_modules.decision_cycles.services.readiness_score_service import (
                ReadinessScoreService,
            )
            try:
                cycle = DecisionCycle.objects.get(pk=cycle_id)
            except DecisionCycle.DoesNotExist:
                return
            ReadinessScoreService.recompute_and_store(cycle)
            logger.info(
                "readiness_score_recomputed",
                extra={'cycle_id': str(cycle_id)},
            )
        except Exception as exc:
            logger.warning(
                "readiness_score_recompute_failed",
                extra={'cycle_id': str(cycle_id), 'error': str(exc)},
                exc_info=False,
            )

    if transaction.get_connection().in_atomic_block:
        transaction.on_commit(_do_recompute)
    else:
        _do_recompute()


def _handle_signal_change(instance):
    """Common handler for signal models that have a decision_cycle FK."""
    if are_signals_disabled():
        return
    dc = getattr(instance, 'decision_cycle', None)
    if dc is not None:
        _recompute_after_commit(dc)


def _handle_activity_change(instance):
    """Handler for Activity model (decision_cycle FK is nullable)."""
    if are_signals_disabled():
        return
    dc = getattr(instance, 'decision_cycle', None)
    if dc is not None:
        _recompute_after_commit(dc)


# =============================================================================
# PAIN SIGNAL
# =============================================================================

@receiver(post_save, sender='module_signals.PainSignal')
def recompute_on_pain_save(sender, instance, **kwargs):
    _handle_signal_change(instance)


@receiver(post_delete, sender='module_signals.PainSignal')
def recompute_on_pain_delete(sender, instance, **kwargs):
    _handle_signal_change(instance)


# =============================================================================
# OBJECTIVE SIGNAL
# =============================================================================

@receiver(post_save, sender='module_signals.ObjectiveSignal')
def recompute_on_objective_save(sender, instance, **kwargs):
    _handle_signal_change(instance)


@receiver(post_delete, sender='module_signals.ObjectiveSignal')
def recompute_on_objective_delete(sender, instance, **kwargs):
    _handle_signal_change(instance)


# =============================================================================
# IMPACT SIGNAL
# =============================================================================

@receiver(post_save, sender='module_signals.ImpactSignal')
def recompute_on_impact_save(sender, instance, **kwargs):
    _handle_signal_change(instance)


@receiver(post_delete, sender='module_signals.ImpactSignal')
def recompute_on_impact_delete(sender, instance, **kwargs):
    _handle_signal_change(instance)


# =============================================================================
# PEOPLE SIGNAL
# =============================================================================

@receiver(post_save, sender='module_signals.PeopleSignal')
def recompute_on_people_save(sender, instance, **kwargs):
    _handle_signal_change(instance)


@receiver(post_delete, sender='module_signals.PeopleSignal')
def recompute_on_people_delete(sender, instance, **kwargs):
    _handle_signal_change(instance)


# =============================================================================
# BLOCKER SIGNAL
# =============================================================================

@receiver(post_save, sender='module_signals.BlockerSignal')
def recompute_on_blocker_save(sender, instance, **kwargs):
    _handle_signal_change(instance)


@receiver(post_delete, sender='module_signals.BlockerSignal')
def recompute_on_blocker_delete(sender, instance, **kwargs):
    _handle_signal_change(instance)


# =============================================================================
# CONSTRAINT SIGNAL
# =============================================================================

@receiver(post_save, sender='module_signals.ConstraintSignal')
def recompute_on_constraint_save(sender, instance, **kwargs):
    _handle_signal_change(instance)


@receiver(post_delete, sender='module_signals.ConstraintSignal')
def recompute_on_constraint_delete(sender, instance, **kwargs):
    _handle_signal_change(instance)


# =============================================================================
# DEAL PRODUCT
# =============================================================================

@receiver(post_save, sender='decision_cycles.DealProduct')
def recompute_on_deal_product_save(sender, instance, **kwargs):
    _handle_signal_change(instance)


@receiver(post_delete, sender='decision_cycles.DealProduct')
def recompute_on_deal_product_delete(sender, instance, **kwargs):
    _handle_signal_change(instance)


# =============================================================================
# ACTIVITY
# =============================================================================

@receiver(post_save, sender='module_activities.Activity')
def recompute_on_activity_save(sender, instance, **kwargs):
    _handle_activity_change(instance)


@receiver(post_delete, sender='module_activities.Activity')
def recompute_on_activity_delete(sender, instance, **kwargs):
    _handle_activity_change(instance)
