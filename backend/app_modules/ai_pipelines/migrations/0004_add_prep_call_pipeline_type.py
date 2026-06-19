# app_modules/ai_pipelines/migrations/0004_add_prep_call_pipeline_type.py
"""
Add PREP_CALL to AIPipelineType choices.

Schema impact: zero (choices is Python-side validation only).
Mirror of migration 0003 pattern.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('module_ai_pipelines', '0003_deal_health_pipeline_type_and_cycle_fk'),
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
                    ('PREP_CALL', 'Prep call brief'),
                ],
                help_text='Identifies which business case produced this run (e.g. TRANSCRIPT_SIGNALS, NEXT_STEPS).',
                max_length=50,
                verbose_name='Pipeline Type',
            ),
        ),
    ]
