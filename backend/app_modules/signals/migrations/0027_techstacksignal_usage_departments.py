# app_modules/signals/migrations/0027_techstacksignal_usage_departments.py
"""
Add the multi-department usage relation to TechStackSignal.

Sub-step 1/3 of the "Tech scope (usage)" sprint: capture WHO uses a tool,
allowing SEVERAL departments at once ("Sales AND Marketing on HubSpot").

  * Adds a ManyToManyField `usage_departments` -> core_modules.StandardDepartment.
  * Creates one link table (module_signals_tech_stack_usage_departments);
    the relation carries no extra attributes, so no `through` model.
  * No data to backfill: the field starts empty on every existing row
    (extraction populates it in sub-step 2).

Reversibility: AddField on a M2M is auto-reversible — reversing this
migration drops the link table and leaves the base tech-stack table and
every other column untouched. No data-migration step, nothing else to undo.

Scope note: the unrelated `signalclusterarchival.signal_type` choices
drift that `makemigrations` proposed alongside this field is intentionally
NOT included here — it belongs to the cluster surface, which this sprint
does not touch.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core_modules", "0001_initial"),
        ("module_signals", "0026_constraint_nature_detach_axes"),
    ]

    operations = [
        migrations.AddField(
            model_name="techstacksignal",
            name="usage_departments",
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    "The set of departments that USE this tool "
                    "(multi-department: a tool can be used by Sales and "
                    "Marketing at once). An attribute of the observation, "
                    "populated by extraction and independent of the "
                    "usage_scope TEAM/COMPANY/UNKNOWN axis. Empty when no "
                    "department is designated."
                ),
                related_name="tech_stack_signals_used_by",
                to="core_modules.standarddepartment",
                verbose_name="Usage Departments",
            ),
        ),
    ]
