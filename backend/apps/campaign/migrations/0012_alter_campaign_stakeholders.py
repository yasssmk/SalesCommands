# apps/campaign/migrations/0012_alter_campaign_stakeholders.py
"""
Align Campaign.stakeholders M2M declaration with the live model.

Drift discovered during the Sprint chore on migration alignment (PR #7,
chore/fix-pre-existing-migration-drifts — Dette 4).

What was off
------------
The original AddField operation in apps/campaign/migrations/0001_initial.py
declared the M2M as:

    field=models.ManyToManyField(
        related_name='participated_campaigns',
        through='campaign.CampaignStakeholder',
        to='end_users.user',
        verbose_name='Stakeholders',
    )

but the live model in apps/campaign/models/campaign.py has carried
`through_fields=('campaign', 'user')` for a while. The omission of
`through_fields` in the migration history is a latent bug, because the
through model `CampaignStakeholder` has TWO FKs that point to the user
model:

  * `user`     — the stakeholder (M2M target)
  * `added_by` — who added the stakeholder (audit FK)

Without `through_fields`, Django cannot disambiguate the M2M target.
Any live use of the reverse-or-forward M2M relation manager
(e.g. `campaign.stakeholders.all()` or `user.participated_campaigns`)
would have raised an ambiguity error. Live code paths reach the
underlying junction via `obj.stakeholder_links` and the prefetch
machinery, so the bug never surfaced at runtime — but
`makemigrations --dry-run` flagged it on every run, polluting the
diff and blocking the chore sprint acceptance criterion.

Secondary change
----------------
Django also renormalises the M2M target reference from `'end_users.user'`
(literal app label) to `settings.AUTH_USER_MODEL` (swappable reference).
Equivalent at runtime — pure metadata cleanup.

Production safety
-----------------
Both changes are STATE-ONLY at the database layer. Django emits no DDL
for an AlterField that only adjusts `through_fields` or normalises a
swappable reference: the underlying junction table and its FKs are
unchanged. Existing production data is untouched; the migration only
updates Django's recorded view of the schema.
"""

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('campaign', '0011_alter_campaign_sequence_type'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='campaign',
            name='stakeholders',
            field=models.ManyToManyField(
                related_name='participated_campaigns',
                through='campaign.CampaignStakeholder',
                through_fields=('campaign', 'user'),
                to=settings.AUTH_USER_MODEL,
                verbose_name='Stakeholders',
            ),
        ),
    ]
