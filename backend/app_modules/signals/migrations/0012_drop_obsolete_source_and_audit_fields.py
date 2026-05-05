# app_modules/signals/migrations/00XX_drop_obsolete_source_and_audit_fields.py
"""
Drop obsolete source_* and last_modified_* columns from signal tables.

Standardisation refactor (PHASE A.5):
  - source_contact     → removed from BaseSignal abstract.
                          Contacts derived at read time from
                          source_activity.contacts via SignalSourceMixin.
  - source_department  → removed from BaseSignal abstract.
                          Same rationale as source_contact.
  - last_modified_by   → removed from BaseSignal abstract.
                          Duplicate with ModuleBaseModel.updated_by.
  - last_modified_at   → removed from BaseSignal abstract.
                          Duplicate with ModuleBaseModel.updated_at.

original_value field is kept on BaseSignal — unique semantics
(snapshot of source_quote at first manual edit of an LLM-extracted
signal). Not affected by this migration.

Tables affected:
  - module_signals_pain         : DROP 4 columns
  - module_signals_objective    : DROP 4 columns
  - module_signals_tech_stack   : DROP 2 columns
                                  (source_contact_id and
                                  source_department_id never existed
                                  on this table — shadow-overridden
                                  since the catalog-FK refactor)

Tables NOT affected:
  - module_signals_pain_impact     (no shared field touched)
  - module_signals_cluster_archival (no shared field touched)

Data loss:
  This migration drops the columns and their data. Local development
  environments only — userMemories explicitly authorise destructive
  DB changes. If a production-like environment ever runs this, the
  source_contact_id / last_modified_by_id values are gone after apply.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        # TODO — replace with the actual previous migration in module_signals
        ('module_signals', '0011_alter_signalclusterarchival_signal_type_and_more'),
    ]

    operations = [
        # ====================================================================
        # PainSignal
        # ====================================================================
        migrations.RemoveField(
            model_name='painsignal',
            name='source_contact',
        ),
        migrations.RemoveField(
            model_name='painsignal',
            name='source_department',
        ),
        migrations.RemoveField(
            model_name='painsignal',
            name='last_modified_by',
        ),
        migrations.RemoveField(
            model_name='painsignal',
            name='last_modified_at',
        ),

        # ====================================================================
        # ObjectiveSignal
        # ====================================================================
        migrations.RemoveField(
            model_name='objectivesignal',
            name='source_contact',
        ),
        migrations.RemoveField(
            model_name='objectivesignal',
            name='source_department',
        ),
        migrations.RemoveField(
            model_name='objectivesignal',
            name='last_modified_by',
        ),
        migrations.RemoveField(
            model_name='objectivesignal',
            name='last_modified_at',
        ),

        # ====================================================================
        # TechStackSignal — only last_modified_* (source_* never existed)
        # ====================================================================
        migrations.RemoveField(
            model_name='techstacksignal',
            name='last_modified_by',
        ),
        migrations.RemoveField(
            model_name='techstacksignal',
            name='last_modified_at',
        ),
    ]