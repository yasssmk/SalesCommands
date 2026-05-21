# app_modules/signals/migrations/0014_drop_painimpact_add_impactsignal_and_scope.py
"""
Destructive schema refactor of the signals module.

Operations performed by this migration:

  1. Truncate every signal data table (PainSignal, ObjectiveSignal,
     TechStackSignal, PainImpact, SignalClusterArchival). The schema
     reshape that follows mutates the storage shape in ways that no
     existing row could survive correctly — and the operational data
     in scope is rep-validated qualitative signals, not finance / billing
     records. A clean slate is the simplest and safest path.

  2. Drop the PainImpact model entirely. The "proof of pain" concept
     it captured is superseded by the new first-class ImpactSignal,
     which sits at the same canonical (what × dimension) layer as
     PainSignal and ObjectiveSignal — not as a child of any of them.

  3. Create the ImpactSignal table. Same canonical structure as
     PainSignal / ObjectiveSignal, augmented with:
       - impact_type (FINANCIAL / TIME / HUMAN / ...)
       - metric_text (free-text quantification)
       - human_impact (optional FRUSTRATION / OVERLOAD / ...)
     source_activity is enforced NOT NULL at create time — ImpactSignal
     has no legacy nullable phase.

  4. Add scope_level to PainSignal with default BUSINESS. Brings Pain
     in line with Objective and Impact on the scope axis. The default
     guarantees the field is never empty even if an API client or LLM
     extraction omits it.

  5. Extend SignalClusterArchival.signal_type choices to include 'impact'.

  6. Durify source_activity to NOT NULL on PainSignal, ObjectiveSignal,
     and TechStackSignal. Every signal of qualification must now be
     anchored to a real conversation. The model layer was already
     enforcing the rule via clean(); this migration brings the DB
     column in line.

Forward path is destructive (data is dropped). The reverse path on
the RunPython step is a no-op — there is no meaningful way to
restore truncated signal data, and the surrounding schema reverse
would re-create the old structure on an empty DB anyway.
"""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


# =============================================================================
# DATA OPERATIONS
# =============================================================================

def truncate_all_signal_data(apps, schema_editor):
    """
    Empty every signal data table before the schema reshape.

    The order is bottom-up (children before parents) to avoid FK
    cascade noise:
      1. PainImpact      (FK -> PainSignal)
      2. PainSignal      (any direct dependants are already gone)
      3. ObjectiveSignal
      4. TechStackSignal
      5. SignalClusterArchival (no FK to the signals themselves —
         scoped by (account, signal_type, canonical_key) only)

    The historical models are obtained via apps.get_model so the
    function works regardless of the current Python class definitions
    in app_modules/signals/models/*.
    """
    PainImpact            = apps.get_model('module_signals', 'PainImpact')
    PainSignal            = apps.get_model('module_signals', 'PainSignal')
    ObjectiveSignal       = apps.get_model('module_signals', 'ObjectiveSignal')
    TechStackSignal       = apps.get_model('module_signals', 'TechStackSignal')
    SignalClusterArchival = apps.get_model('module_signals', 'SignalClusterArchival')

    PainImpact.objects.all().delete()
    PainSignal.objects.all().delete()
    ObjectiveSignal.objects.all().delete()
    TechStackSignal.objects.all().delete()
    SignalClusterArchival.objects.all().delete()


# =============================================================================
# MIGRATION
# =============================================================================

