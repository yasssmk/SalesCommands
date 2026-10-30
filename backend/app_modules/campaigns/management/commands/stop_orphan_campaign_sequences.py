# app_modules/campaigns/management/commands/stop_orphan_campaign_sequences.py
"""
Sprint Next steps 5.14a — end the campaign sequences that should have stopped.

Before 5.14a, a FINAL outcome (SUCCESSFUL / terminal) written outside
process_result — the campaign "Log Response" on an already COMPLETED step,
the PATCH — left the prospect's sequence running. The runtime is fixed (the
Activity post_save, CampaignExecutionService.apply_final_outcome); this
command fixes the EXISTING data with the SAME method: for each campaign
prospect that has a final outcome AND open cadence steps (PLANNED / ON_HOLD),
the prospect is completed / stopped and its open steps deleted.

The deletion is irreversible (no migration): run with --dry-run first — it
lists, per tenant, the prospects and the steps that WOULD be deleted, and
writes nothing. The same selection as the PO's audit SELECT
(audit_514a_orphan_chains.sql). Re-runnable: a second run finds nothing.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from app_modules.activities.constants import ActivityStatus
from app_modules.activities.models import Activity
from app_modules.campaigns.constants import SUCCESSFUL_OUTCOMES, TERMINAL_OUTCOMES
from app_modules.campaigns.services.campaign_execution_service import CampaignExecutionService
from core.exceptions import StandardizedValidationError

OPEN_STEP_STATUSES = (ActivityStatus.PLANNED, ActivityStatus.ON_HOLD)
FINAL_OUTCOMES = SUCCESSFUL_OUTCOMES | TERMINAL_OUTCOMES


class Command(BaseCommand):
    help = (
        'End the campaign sequences that should have stopped: prospects with a '
        'final outcome (SUCCESSFUL / terminal) and open cadence steps. Use '
        '--dry-run first (the deletion of the open steps is irreversible).'
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
        finals = (
            Activity.objects
            .filter(
                campaign_contact__isnull=False,
                status=ActivityStatus.COMPLETED,
                outcome__in=FINAL_OUTCOMES,
                campaign_contact__activities__status__in=OPEN_STEP_STATUSES,
            )
            .select_related('campaign_contact', 'campaign')
            .order_by('client_id', 'campaign_contact_id', 'completed_at')
            .distinct()
        )
        if options.get('client_id'):
            finals = finals.filter(client_id=options['client_id'])

        # The FIRST final activity of each prospect is the one that ended it.
        by_contact = {}
        for activity in finals:
            by_contact.setdefault(activity.campaign_contact_id, activity)

        mode = 'DRY RUN — nothing written' if dry_run else 'APPLY'
        self.stdout.write(f'stop_orphan_campaign_sequences: {mode}')
        if not by_contact:
            self.stdout.write('No campaign sequence to stop.')
            return

        current_tenant = None
        applied = refused = 0
        for activity in by_contact.values():
            if activity.client_id != current_tenant:
                current_tenant = activity.client_id
                self.stdout.write(f'\nTenant {current_tenant}')
            contact = activity.campaign_contact
            open_steps = list(
                Activity.objects
                .filter(campaign_contact_id=contact.id, status__in=OPEN_STEP_STATUSES)
                .order_by('sequence_position', 'created_at')
            )
            self.stdout.write(
                f'  prospect {contact.id} ({contact.status}) — campaign '
                f'"{activity.campaign.name if activity.campaign else "?"}" — '
                f'{activity.outcome} on "{activity.title}"'
            )
            for step in open_steps:
                date = step.scheduled_date or step.due_date
                self.stdout.write(
                    f'    would delete: #{step.sequence_position} "{step.title}" '
                    f'({step.status}, {date})' if dry_run else
                    f'    delete: #{step.sequence_position} "{step.title}" ({step.status}, {date})'
                )
            if dry_run:
                continue
            try:
                with transaction.atomic():
                    done = CampaignExecutionService(
                        user=None, client_id=activity.client_id,
                    ).apply_final_outcome(activity)
            except StandardizedValidationError as exc:
                done = False
                self.stdout.write(f'    refused: {exc}')
            if done:
                applied += 1
            else:
                refused += 1
                self.stdout.write('    not applied (see the log / the line above)')

        self.stdout.write(
            f'\n{len(by_contact)} prospect(s) found'
            + ('' if dry_run else f' — {applied} stopped, {refused} not applied')
        )
