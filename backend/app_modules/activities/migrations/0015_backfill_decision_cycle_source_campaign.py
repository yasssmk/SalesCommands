# app_modules/activities/migrations/0015_backfill_decision_cycle_source_campaign.py
from django.db import migrations


def backfill_source_campaign(apps, schema_editor):
    """
    Backfill DecisionCycle.source_campaign_id for cycles where it is null
    but a linked activity has a campaign_id set.
    """
    DecisionCycle = apps.get_model('decision_cycles', 'DecisionCycle')
    Activity = apps.get_model('module_activities', 'Activity')

    cycles_updated = 0

    cycles = DecisionCycle.objects.filter(source_campaign__isnull=True)

    for cycle in cycles:
        activity = (
            Activity.objects
            .filter(decision_cycle_id=cycle.id, campaign__isnull=False)
            .values('campaign_id')
            .first()
        )
        if activity:
            cycle.source_campaign_id = activity['campaign_id']
            cycle.save(update_fields=['source_campaign_id'])
            cycles_updated += 1

    print(f"\n  backfilled source_campaign on {cycles_updated} decision cycles")


def reverse_backfill(apps, schema_editor):
    """Irreversible."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('module_activities', '0014_nullify_prev_next_activity'),
    ]

    operations = [
        migrations.RunPython(
            backfill_source_campaign,
            reverse_code=reverse_backfill,
        ),
    ]