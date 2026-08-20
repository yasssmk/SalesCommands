# app_modules/quotas/migrations/0004_purge_leads_quotas.py
#
# Delete the personal objectives stored under the retired LEADS metric (PO).
#
# 0003 removed LEADS from the enum, which narrows ``choices`` — metadata Django
# validates on write, never a database constraint — so every row already written
# under it survived, pointing at a metric nothing can compute. This deletes them.
#
# THIS DESTROYS USER DATA, deliberately and on the PO's instruction (the rows are
# test data). It is therefore written to be auditable rather than clever: one
# named function, one filter, no cascade of its own — Quota owns no children, so
# nothing else goes with it.
#
# NOT REVERSIBLE in substance. ``reverse`` is a no-op, not a restore: the rows
# are gone and a migration cannot invent them back. It exists so ``migrate
# quotas 0003`` runs instead of refusing, and it is declared explicitly rather
# than left as ``None`` so that choice is visible here and not a side effect.
#
# The read path does NOT depend on this having run: a stored unknown metric
# reports 0 rather than raising (quotas/services/progress._compute_value), which
# covers rows an old client writes between the deploy and this migration.

from django.db import migrations


RETIRED_METRICS = ['LEADS']


def purge_leads_quotas(apps, schema_editor):
    """Delete every Quota whose metric is no longer in the vocabulary.

    Filters on the literal string, NOT on ``MetricKey.LEADS`` — the enum member
    no longer exists, and a migration must in any case read the data as it is
    stored rather than through today's application code.
    """
    Quota = apps.get_model('quotas', 'Quota')
    Quota.objects.filter(metric__in=RETIRED_METRICS).delete()


def noop_reverse(apps, schema_editor):
    """Deleted rows cannot be restored; this only lets the migration unapply."""


class Migration(migrations.Migration):

    dependencies = [
        ('quotas', '0003_alter_quota_metric'),
    ]

    operations = [
        migrations.RunPython(purge_leads_quotas, noop_reverse),
    ]
