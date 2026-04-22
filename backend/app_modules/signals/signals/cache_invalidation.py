# app_modules/signals/signals/cache_invalidation.py

"""
Cache invalidation Django signals for the Signals module.
Automatically invalidates the 'signals' cache tag when a
PeopleSignal, PainSignal, ObjectiveSignal, or TechStackSignal
is created, updated, or deleted.

This is a safety net: the ViewSet already calls invalidate_tag() directly
on every write path. These receivers catch writes made outside the ViewSet
(admin, management commands, direct ORM calls from other services).

Signal control:
  - Each receiver checks are_signals_disabled() before executing.
  - Prevents N signal calls during bulk operations wrapped in
    disable_signals() / disable_signals_with_invalidation().

Invalidates:
  - 'signals' tag — all signal list/detail/filtered caches
"""

import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.cache_utils import are_signals_disabled, invalidate_tag

logger = logging.getLogger(__name__)


def _invalidate_after_commit(client_id: str) -> None:
    """
    Invalidate signal cache tags after transaction commit.

    Defers invalidation to after commit when inside an atomic block,
    ensuring cache is only busted after the DB write is durable.
    """
    if not client_id:
        return

    def _do_invalidate():
        try:
            invalidate_tag(client_id, 'signals')
            logger.info(
                "signals_cache_invalidated",
                extra={
                    'client_id': str(client_id),
                    'namespace': 'signals',
                },
            )
        except Exception as exc:
            logger.warning(
                "signals_cache_invalidation_failed",
                extra={'client_id': str(client_id), 'error': str(exc)},
                exc_info=False,
            )

    if transaction.get_connection().in_atomic_block:
        transaction.on_commit(_do_invalidate)
    else:
        _do_invalidate()


# =============================================================================
# PEOPLE SIGNAL
# =============================================================================

@receiver(post_save, sender='module_signals.PeopleSignal')
def invalidate_on_people_save(sender, instance, **kwargs):
    """Invalidate signal caches when a PeopleSignal is saved."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if client_id:
        _invalidate_after_commit(str(client_id))

@receiver(post_delete, sender='module_signals.PeopleSignal')
def invalidate_on_people_delete(sender, instance, **kwargs):
    """Invalidate signal caches when a PeopleSignal is deleted."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if client_id:
        _invalidate_after_commit(str(client_id))


# =============================================================================
# PAIN SIGNAL
# =============================================================================

@receiver(post_save, sender='module_signals.PainSignal')
def invalidate_on_pain_save(sender, instance, **kwargs):
    """Invalidate signal caches when a PainSignal is saved."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if client_id:
        _invalidate_after_commit(str(client_id))

@receiver(post_delete, sender='module_signals.PainSignal')
def invalidate_on_pain_delete(sender, instance, **kwargs):
    """Invalidate signal caches when a PainSignal is deleted."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if client_id:
        _invalidate_after_commit(str(client_id))


# =============================================================================
# OBJECTIVE SIGNAL
# =============================================================================

@receiver(post_save, sender='module_signals.ObjectiveSignal')
def invalidate_on_objective_save(sender, instance, **kwargs):
    """Invalidate signal caches when an ObjectiveSignal is saved."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if client_id:
        _invalidate_after_commit(str(client_id))

@receiver(post_delete, sender='module_signals.ObjectiveSignal')
def invalidate_on_objective_delete(sender, instance, **kwargs):
    """Invalidate signal caches when an ObjectiveSignal is deleted."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if client_id:
        _invalidate_after_commit(str(client_id))
# =============================================================================
# TECH STACK SIGNAL
# =============================================================================

@receiver(post_save, sender='module_signals.TechStackSignal')
def invalidate_on_tech_stack_save(sender, instance, **kwargs):
    """Invalidate signal caches when a TechStackSignal is saved."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if client_id:
        _invalidate_after_commit(str(client_id))


@receiver(post_delete, sender='module_signals.TechStackSignal')
def invalidate_on_tech_stack_delete(sender, instance, **kwargs):
    """Invalidate signal caches when a TechStackSignal is deleted."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if client_id:
        _invalidate_after_commit(str(client_id))


# =============================================================================
# PAIN IMPACT
# =============================================================================
#
# PainImpact has no lifecycle of its own (no BaseSignal inheritance), but
# it still shares the 'signals' cache tag with its parent pain for reads.
# A create/update/delete on a PainImpact should invalidate the same cache
# namespace so that list views of PainSignal (which nest 'impacts') reflect
# the change on next read.
# =============================================================================

@receiver(post_save, sender='module_signals.PainImpact')
def invalidate_on_pain_impact_save(sender, instance, **kwargs):
    """Invalidate signal caches when a PainImpact is saved."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if client_id:
        _invalidate_after_commit(str(client_id))


@receiver(post_delete, sender='module_signals.PainImpact')
def invalidate_on_pain_impact_delete(sender, instance, **kwargs):
    """Invalidate signal caches when a PainImpact is deleted."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, 'client_id', None)
    if client_id:
        _invalidate_after_commit(str(client_id))