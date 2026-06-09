# app_modules/ai_pipelines/management/commands/cleanup_pipeline_runs.py

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from app_modules.ai_pipelines.constants import AIPipelineStatus
from app_modules.ai_pipelines.models.pipeline_run import AIPipelineRun


class Command(BaseCommand):
    help = (
        'Mark zombie AIPipelineRun rows (stuck in RUNNING beyond a '
        'threshold) as LLM_ERROR so they no longer block idempotency '
        'checks or confuse the last-run endpoint.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would change without writing to the DB.',
        )
        parser.add_argument(
            '--threshold-minutes',
            type=int,
            default=30,
            help='Runs stuck RUNNING longer than this are considered zombies (default: 30).',
        )
        parser.add_argument(
            '--run-ids',
            nargs='*',
            help='Target specific run UUIDs instead of scanning by threshold.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        threshold_minutes = options['threshold_minutes']
        run_ids = options.get('run_ids')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE — no changes will be saved\n'))

        qs = AIPipelineRun.objects.filter(status=AIPipelineStatus.RUNNING)

        if run_ids:
            qs = qs.filter(id__in=run_ids)
            self.stdout.write(f'Targeting {len(run_ids)} specific run ID(s).\n')
        else:
            cutoff = timezone.now() - timedelta(minutes=threshold_minutes)
            qs = qs.filter(created_at__lt=cutoff)
            self.stdout.write(
                f'Scanning for RUNNING runs older than {threshold_minutes} minutes '
                f'(cutoff: {cutoff:%Y-%m-%d %H:%M:%S %Z}).\n'
            )

        zombies = list(qs.order_by('created_at'))

        if not zombies:
            self.stdout.write(self.style.SUCCESS('No zombie runs found.'))
            return

        self.stdout.write(f'Found {len(zombies)} zombie run(s):\n')
        for run in zombies:
            age = timezone.now() - run.created_at
            self.stdout.write(
                f'  {run.id} | {run.get_pipeline_type_display()} | '
                f'created {run.created_at:%Y-%m-%d %H:%M} | '
                f'age {age.total_seconds() / 60:.0f}m'
            )

        if dry_run:
            self.stdout.write(self.style.WARNING(f'\nWould mark {len(zombies)} run(s) as LLM_ERROR.'))
            return

        with transaction.atomic():
            updated = qs.update(
                status=AIPipelineStatus.LLM_ERROR,
                error_message='Marked as zombie by cleanup_pipeline_runs management command.',
            )

        self.stdout.write(self.style.SUCCESS(f'\nMarked {updated} run(s) as LLM_ERROR.'))
