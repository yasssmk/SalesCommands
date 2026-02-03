# app_modules/activities/signals/cache_invalidation.py
"""
Cache invalidation signals for Activity module.

Automatically invalidates cache when Activities are created, updated, or deleted.
Uses tag versioning strategy for O(1) Redis-safe invalidation.

This is a safety net: ViewSet hooks already call _invalidate_activity_caches(),
but signals catch modifications made outside the ViewSet (admin, management
commands, other services, direct ORM usage).

Signal Control:
- Signals can be temporarily disabled during bulk operations using disable_signals()
- Each receiver checks are_signals_disabled() before executing
- Prevents N signal calls when processing N objects in bulk

Invalidates:
- 'activities' tag (all activity list/detail/filtered caches)
- 'accounts' tag (workspace stats depend on activity data)
- 'decision_cycles' tag (timeline displays activities per step)
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from core.cache_utils import invalidate_tag, are_signals_disabled
import logging

logger = logging.getLogger(__name__)


def _invalidate_activities_after_commit(client_id):
    """
    Invalidate activity-related cache tags after transaction commit.

    Defers invalidation to after commit when inside an atomic block,
    ensuring cache is only invalidated after successful DB write.
    """
    if not client_id:
        return

    def _do_invalidate():
        try:
            invalidate_tag(client_id, 'activities')
            invalidate_tag(client_id, 'accounts')
            invalidate_tag(client_id, 'decision_cycles')
            logger.info(
                "Activities cache invalidated (signals)",
                extra={
                    "client_id": str(client_id),
                    "namespaces": ["activities", "accounts", "decision_cycles"],
                }
            )
        except Exception as e:
            logger.warning(f"Failed to invalidate cache (signals): {e}", exc_info=False)

    if transaction.get_connection().in_atomic_block:
        transaction.on_commit(_do_invalidate)
    else:
        _do_invalidate()


# ========================= ACTIVITIES =========================

@receiver(post_save, sender='module_activities.Activity')
def invalidate_activities_cache_on_save(sender, instance, created, **kwargs):
    """Invalidate activity caches when an Activity is created or updated."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, "client_id", None)
    if not client_id:
        return
    _invalidate_activities_after_commit(client_id)


@receiver(post_delete, sender='module_activities.Activity')
def invalidate_activities_cache_on_delete(sender, instance, **kwargs):
    """Invalidate activity caches when an Activity is deleted."""
    if are_signals_disabled():
        return
    client_id = getattr(instance, "client_id", None)
    if not client_id:
        return
    _invalidate_activities_after_commit(client_id)