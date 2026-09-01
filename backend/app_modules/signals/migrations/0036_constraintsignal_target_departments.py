# app_modules/signals/migrations/0036_constraintsignal_target_departments.py
"""
Add the multi-department scope relation to ConstraintSignal.

Sub-step 1a/… of the "Signal scope (department)" sprint: let a constraint
concern SEVERAL departments at once (e.g. a security requirement owned by IT
AND Security & Risk). Clones the established multi-department pattern
TechStackSignal.usage_departments (migration 0027).

  * Adds a ManyToManyField `target_departments` -> core_modules.StandardDepartment.
  * Creates one link table (module_signals_constraint_target_departments);
    the relation carries no extra attributes, so no `through` model.
  * The legacy single-FK `target_department` is intentionally LEFT IN PLACE
    (its drop is a later sub-step, once every reader/writer moves onto the
    M2M). The one-time copy of the existing FK value into this M2M is the
    data migration 0037 (a separate node so its RunPython can be exercised
    in isolation by the migration test).

Reversibility: AddField on a M2M is auto-reversible — reversing this
migration drops the link table and leaves the base constraint table and
every other column (target_department included) untouched.

Scope note: the unrelated `signalclusterarchival.signal_type` choices drift
that `makemigrations` proposes alongside this field is intentionally NOT
included here — it is a pre-existing, choices-only (no-DDL) drift introduced
by the People sprint and belongs to a dedicated sanitization migration, not
to this scope-M2M sub-step. Same stance as migrations 0027/0028/0031.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core_modules", "0001_initial"),
        ("module_signals", "0035_peoplesignal_full_name_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="constraintsignal",
            name="target_departments",
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    "The set of departments this constraint concerns "
                    "(multi-department: a constraint can be owned by IT and "
                    "Security & Risk at once). Supersedes the legacy single-FK "
                    "target_department. Empty when no department is designated "
                    "(company-wide / cross-departmental)."
                ),
                related_name="constraint_signals_scoped_to",
                to="core_modules.standarddepartment",
                verbose_name="Target Departments",
            ),
        ),
    ]