class Migration(migrations.Migration):

    # PostgreSQL raises "ObjectInUse: cannot ALTER TABLE ... because it
    # has pending trigger events" when a transaction performs a DELETE
    # (RunPython truncate, STEP A) followed by an ALTER TABLE on the
    # same table (STEP D / F) in the same transaction. The triggers
    # accumulated by the cascading FK checks of the truncate must be
    # flushed before any DDL can run on the affected tables.
    #
    # Setting atomic = False makes Django run each operation in its own
    # transaction, so the truncate commits and flushes its trigger
    # queue before the schema operations run. The trade-off is that a
    # failure mid-migration cannot be auto-rolled-back — acceptable
    # here because the forward path is already destructive (full data
    # reset) and the database is local during development.
    atomic = False

    dependencies = [
        ('decision_cycles', '0012_decisioncycle_source_campaign'),
        ('module_accounts', '0003_alter_companyaccount_industry'),
        ('module_activities', '0017_activity_source_decision_cycle'),
        ('module_campaigns', '0014_campaign_channel_override'),
        ('module_signals', '0013_alter_techstacksignal_tech_catalog_entry'),
        ('tech_catalog', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # =====================================================================
        # STEP A — Truncate every signal data table.
        # Forward is destructive; reverse is a no-op (cannot restore
        # truncated data, and the surrounding schema reverse would
        # re-create the old structure on an empty DB).
        # =====================================================================
        migrations.RunPython(
            truncate_all_signal_data,
            migrations.RunPython.noop,
        ),

        # =====================================================================
        # STEP B — Drop PainImpact. The model is being superseded by the
        # first-class ImpactSignal created in step C.
        # =====================================================================
        migrations.DeleteModel(
            name='PainImpact',
        ),

        # =====================================================================
        # STEP C — Create the ImpactSignal table and wire its FKs/indexes.
        # =====================================================================
        migrations.CreateModel(
            name='ImpactSignal',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('client_id', models.UUIDField(db_index=True, editable=False, help_text='ID of the client company this record belongs to', verbose_name='Client ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('canonical_key', models.CharField(blank=True, db_index=True, help_text='Stable identifier used to group multiple observations of the same fact for corroboration. Auto-computed by concrete model save() for PeopleSignal and TechStackSignal. Set manually or by LLM for PainSignal and ObjectiveSignal.', max_length=255, null=True, verbose_name='Canonical Key')),
                ('source_quote', models.TextField(blank=True, help_text='Exact excerpt from the transcript that supports this signal, preserved in its original language', null=True, verbose_name='Source Quote')),
                ('confidence', models.FloatField(blank=True, help_text='LLM confidence score (0.0–1.0). Null for manually entered signals.', null=True, verbose_name='Confidence')),
                ('is_inferred', models.BooleanField(default=False, help_text='False = verbatim from transcript. True = deduced / inferred by LLM.', verbose_name='Is Inferred')),
                ('metadata', models.JSONField(blank=True, help_text='Flexible storage for merge history, LLM context, etc.', null=True, verbose_name='Metadata')),
                ('source', models.CharField(choices=[('MANUAL', 'Manual entry'), ('LLM_EXTRACTED', 'LLM extracted'), ('LLM_MODIFIED', 'LLM modified'), ('EXTERNAL_RESEARCH', 'External research')], default='MANUAL', help_text='How the signal was created (manual entry vs. LLM)', max_length=20, verbose_name='Source')),
                ('language_original', models.CharField(blank=True, help_text='BCP-47 language tag of the source transcript (e.g. "fr", "en-US")', max_length=10, null=True, verbose_name='Original Language')),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('VALIDATED', 'Validated'), ('REJECTED', 'Rejected')], default='PENDING', help_text='PENDING = awaiting rep validation (LLM signals). VALIDATED = approved (manual signals start here). REJECTED = dismissed. MERGED = absorbed into another signal.', max_length=20, verbose_name='Status')),
                ('validated_at', models.DateTimeField(blank=True, help_text='When the signal was validated (was approved_at in legacy)', null=True, verbose_name='Validated At')),
                ('original_value', models.JSONField(blank=True, help_text='Snapshot of value before the first manual edit. Null for signals that have never been edited.', null=True, verbose_name='Original Value')),
                ('what', models.CharField(choices=[('OPS', 'Operations / Process'), ('TECH', 'Technology / System'), ('DATA', 'Data / Visibility'), ('PEOPLE', 'People / Org'), ('GROWTH', 'Growth / Revenue')], help_text='Domain axis of the impact (first component of canonical_key)', max_length=20, verbose_name='What')),
                ('dimension', models.CharField(choices=[('TIME', 'Time / Speed'), ('COST', 'Cost / Budget'), ('QUALITY', 'Quality / Accuracy'), ('SCALE', 'Scale / Capacity'), ('RISK', 'Risk / Compliance')], help_text='Outcome axis of the impact (second component of canonical_key)', max_length=20, verbose_name='Dimension')),
                ('scope_level', models.CharField(choices=[('BUSINESS', 'Business'), ('DEPARTMENT', 'Department'), ('PERSONAL', 'Personal')], help_text='Organisational scope at which the impact is measured (BUSINESS / DEPARTMENT / PERSONAL). Purely descriptive — no conditional FK requirement on ImpactSignal (contrast with ObjectiveSignal where scope drives target_contact / target_department).', max_length=20, verbose_name='Scope Level')),
                ('impact_type', models.CharField(choices=[('FINANCIAL', 'Financial impact'), ('TIME', 'Time impact'), ('PRODUCTIVITY', 'Productivity impact'), ('REVENUE', 'Revenue impact'), ('RISK', 'Risk impact'), ('CUSTOMER', 'Customer impact'), ('HUMAN', 'Human impact'), ('STRATEGIC', 'Strategic impact'), ('METRIC', 'Raw metric')], help_text='Nature of the impact observation — FINANCIAL, TIME, PRODUCTIVITY, REVENUE, RISK, CUSTOMER, HUMAN, STRATEGIC, or METRIC. Orthogonal axis to (what, dimension): two observations sharing the same canonical_key can carry different impact_types (e.g. one FINANCIAL, one HUMAN).', max_length=20, verbose_name='Impact Type')),
                ('summary', models.TextField(help_text='The impact described in plain language', verbose_name='Summary')),
                ('metric_text', models.CharField(blank=True, help_text='Quantified value as expressed during the conversation. Free text — e.g. "30k€/month", "5h/week", "around 50 people", "between 100 and 200". Intentionally NOT a structured numeric field — values are reported with widely varying granularity, units, and currency by reps; structured capture would lose nuance and force false precision.', max_length=255, verbose_name='Metric (free text)')),
                ('human_impact', models.CharField(blank=True, choices=[('FRUSTRATION', 'Frustration'), ('OVERLOAD', 'Overload'), ('STRESS', 'Stress / Anxiety'), ('DEMOTIVATION', 'Demotivation'), ('CONFLICT', 'Conflict')], help_text='Optional human dimension — FRUSTRATION / OVERLOAD / STRESS / DEMOTIVATION / CONFLICT. Typically paired with impact_type=HUMAN but the model layer stays permissive: a RISK or STRATEGIC impact may also legitimately carry a human note. Frontend UX guidance suggests human_impact primarily on impact_type=HUMAN.', max_length=20, null=True, verbose_name='Human Impact')),
            ],
            options={
                'verbose_name': 'Impact Signal',
                'verbose_name_plural': 'Impact Signals',
                'db_table': 'module_signals_impact',
                'ordering': ['-created_at'],
                'abstract': False,
            },
        ),

        # --- ImpactSignal FKs ---
        migrations.AddField(
            model_name='impactsignal',
            name='account',
            field=models.ForeignKey(
                help_text='Account this signal belongs to — required',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='%(class)s_signals',
                to='module_accounts.companyaccount',
                verbose_name='Account',
            ),
        ),
        migrations.AddField(
            model_name='impactsignal',
            name='campaign',
            field=models.ForeignKey(
                blank=True,
                help_text='Campaign this signal is associated with',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='%(class)s_signals',
                to='module_campaigns.campaign',
                verbose_name='Campaign',
            ),
        ),
        migrations.AddField(
            model_name='impactsignal',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='%(app_label)s_%(class)s_created',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Created By',
            ),
        ),
        migrations.AddField(
            model_name='impactsignal',
            name='decision_cycle',
            field=models.ForeignKey(
                blank=True,
                help_text='Decision cycle this signal is associated with',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='%(class)s_signals',
                to='decision_cycles.decisioncycle',
                verbose_name='Decision Cycle',
            ),
        ),
        migrations.AddField(
            model_name='impactsignal',
            name='requested_by',
            field=models.ForeignKey(
                blank=True,
                help_text='User who triggered the LLM extraction (null for manual signals)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='%(class)s_requested',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Requested By',
            ),
        ),
        # source_activity: created NOT NULL directly. ImpactSignal has
        # no legacy phase where the FK could be null. The model layer
        # also enforces this via clean().
        migrations.AddField(
            model_name='impactsignal',
            name='source_activity',
            field=models.ForeignKey(
                help_text='Activity (call/meeting) from which this signal was extracted',
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='%(class)s_signals',
                to='module_activities.activity',
                verbose_name='Source Activity',
            ),
        ),
        migrations.AddField(
            model_name='impactsignal',
            name='updated_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='%(app_label)s_%(class)s_updated',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Updated By',
            ),
        ),
        migrations.AddField(
            model_name='impactsignal',
            name='validated_by',
            field=models.ForeignKey(
                blank=True,
                help_text='Rep who validated this signal (was approved_by in legacy)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='%(class)s_validated',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Validated By',
            ),
        ),

        # --- ImpactSignal indexes ---
        migrations.AddIndex(
            model_name='impactsignal',
            index=models.Index(fields=['account'], name='impsig_account_idx'),
        ),
        migrations.AddIndex(
            model_name='impactsignal',
            index=models.Index(fields=['what'], name='impsig_what_idx'),
        ),
        migrations.AddIndex(
            model_name='impactsignal',
            index=models.Index(fields=['dimension'], name='impsig_dimension_idx'),
        ),
        migrations.AddIndex(
            model_name='impactsignal',
            index=models.Index(fields=['scope_level'], name='impsig_scope_level_idx'),
        ),
        migrations.AddIndex(
            model_name='impactsignal',
            index=models.Index(fields=['impact_type'], name='impsig_impact_type_idx'),
        ),
        migrations.AddIndex(
            model_name='impactsignal',
            index=models.Index(fields=['status'], name='impsig_status_idx'),
        ),
        migrations.AddIndex(
            model_name='impactsignal',
            index=models.Index(fields=['account', 'canonical_key'], name='impsig_account_canon_idx'),
        ),

        # =====================================================================
        # STEP D — Add scope_level to PainSignal with default BUSINESS.
        # =====================================================================
        migrations.AddField(
            model_name='painsignal',
            name='scope_level',
            field=models.CharField(
                choices=[
                    ('BUSINESS', 'Business'),
                    ('DEPARTMENT', 'Department'),
                    ('PERSONAL', 'Personal'),
                ],
                default='BUSINESS',
                help_text='Organisational scope at which the pain is felt (BUSINESS / DEPARTMENT / PERSONAL). Purely descriptive — no conditional FK requirement on PainSignal (contrast with ObjectiveSignal where scope drives target_contact / target_department). Defaults to BUSINESS — the safest interpretation when no specific scope is provided. LLM extraction is expected to emit an explicit value (see pain_v1.py); the default is a defence-in-depth fallback guaranteeing the field is never empty even if the API or LLM omits it.',
                max_length=20,
                verbose_name='Scope Level',
            ),
        ),
        migrations.AddIndex(
            model_name='painsignal',
            index=models.Index(fields=['scope_level'], name='painsig_scope_level_idx'),
        ),

        # =====================================================================
        # STEP E — Extend SignalClusterArchival.signal_type choices.
        # =====================================================================
        migrations.AlterField(
            model_name='signalclusterarchival',
            name='signal_type',
            field=models.CharField(
                choices=[
                    ('pain', 'Pain'),
                    ('objective', 'Objective'),
                    ('tech_stack', 'Tech Stack'),
                    ('impact', 'Impact'),
                ],
                help_text="Signal family the cluster belongs to (e.g. 'pain'). Matches the type identifiers used by SignalDataService and the cluster endpoints.",
                max_length=20,
                verbose_name='Signal Type',
            ),
        ),

        # =====================================================================
        # STEP F — Durify source_activity to NOT NULL on the three
        # existing concrete signal models. Safe because step A truncated
        # every row beforehand — no orphan NULL row can block the
        # column alteration.
        # =====================================================================
        migrations.AlterField(
            model_name='painsignal',
            name='source_activity',
            field=models.ForeignKey(
                help_text='Activity (call/meeting) from which this signal was extracted',
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
                help_text='Activity (call/meeting) from which this signal was extracted',
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
                help_text='Activity (call/meeting) from which this signal was extracted',
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='%(class)s_signals',
                to='module_activities.activity',
                verbose_name='Source Activity',
            ),
        ),
    ]