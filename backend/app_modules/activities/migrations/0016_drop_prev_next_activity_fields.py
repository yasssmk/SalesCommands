# app_modules/activities/migrations/0016_drop_prev_next_activity_fields.py
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('module_activities', '0015_backfill_decision_cycle_source_campaign'),
    ]

    operations = [
        # Drop indexes first
        migrations.RemoveIndex(
            model_name='activity',
            name='act_prev_idx',
        ),
        migrations.RemoveIndex(
            model_name='activity',
            name='act_next_idx',
        ),
        # Drop fields
        migrations.RemoveField(
            model_name='activity',
            name='previous_activity',
        ),
        migrations.RemoveField(
            model_name='activity',
            name='next_activity',
        ),
    ]