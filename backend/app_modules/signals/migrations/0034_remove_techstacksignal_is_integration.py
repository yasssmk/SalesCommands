# Sub-step 9c — schema drop of TechStackSignal.is_integration (last act of the
# Competitors sprint).
#
# The manual Integration tag was retired in sub-step 9b (no live reader/writer
# left); an integration requirement now lives as a TECHNICAL ConstraintSignal.
# No backfill (test data only). This drops the now-dead column.
#
# SCHEMA-ONLY, reversible (RemoveField re-adds a default=False BooleanField on
# reverse). No data. Scoped to is_integration — is_to_replace untouched.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("module_signals", "0033_remove_techstacksignal_is_competitor"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="techstacksignal",
            name="is_integration",
        ),
    ]
