# app_modules/signals/migrations/0028_drop_techstacksignal_usage_department.py
"""
Drop the legacy single-FK usage_department from TechStackSignal.

Finition of the "Tech scope (usage)" sprint: the WHO-uses-the-tool signal
moved from the mono FK usage_department to the multi-department M2M
usage_departments (migration 0027). Every consumer -- extraction,
prep_call, deal_health, the detail display and now the manual Create/Update
serializer -- reads/writes the M2M, so the FK has no remaining reader or
writer and is removed.

  * RemoveField usage_department -- reversible: reversing this migration
    re-adds the nullable FK from the historical state carried by 0027, so a
    rollback restores the column (empty; no data to backfill either way).
  * AlterField usage_scope -- state-only help_text refresh (the field now
    documents itself as the SCALE axis, independent of the M2M WHO). No DB
    change; the choices are unchanged.

Scope note: the unrelated signalclusterarchival.signal_type choices drift
that makemigrations proposes alongside is intentionally NOT included -- it
belongs to the cluster surface, untouched by this sprint.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("module_signals", "0027_techstacksignal_usage_departments"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="techstacksignal",
            name="usage_department",
        ),
        migrations.AlterField(
            model_name="techstacksignal",
            name="usage_scope",
            field=models.CharField(
                blank=True,
                choices=[
                    ("TEAM", "Team"),
                    ("DEPARTMENT", "Department"),
                    ("COMPANY", "Company-wide"),
                    ("UNKNOWN", "Unknown"),
                ],
                help_text=(
                    "Organisational SCALE of the tool usage at this account "
                    "(TEAM / COMPANY / UNKNOWN). Independent of WHO uses the "
                    "tool — that is the multi-department usage_departments "
                    "M2M below."
                ),
                max_length=20,
                null=True,
                verbose_name="Usage Scope",
            ),
        ),
    ]
