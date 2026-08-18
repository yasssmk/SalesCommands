# end_users/migrations/0013_rename_default_quota_currency_clientaccount_currency.py
"""
Rename ClientAccount.default_quota_currency -> currency.

The tenant already carried a currency (added by 0002, choices from
core.constants.CURRENCY, default EUR); only its NAME tied it to quotas, and only
one reader used it. Sprint C makes it the unit of every amount the tenant owns —
product prices, deal lines, cycle totals, KPI figures — so the field is renamed
rather than duplicated by a second currency column.

RenameField preserves the column's data: existing tenants keep whatever currency
they had, and none needs a backfill.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('end_users', '0012_transition_to_client_account'),
    ]

    operations = [
        migrations.RenameField(
            model_name='clientaccount',
            old_name='default_quota_currency',
            new_name='currency',
        ),
        migrations.AlterField(
            model_name='clientaccount',
            name='currency',
            field=models.CharField(
                choices=[('USD', 'DOLLAR'), ('EUR', 'EURO'),
                         ('GBP', 'GREAT BRITAIN POUND')],
                default='EUR',
                help_text=(
                    "The tenant's single currency (ISO-4217). EVERY amount this "
                    "client owns — product prices, deal lines, cycle totals, KPI "
                    "figures, quota targets — is expressed in it. There is no "
                    "conversion and no per-deal currency: amounts are stored as "
                    "plain numbers and this is the context that gives them a "
                    "unit. Renamed from default_quota_currency: the currency "
                    "belongs to the tenant, not to the quota that happened to "
                    "read it first."
                ),
                max_length=3,
                verbose_name='Currency',
            ),
        ),
    ]
