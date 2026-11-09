# app_modules/activities/signals/signal_cycle_attachment.py
"""
Sprint « Cycle de vie des contacts », étape 2 -- an activity linked to a
decision cycle gives that cycle to its signals.

The ONE place every write path goes through (Activity.save): the POST
(ActivityCreateSerializer), the PATCH (ActivityUpdateSerializer),
create-with-entities (« Start Decision Cycle », 5.13). pre_save stashes the
previous decision_cycle_id (the 5.14a / readiness_recompute pattern);
post_save runs services.signal_cycle_attachment only when the cycle is SET
or CHANGES -- a re-save never re-runs it, an activity that LEAVES its cycle
touches nothing. Respects are_signals_disabled().
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from core.cache_utils import are_signals_disabled


@receiver(pre_save, sender='module_activities.Activity')
def capture_old_cycle_for_signal_attachment(sender, instance, **kwargs):
    """Stash the previous decision_cycle_id so post_save sees the transition."""
    if are_signals_disabled():
        return
    instance._old_cycle_for_signals = (
        sender.objects.filter(pk=instance.pk)
        .values_list('decision_cycle_id', flat=True)
        .first()
        if instance.pk else None
    )


@receiver(post_save, sender='module_activities.Activity')
def attach_signals_on_cycle_link(sender, instance, created, **kwargs):
    """The activity's cycle was set or changed: its signals take it."""
    if are_signals_disabled() or not instance.decision_cycle_id:
        return
    previous = getattr(instance, '_old_cycle_for_signals', None)
    if not created and previous == instance.decision_cycle_id:
        return

    from app_modules.signals.services.signal_cycle_attachment import (
        attach_signals_to_activity_cycle,
    )
    attach_signals_to_activity_cycle(instance)
