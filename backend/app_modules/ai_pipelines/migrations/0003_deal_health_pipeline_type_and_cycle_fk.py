# app_modules/ai_pipelines/migrations/0003_deal_health_pipeline_type_and_cycle_fk.py
"""
Add DEAL_HEALTH to AIPipelineType choices + source_decision_cycle FK.

Two operations:

1. AlterField on pipeline_type to sync the TextChoices with the new
   DEAL_HEALTH value. Schema impact: zero (choices is Python-side
   validation only). Mirror of migration 0002.

2. AddField source_decision_cycle — nullable FK to DecisionCycle.
   Allows cycle-level pipelines (deal-health) to record which cycle
   they operated on, mirroring the existing source_activity FK for
   activity-level pipelines.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('module_ai_pipelines', '0002_alter_aipipelinerun_pipeline_type'),
        ('decision_cycles', '0013_dealhealthsnapshot_dealproduct'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aipipelinerun',
            name='pipeline_type',
            field=models.CharField(
                choices=[
                    ('TRANSCRIPT_SIGNALS', 'Transcript signal extraction'),
                    ('NEXT_STEPS', 'Next steps extraction'),
                    ('DEAL_HEALTH', 'Deal health diagnostic'),
                ],
                help_text=(
                    'Identifies which business case produced this run '
                    '(e.g. TRANSCRIPT_SIGNALS, NEXT_STEPS).'
                ),
                max_length=50,
                verbose_name='Pipeline Type',
            ),
        ),
        migrations.AddField(
            model_name='aipipelinerun',
            name='source_decision_cycle',
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    'DecisionCycle this run operated on, for cycle-level '
                    'pipelines (deal-health). Null for activity-level '
                    'pipelines. SET_NULL on DecisionCycle deletion so the '
                    'audit row survives.'
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='ai_pipeline_runs',
                to='decision_cycles.decisioncycle',
                verbose_name='Source Decision Cycle',
            ),
        ),
    ]
