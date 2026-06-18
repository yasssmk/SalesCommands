# app_modules/signals/migrations/0020_alter_nextstepsignal_suggested_activity_type.py
"""
Reflect the addition of DEMO in ActivityType choices on NextStepSignal.

NextStepSignal.suggested_activity_type uses ActivityType.choices as its
single source of truth. Adding DEMO to ActivityType (migration
module_activities/0019_add_demo_activity_type) propagates here as a
state-only AlterField — no DB schema change.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('module_signals', '0019_basesignal_source_run'),
    ]

    operations = [
        migrations.AlterField(
            model_name='nextstepsignal',
            name='suggested_activity_type',
            field=models.CharField(
                choices=[
                    ('CALL', 'Phone Call'),
                    ('EMAIL', 'Email'),
                    ('MEETING', 'Meeting'),
                    ('DEMO', 'Demo'),
                    ('TASK', 'Task'),
                    ('LINKEDIN', 'LinkedIn Message'),
                    ('OTHER', 'Other'),
                ],
                help_text=(
                    'Proposed type of the next-step Activity '
                    '(CALL / EMAIL / MEETING / TASK / LINKEDIN / OTHER). '
                    'Choices imported directly from ActivityType to keep a '
                    'single source of truth — no enum duplication.'
                ),
                max_length=20,
                verbose_name='Suggested Activity Type',
            ),
        ),
    ]
