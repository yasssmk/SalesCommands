# app_modules/signals/migrations/0039_pain_impact_target_departments.py
"""
Add the multi-department scope relation to PainSignal and ImpactSignal.

Sub-step 2a/… of the "Signal scope (department)" sprint: let a pain / an
impact concern SEVERAL departments at once, cloning the established
multi-department pattern (TechStackSignal.usage_departments, and
ConstraintSignal.target_departments from sub-step 1a / migration 0036).

  * Adds a ManyToManyField `target_departments` -> core_modules.StandardDepartment
    on PainSignal (link table module_signals_pain_target_departments) and on
    ImpactSignal (link table module_signals_impact_target_departments); the
    relations carry no extra attributes, so no `through` models.
  * The legacy single-FK target_department is LEFT IN PLACE on both models
    (its drop is a later sub-step, once every reader/writer moves onto the
    M2M). scope_level is untouched. The one-time copy of the existing FK
    values into the M2Ms is the data migration 0040 (a separate node so its
    RunPython backfills can be exercised in isolation by the migration test).

Reversibility: AddField on a M2M is auto-reversible — reversing this migration
drops the two link tables and leaves the base tables and every other column
(target_department, scope_level included) untouched.

Scope note: the unrelated signalclusterarchival.signal_type choices drift that
makemigrations proposes alongside these fields is intentionally NOT included —
it is a pre-existing, choices-only (no-DDL) drift left by the People sprint and
belongs to a dedicated sanitization migration, not to this scope-M2M sub-step.
Same stance as migrations 0027/0028/0031/0036/0038. This migration is
hand-written so it carries ONLY the two AddField operations.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core_modules", "0001_initial"),
        ("module_signals", "0038_remove_constraintsignal_target_department"),
    ]

    operations = [
        migrations.AddField(
            model_name="painsignal",
            name="target_departments",
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    "The set of departments this pain concerns "
                    "(multi-department). Supersedes the legacy single-FK "
                    "target_department. Empty when no department is designated "
                    "(BUSINESS / company-wide)."
                ),
                related_name="pain_signals_scoped_to",
                to="core_modules.standarddepartment",
                verbose_name="Target Departments",
            ),
        ),
        migrations.AddField(
            model_name="impactsignal",
            name="target_departments",
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    "The set of departments this impact concerns "
                    "(multi-department). Supersedes the legacy single-FK "
                    "target_department. Empty when no department is designated "
                    "(BUSINESS / company-wide)."
                ),
                related_name="impact_signals_scoped_to",
                to="core_modules.standarddepartment",
                verbose_name="Target Departments",
            ),
        ),
    ]
