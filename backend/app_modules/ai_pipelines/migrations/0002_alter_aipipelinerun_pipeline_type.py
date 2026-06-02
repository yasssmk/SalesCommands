# app_modules/ai_pipelines/migrations/0002_alter_aipipelinerun_pipeline_type.py
"""
Sync AIPipelineRun.pipeline_type choices with AIPipelineType.NEXT_STEPS.

Sprint B4 adds a new value to the AIPipelineType TextChoices enum
(NEXT_STEPS, used by NextStepsPipeline). The `pipeline_type` column on
AIPipelineRun declares `choices=AIPipelineType.choices`, which Django
captures into migration state. Adding a value to the enum therefore
triggers a no-op-at-the-DB-level but mandatory-at-migration-tree-level
AlterField operation.

Schema impact: zero. `choices` is a Python-side validation parameter
(enforced by ModelForm / DRF serializer), not a DB-level constraint.
SQLite emits no DDL; PostgreSQL emits no DDL. The column type, length,
nullability, default, indexes, and help_text are all unchanged.

Purpose: keep the migration tree drift-free so a future
`makemigrations` does not re-detect this change. The legacy value
TRANSCRIPT_SIGNALS is preserved on all historical rows (no data
migration).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('module_ai_pipelines', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aipipelinerun',
            name='pipeline_type',
            field=models.CharField(
                choices=[
                    ('TRANSCRIPT_SIGNALS', 'Transcript signal extraction'),
                    ('NEXT_STEPS',         'Next steps extraction'),
                ],
                help_text=(
                    'Identifies which business case produced this run '
                    '(e.g. TRANSCRIPT_SIGNALS, NEXT_STEPS).'
                ),
                max_length=50,
                verbose_name='Pipeline Type',
            ),
        ),
    ]
