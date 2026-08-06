# Switch Campaign.channel_override to the ChannelOverride TextChoices and
# rename the stored value 'EMAIL_ONLY' -> 'NO_CALLS'.
#
# The literals 'EMAIL_ONLY'/'NO_CALLS' are frozen here on purpose: a data
# migration operates on the historical value, which no longer exists as an
# application constant. Everywhere else the value flows through
# app_modules.campaigns.constants.ChannelOverride.

from django.db import migrations, models
from django.db.models import Count


def _distribution(Campaign):
    """Return {channel_override: count} across all campaigns."""
    return {
        row['channel_override']: row['n']
        for row in Campaign.objects.values('channel_override').annotate(n=Count('id'))
    }


def email_only_to_no_calls(apps, schema_editor):
    """Migrate the legacy 'EMAIL_ONLY' channel_override value to 'NO_CALLS'."""
    Campaign = apps.get_model('module_campaigns', 'Campaign')

    print(f"\n  channel_override BEFORE: {_distribution(Campaign)}")
    updated = Campaign.objects.filter(channel_override='EMAIL_ONLY').update(
        channel_override='NO_CALLS'
    )
    print(f"  migrated EMAIL_ONLY -> NO_CALLS on {updated} campaign(s)")
    print(f"  channel_override AFTER:  {_distribution(Campaign)}")


def no_calls_to_email_only(apps, schema_editor):
    """Reverse — restore 'NO_CALLS' back to the legacy 'EMAIL_ONLY' value."""
    Campaign = apps.get_model('module_campaigns', 'Campaign')

    restored = Campaign.objects.filter(channel_override='NO_CALLS').update(
        channel_override='EMAIL_ONLY'
    )
    print(f"\n  reverted NO_CALLS -> EMAIL_ONLY on {restored} campaign(s)")


class Migration(migrations.Migration):

    dependencies = [
        ("module_campaigns", "0015_campaigncontact_sequence_run"),
    ]

    operations = [
        migrations.AlterField(
            model_name="campaign",
            name="channel_override",
            field=models.CharField(
                choices=[("AUTO", "Auto"), ("NO_CALLS", "No calls")],
                default="AUTO",
                help_text="AUTO = backend selects variant per contact channels. NO_CALLS = never call; email or LinkedIn only.",
                max_length=20,
                verbose_name="Channel Override",
            ),
        ),
        migrations.RunPython(
            email_only_to_no_calls,
            reverse_code=no_calls_to_email_only,
        ),
    ]
