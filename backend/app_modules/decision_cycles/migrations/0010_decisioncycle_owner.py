# backend/app_modules/decision_cycles/migrations/0010_decisioncycle_owner.py
"""
Add owner field to DecisionCycle and backfill from created_by.

For existing cycles, owner is set to created_by (the user who created the cycle).
New cycles will have owner set explicitly in the serializer.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_owner_from_created_by(apps, schema_editor):
    """Set owner = created_by for all existing cycles that have no owner."""
    DecisionCycle = apps.get_model('decision_cycles', 'DecisionCycle')
    updated = DecisionCycle.objects.filter(
        owner__isnull=True,
        created_by__isnull=False,
    ).update(owner=models.F('created_by'))
    if updated:
        print(f"\n  Backfilled owner for {updated} existing decision cycle(s).")


def reverse_backfill(apps, schema_editor):
    """Reverse: clear owner field (non-destructive)."""
    DecisionCycle = apps.get_model('decision_cycles', 'DecisionCycle')
    DecisionCycle.objects.all().update(owner=None)


class Migration(migrations.Migration):

    dependencies = [
        ('decision_cycles', '0009_decisioncycle_hold_until_decisioncycle_outcome_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Step 1: Add the owner field (nullable)
        migrations.AddField(
            model_name='decisioncycle',
            name='owner',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='owned_decision_cycles',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Owner',
                help_text='User who owns this decision cycle (defaults to creator)',
            ),
        ),
        # Step 2: Add index for ownership filtering performance
        migrations.AddIndex(
            model_name='decisioncycle',
            index=models.Index(fields=['owner'], name='dc_owner_idx'),
        ),
        # Step 3: Backfill owner = created_by for existing rows
        migrations.RunPython(
            backfill_owner_from_created_by,
            reverse_backfill,
        ),
    ]