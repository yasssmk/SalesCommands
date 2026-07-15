# app_modules/bi/signals/cache_invalidation.py
"""
Registry-driven cache invalidation for BI KPIs.

Each KPIDefinition declares `invalidation_sources` (model labels, e.g.
'module_activities.Activity') and `cache_tags` (namespaces its cached value is
keyed under). A write to a source model must bump the tag versions of every
KPI that reads it, so its cached entries go stale.

This mirrors app_modules/activities/signals/cache_invalidation.py:
- guarded by are_signals_disabled() (bulk-op suppression),
- deferred to transaction.on_commit when inside an atomic block,
- bumps tags via invalidate_tag(client_id, namespace) (O(1) tag versioning).

Unlike the per-module receivers, the sender set here is DYNAMIC (derived from
the registry), so receivers are connected programmatically by
connect_invalidation_receivers() — called from BIConfig.ready() after KPI
definitions are discovered. It is idempotent (dispatch_uid per model) and
re-derivable if the registry changes.
"""

from __future__ import annotations

import logging

from django.apps import apps as django_apps
from django.db import transaction
from django.db.models.signals import post_delete, post_save

from core.cache_utils import are_signals_disabled, invalidate_tag

from ..registry import all_kpis

logger = logging.getLogger(__name__)

# model_label -> dispatch_uid, so we can disconnect/reconnect idempotently.
_connected: dict = {}


def build_model_tag_map() -> dict:
    """Aggregate the registry into {model_label: frozenset(tags_to_bump)}.

    A model bumps the union of cache_tags of every KPI that lists it in
    invalidation_sources.
    """
    mapping: dict = {}
    for kpi in all_kpis():
        for source in kpi.invalidation_sources:
            mapping.setdefault(source, set()).update(kpi.cache_tags)
    return {label: frozenset(tags) for label, tags in mapping.items()}


def _bump_tags_after_commit(client_id, tags):
    """Bump `tags` for `client_id`, after commit when inside a transaction."""
    if not client_id or not tags:
        return

    def _do():
        for tag in tags:
            try:
                invalidate_tag(client_id, tag)
            except Exception as e:  # pragma: no cover - defensive
                logger.warning(
                    "BI cache invalidation failed",
                    extra={'client_id': str(client_id), 'tag': tag, 'error': str(e)},
                )
        logger.info(
            "BI KPI cache invalidated (signals)",
            extra={'client_id': str(client_id), 'namespaces': sorted(tags)},
        )

    if transaction.get_connection().in_atomic_block:
        transaction.on_commit(_do)
    else:
        _do()


def _make_receiver(tags):
    """Build a post_save/post_delete receiver that bumps `tags`."""

    def _receiver(sender, instance, **kwargs):
        if are_signals_disabled():
            return
        client_id = getattr(instance, 'client_id', None)
        if not client_id:
            return
        _bump_tags_after_commit(client_id, tags)

    return _receiver


def connect_invalidation_receivers() -> None:
    """(Re)connect BI invalidation receivers from the current registry.

    Idempotent: each source model gets one post_save + one post_delete
    receiver keyed by dispatch_uid; a prior binding is disconnected first so a
    changed registry re-wires cleanly.
    """
    mapping = build_model_tag_map()
    for model_label, tags in mapping.items():
        try:
            model = django_apps.get_model(model_label)
        except Exception:
            logger.warning(
                "BI invalidation: unknown model, skipped",
                extra={'model_label': model_label},
            )
            continue

        uid = f"bi_invalidation:{model_label}"
        # Disconnect any prior binding, then connect the fresh receiver.
        post_save.disconnect(dispatch_uid=uid, sender=model)
        post_delete.disconnect(dispatch_uid=uid, sender=model)

        receiver = _make_receiver(tags)
        post_save.connect(receiver, sender=model, dispatch_uid=uid, weak=False)
        post_delete.connect(receiver, sender=model, dispatch_uid=uid, weak=False)
        _connected[model_label] = uid


def disconnect_invalidation_receivers() -> None:
    """Disconnect all BI invalidation receivers (test hygiene / re-wiring)."""
    for model_label, uid in list(_connected.items()):
        try:
            model = django_apps.get_model(model_label)
        except Exception:
            continue
        post_save.disconnect(dispatch_uid=uid, sender=model)
        post_delete.disconnect(dispatch_uid=uid, sender=model)
    _connected.clear()
