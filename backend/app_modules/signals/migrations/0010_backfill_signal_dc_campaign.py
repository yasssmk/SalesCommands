# app_modules/signals/migrations/0010_backfill_signal_dc_campaign.py
"""
Sprint 1 — backfill decision_cycle and campaign FKs on historical signals.

Why
---
Before Sprint 1, signals created from an Activity context had their
decision_cycle and campaign fields left null because no auto-propagation
hook existed in SignalManager.create() — even when the source_activity
itself carried these FKs. The Sprint 1 fix introduces the propagation
hook for new writes; this migration backfills historical data so that
cluster scoping is consistent across both new and pre-existing rows.

Scope
-----
Models in scope:
  - PainSignal       (has decision_cycle, campaign FK fields)
  - ObjectiveSignal  (has decision_cycle, campaign FK fields)

Models NOT in scope:
  - TechStackSignal  — shadow-overrides decision_cycle and campaign to
                       None at the model class level; no DB columns exist.
  - PeopleSignal     — slated for removal in Sprint 2; backfilling data
                       on a model in sunset would be wasted work.

Algorithm
---------
For each (Model, field) pair:

    UPDATE <signal_table>
    SET <field>_id = (
        SELECT activity.<field>_id
        FROM module_activities act
        WHERE act.id = signal.source_activity_id
    )
    WHERE <field>_id IS NULL
      AND source_activity_id IS NOT NULL
      AND source_activity.<field>_id IS NOT NULL

Implemented as one ORM update() per pair using a correlated Subquery —
Django does NOT allow F('source_activity__<field>') in update()
(joined-field references are not portable across DB backends; ORM
raises FieldError). The Subquery pattern is the supported alternative.

Idempotency
-----------
The filter `<field>__isnull=True` excludes rows that have already been
backfilled. A re-run on the same database is a no-op (zero rows match).

Non-destructiveness
-------------------
Existing non-null values are never overwritten — the WHERE clause
explicitly requires `<field>__isnull=True`.

Reverse
-------
RunPython.noop — irreversible. Distinguishing backfilled values from
legitimate ones after the fact is not possible.
"""

from django.db import migrations
from django.db.models import OuterRef, Subquery


def backfill_dc_campaign(apps, schema_editor):
    """
    Backfill decision_cycle and campaign on PainSignal and ObjectiveSignal
    from their source_activity, when the signal field is null and the
    activity field is set.
    """
    Activity = apps.get_model('module_activities', 'Activity')
    PainSignal = apps.get_model('module_signals', 'PainSignal')
    ObjectiveSignal = apps.get_model('module_signals', 'ObjectiveSignal')

    # -------------------------------------------------------------------------
    # PainSignal — decision_cycle
    # -------------------------------------------------------------------------
    activity_dc = Subquery(
        Activity.objects.filter(
            pk=OuterRef('source_activity_id'),
        ).values('decision_cycle_id')[:1]
    )
    updated = PainSignal.objects.filter(
        decision_cycle__isnull=True,
        source_activity__isnull=False,
        source_activity__decision_cycle__isnull=False,
    ).update(decision_cycle_id=activity_dc)
    print(f"  PainSignal.decision_cycle: backfilled {updated} row(s)")

    # -------------------------------------------------------------------------
    # PainSignal — campaign
    # -------------------------------------------------------------------------
    activity_campaign = Subquery(
        Activity.objects.filter(
            pk=OuterRef('source_activity_id'),
        ).values('campaign_id')[:1]
    )
    updated = PainSignal.objects.filter(
        campaign__isnull=True,
        source_activity__isnull=False,
        source_activity__campaign__isnull=False,
    ).update(campaign_id=activity_campaign)
    print(f"  PainSignal.campaign: backfilled {updated} row(s)")

    # -------------------------------------------------------------------------
    # ObjectiveSignal — decision_cycle
    # -------------------------------------------------------------------------
    activity_dc = Subquery(
        Activity.objects.filter(
            pk=OuterRef('source_activity_id'),
        ).values('decision_cycle_id')[:1]
    )
    updated = ObjectiveSignal.objects.filter(
        decision_cycle__isnull=True,
        source_activity__isnull=False,
        source_activity__decision_cycle__isnull=False,
    ).update(decision_cycle_id=activity_dc)
    print(f"  ObjectiveSignal.decision_cycle: backfilled {updated} row(s)")

    # -------------------------------------------------------------------------
    # ObjectiveSignal — campaign
    # -------------------------------------------------------------------------
    activity_campaign = Subquery(
        Activity.objects.filter(
            pk=OuterRef('source_activity_id'),
        ).values('campaign_id')[:1]
    )
    updated = ObjectiveSignal.objects.filter(
        campaign__isnull=True,
        source_activity__isnull=False,
        source_activity__campaign__isnull=False,
    ).update(campaign_id=activity_campaign)
    print(f"  ObjectiveSignal.campaign: backfilled {updated} row(s)")


class Migration(migrations.Migration):

    dependencies = [
        ('module_signals', '0009_painsignal_related_techstack_and_more'),
    ]

    operations = [
        migrations.RunPython(
            backfill_dc_campaign,
            reverse_code=migrations.RunPython.noop,
        ),
    ]