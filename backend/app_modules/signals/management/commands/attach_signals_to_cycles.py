# app_modules/signals/management/commands/attach_signals_to_cycles.py
"""
Sprint « Cycle de vie des contacts », étape 2 -- give their decision cycle to
the EXISTING signals that should have it.

The runtime is fixed (the Activity post_save,
services/signal_cycle_attachment.py); this command fixes the existing data
with the SAME rules, for every activity linked to a cycle (oldest first):
its own signals, plus -- when it was created from a campaign activity -- the
signals of the whole campaign_account sequence, whose decision_cycle is NULL.
The excluded signal types are the service's EXCLUDED_SIGNAL_TYPES (today
next_step and, temporarily, tech_stack); a signal already on another cycle
is never moved (counted as "kept").

Oldest activity first: when two cycles were born from the same
campaign_account, the FIRST one takes the sequence (born_decision_cycle
rule). Run with --dry-run first: it lists, per tenant, what WOULD be
attached, deduplicated per signal, and writes nothing. Re-runnable: a second
run finds nothing.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from app_modules.activities.models import Activity
from app_modules.signals.services.signal_cycle_attachment import (
    _attachable_models,
    attach_signals_to_activity_cycle,
    source_activity_ids,
)


class Command(BaseCommand):
    help = (
        'Attach the existing signals to the decision cycle of their activity '
        '(and of the cycle born from their campaign_account sequence). Use '
        '--dry-run first.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List, per tenant, what would change without writing to the DB.',
        )
        parser.add_argument(
            '--client-id',
            help='Limit to one tenant (client_id UUID).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        activities = (
            Activity.objects
            .filter(decision_cycle__isnull=False)
            .only('id', 'client_id', 'title', 'decision_cycle_id', 'source_activity_id')
            .order_by('client_id', 'created_at', 'id')
        )
        if options.get('client_id'):
            activities = activities.filter(client_id=options['client_id'])

        mode = 'DRY RUN — nothing written' if dry_run else 'APPLY'
        self.stdout.write(f'attach_signals_to_cycles: {mode}')

        claimed = {signal_type: set() for signal_type, _ in _attachable_models()}
        kept_seen = {signal_type: set() for signal_type, _ in _attachable_models()}
        totals = {}
        current_tenant = None
        touched = 0
        for activity in activities.iterator():
            if dry_run:
                attached, kept = self._plan(activity, claimed, kept_seen)
            else:
                with transaction.atomic():
                    result = attach_signals_to_activity_cycle(activity)
                attached, kept = result.attached, result.kept_on_other_cycle
            if not attached and not kept:
                continue
            if activity.client_id != current_tenant:
                current_tenant = activity.client_id
                self.stdout.write(f'\nTenant {current_tenant}')
            touched += 1
            verb = 'would attach' if dry_run else 'attached'
            self.stdout.write(
                f'  activity {activity.id} "{activity.title}" -> cycle '
                f'{activity.decision_cycle_id}: {verb} {attached or "nothing"}'
                + (f' ; kept on another cycle {kept}' if kept else '')
            )
            for signal_type, n in attached.items():
                totals[signal_type] = totals.get(signal_type, 0) + n

        if not touched:
            self.stdout.write('No signal to attach.')
            return
        verb = 'would be attached' if dry_run else 'attached'
        self.stdout.write(
            f'\n{sum(totals.values())} signal(s) {verb} — per type: {totals}'
        )

    @staticmethod
    def _plan(activity, claimed, kept_seen):
        """Dry run: the orphan signals this activity would take, deduplicated
        against the ones an older activity already claimed."""
        ids = source_activity_ids(activity)
        attached, kept = {}, {}
        for signal_type, model in _attachable_models():
            scoped = model.objects.filter(
                client_id=activity.client_id, source_activity_id__in=ids,
            )
            orphan_ids = set(
                scoped.filter(decision_cycle_id__isnull=True).values_list('id', flat=True)
            ) - claimed[signal_type]
            kept_ids = set(
                scoped.filter(decision_cycle_id__isnull=False)
                .exclude(decision_cycle_id=activity.decision_cycle_id)
                .values_list('id', flat=True)
            ) - kept_seen[signal_type]
            claimed[signal_type] |= orphan_ids
            kept_seen[signal_type] |= kept_ids
            if orphan_ids:
                attached[signal_type] = len(orphan_ids)
            if kept_ids:
                kept[signal_type] = len(kept_ids)
        return attached, kept
