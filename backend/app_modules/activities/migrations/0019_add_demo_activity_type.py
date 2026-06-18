# app_modules/activities/migrations/0019_add_demo_activity_type.py
"""
Add DEMO to ActivityType choices.

Schema impact: zero (choices is Python-side validation only on a
CharField). No ALTER TABLE required — the column already accepts
any string up to max_length=20.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('module_activities', '0018_activity_next_step_signal'),
    ]

    operations = [
        migrations.AlterField(
            model_name='activity',
            name='activity_type',
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
                max_length=20,
                verbose_name='Activity Type',
            ),
        ),
    ]
