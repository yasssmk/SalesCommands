# app_modules/signals/migrations/0029_merge_usage_department_drop.py
"""
Merge the two module_signals 0028 leaf migrations back into one head.

The module_signals graph had TWO 0028 siblings, both children of 0027
("multiple leaf nodes" — the error the PO hit on migrate):

  * 0028_alter_signalclusterarchival_signal_type   (pre-existing choices
    drift; already applied on the PO's base)
  * 0028_drop_techstacksignal_usage_department      (tech-scope C+D drop)

This merge migration reconciles them. It carries NO operations — merges
never change the schema; they only add a node that depends on both leaves
so the graph has a single linear head again. Both 0028 migrations keep
their identity and their applied/unapplied state on every environment
(nothing is renumbered), and whichever of the two has not run yet applies
normally on the next migrate, followed by this no-op merge.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("module_signals", "0028_alter_signalclusterarchival_signal_type"),
        ("module_signals", "0028_drop_techstacksignal_usage_department"),
    ]

    operations = []
