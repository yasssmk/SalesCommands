# app_modules/signals/migrations/0016_revert_source_activity_nullable.py
"""
Revert step F durification: keep source_activity nullable per the
documented BaseSignal intent.

Migration 0014_drop_painimpact_add_impactsignal_and_scope step F
durified `source_activity` to NOT NULL on PainSignal, ObjectiveSignal,
and TechStackSignal, and the ImpactSignal table was created NOT NULL
directly at step C. The intent stated in 0014's docstring was to "bring
the DB column in line with the model layer rule that source_activity
is required".

That step over-shot. Two problems:

  1. SEMANTIC INCOHERENCE — `on_delete=SET_NULL` was kept on every
     concrete model's source_activity FK (inherited from BaseSignal,
     never overridden). SET_NULL on a NOT NULL column is contradictory:
     deleting an Activity triggers Django to issue
       UPDATE … SET source_activity_id = NULL
     which the DB rejects with an IntegrityError. The combination acts
     as a hidden PROTECT — not declarative, not what readers expect.

  2. DRIFT — `BaseSignal.source_activity` was never updated. The model
     declaration is still `null=True, blank=True`. Running
     `makemigrations --dry-run` on the 4 affected models flags
     "Alter field source_activity" on every migration probe, polluting
     the diff and forcing operators to use `--no-migrations` in tests.

The required-at-create constraint is — and remains — enforced at the
APPLICATION layer:

  * PainSignal.clean         (line ~ 285)
  * ObjectiveSignal.clean    (analogous)
  * ImpactSignal.clean       (analogous)
  * TechStackSignal.clean    (analogous)
  * BlockerSignal.clean      (Sprint B1)

  * PainSignalCreateSerializer.validate
  * ObjectiveSignalCreateSerializer.validate
  * ImpactSignalCreateSerializer.validate
  * TechStackSignalCreateSerializer.validate
  * BlockerSignalCreateSerializer.validate

The application-layer rule is sufficient. The DB-level NOT NULL only
introduced incoherence with SET_NULL and a maintenance burden.

This migration re-renders the column nullable on all 4 affected types,
restoring coherence with BaseSignal. It is the inverse of 0014 step F
(and the post-create durification implicit in step C for ImpactSignal).

BlockerSignal (introduced by 0015) was already nullable on the column;
this migration only synchronises its `help_text` metadata with the new
explanatory text now declared on BaseSignal.source_activity. No DDL on
the blockersignal table beyond what makemigrations infers.

Forward path is non-destructive: rows with non-NULL source_activity are
preserved as-is; the column simply gains the ability to be NULL going
forward. The reverse direction durifies back to NOT NULL — usable only
if every row's source_activity is non-NULL at the time of reverse
migration.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('module_activities', '0017_activity_source_decision_cycle'),
        ('module_signals', '0015_blockersignal'),
    ]

    operations = [
        migrations.AlterField(
            model_name='painsignal',
            name='source_activity',
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    'Activity (call/meeting) from which this signal was '
                    'extracted. Nullable + on_delete=SET_NULL is '
                    'INTENTIONAL: a validated signal survives the deletion '
                    'of its source conversation as an account-level '
                    'observation. The "source_activity required at create" '
                    'rule is enforced at the application layer — in '
                    'concrete model clean() methods and in the Create '
                    'serializers (see PainSignal.clean, BlockerSignal.clean, '
                    'etc.) — never via a DB-level NOT NULL constraint, '
                    'because durifying the column would contradict the '
                    'SET_NULL deletion semantic.'
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='%(class)s_signals',
                to='module_activities.activity',
                verbose_name='Source Activity',
            ),
        ),
        migrations.AlterField(
            model_name='objectivesignal',
            name='source_activity',
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    'Activity (call/meeting) from which this signal was '
                    'extracted. Nullable + on_delete=SET_NULL is '
                    'INTENTIONAL: a validated signal survives the deletion '
                    'of its source conversation as an account-level '
                    'observation. The "source_activity required at create" '
                    'rule is enforced at the application layer — in '
                    'concrete model clean() methods and in the Create '
                    'serializers (see PainSignal.clean, BlockerSignal.clean, '
                    'etc.) — never via a DB-level NOT NULL constraint, '
                    'because durifying the column would contradict the '
                    'SET_NULL deletion semantic.'
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='%(class)s_signals',
                to='module_activities.activity',
                verbose_name='Source Activity',
            ),
        ),
        migrations.AlterField(
            model_name='impactsignal',
            name='source_activity',
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    'Activity (call/meeting) from which this signal was '
                    'extracted. Nullable + on_delete=SET_NULL is '
                    'INTENTIONAL: a validated signal survives the deletion '
                    'of its source conversation as an account-level '
                    'observation. The "source_activity required at create" '
                    'rule is enforced at the application layer — in '
                    'concrete model clean() methods and in the Create '
                    'serializers (see PainSignal.clean, BlockerSignal.clean, '
                    'etc.) — never via a DB-level NOT NULL constraint, '
                    'because durifying the column would contradict the '
                    'SET_NULL deletion semantic.'
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='%(class)s_signals',
                to='module_activities.activity',
                verbose_name='Source Activity',
            ),
        ),
        migrations.AlterField(
            model_name='techstacksignal',
            name='source_activity',
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    'Activity (call/meeting) from which this signal was '
                    'extracted. Nullable + on_delete=SET_NULL is '
                    'INTENTIONAL: a validated signal survives the deletion '
                    'of its source conversation as an account-level '
                    'observation. The "source_activity required at create" '
                    'rule is enforced at the application layer — in '
                    'concrete model clean() methods and in the Create '
                    'serializers (see PainSignal.clean, BlockerSignal.clean, '
                    'etc.) — never via a DB-level NOT NULL constraint, '
                    'because durifying the column would contradict the '
                    'SET_NULL deletion semantic.'
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='%(class)s_signals',
                to='module_activities.activity',
                verbose_name='Source Activity',
            ),
        ),
        # BlockerSignal was created nullable in migration 0015 — no DDL
        # change here, only a help_text sync to track the new explanatory
        # docstring now declared on BaseSignal.source_activity.
        migrations.AlterField(
            model_name='blockersignal',
            name='source_activity',
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    'Activity (call/meeting) from which this signal was '
                    'extracted. Nullable + on_delete=SET_NULL is '
                    'INTENTIONAL: a validated signal survives the deletion '
                    'of its source conversation as an account-level '
                    'observation. The "source_activity required at create" '
                    'rule is enforced at the application layer — in '
                    'concrete model clean() methods and in the Create '
                    'serializers (see PainSignal.clean, BlockerSignal.clean, '
                    'etc.) — never via a DB-level NOT NULL constraint, '
                    'because durifying the column would contradict the '
                    'SET_NULL deletion semantic.'
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='%(class)s_signals',
                to='module_activities.activity',
                verbose_name='Source Activity',
            ),
        ),
    ]
