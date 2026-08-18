# app_modules/decision_cycles/migrations/0020_dealproduct_discount_percent_bounds.py
"""
TD-74 — bound DealProduct.discount_percent to [0, 100].

The field was added unbounded by 0017; since the discount drives the derived
line amount, an out-of-range value corrupts the cycle total and KPI 7.

Two operations, in order:

1. ``clamp_out_of_range_discounts`` — pins any existing row into [0, 100] so
   the constraint can be added on ANY environment. In the current data every
   row is 0 (the field has never been writable through the API), so this is
   expected to touch nothing — it exists so the migration cannot fail against
   an environment whose rows were written some other way.

2. ``AddConstraint`` — the integrity backstop.

The clamp is deliberately NOT reversible in the data sense: un-clamping would
mean restoring corrupt values. Reverse is a no-op so the constraint can still
be dropped.
"""

from django.db import migrations, models


def clamp_out_of_range_discounts(apps, schema_editor):
    DealProduct = apps.get_model('decision_cycles', 'DealProduct')
    DealProduct.objects.filter(discount_percent__lt=0).update(discount_percent=0)
    DealProduct.objects.filter(discount_percent__gt=100).update(discount_percent=100)


def noop_reverse(apps, schema_editor):
    """Nothing to restore — the pre-clamp values were out of range by definition."""


class Migration(migrations.Migration):

    dependencies = [
        # 0017 added discount_percent; 0019 is the current head.
        ('decision_cycles', '0019_remove_decisionstep_ds_status_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(clamp_out_of_range_discounts, noop_reverse),
        migrations.AddConstraint(
            model_name='dealproduct',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ('discount_percent__gte', 0), ('discount_percent__lte', 100),
                ),
                name='deal_product_discount_percent_bounds',
            ),
        ),
    ]
