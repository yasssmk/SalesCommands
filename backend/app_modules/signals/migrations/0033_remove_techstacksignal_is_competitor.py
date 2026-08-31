# Sub-step 8b — schema drop of TechStackSignal.is_competitor.
#
# The manual Competitor tag was retired in sub-step 8-bis (every live
# reader/writer removed; audit clean). Historical data was migrated to
# CompetitorSignal by 0031. This drops the now-dead column.
#
# SCHEMA-ONLY, reversible (RemoveField re-adds a default=False BooleanField on
# reverse). No data. Scoped to is_competitor — is_integration / is_to_replace
# untouched.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("module_signals", "0032_alter_signalclusterarchival_signal_type"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="techstacksignal",
            name="is_competitor",
        ),
    ]
