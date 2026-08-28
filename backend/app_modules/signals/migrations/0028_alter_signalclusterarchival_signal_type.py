# app_modules/signals/migrations/0028_alter_signalclusterarchival_signal_type.py
"""
Pre-existing SignalClusterArchival.signal_type choices refresh.

This is the long-standing model-state drift that makemigrations kept
proposing (the `signal_type` choices list gained "constraint" and was
reordered on the model, without a matching migration). It was deliberately
left out of the tech-scope migrations, but the PO's environment generated
and APPLIED it as `0028_alter_signalclusterarchival_signal_type` — a sibling
of `0027` — at the same time `0028_drop_techstacksignal_usage_department`
(the tech-scope C+D drop) was added, giving the module_signals graph TWO
0028 leaves ("multiple leaf nodes").

This file materialises that sibling in the repository so the branch matches
the state already recorded on the PO's base. The companion
`0029_merge_*` migration then reconciles the two 0028 leaves back into a
single linear head.

Nature: AlterField on a CharField's `choices` only. `choices` are not
enforced at the PostgreSQL level, so this runs NO DDL — it is a pure
migration-state (Django) change, non-destructive and reversible (Django
reverses it to the prior choices state). The tech-stack rows and every
other table are untouched.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("module_signals", "0027_techstacksignal_usage_departments"),
    ]

    operations = [
        migrations.AlterField(
            model_name="signalclusterarchival",
            name="signal_type",
            field=models.CharField(
                choices=[
                    ("pain", "Pain"),
                    ("objective", "Objective"),
                    ("tech_stack", "Tech Stack"),
                    ("impact", "Impact"),
                    ("constraint", "Constraint"),
                ],
                help_text=(
                    "Signal family the cluster belongs to (e.g. 'pain'). "
                    "Matches the type identifiers used by SignalDataService "
                    "and the cluster endpoints."
                ),
                max_length=20,
                verbose_name="Signal Type",
            ),
        ),
    ]
