# app_modules/signals/migrations/0008_techstack_canonical_refactor.py
"""
Sprint TechStack — destructive refactor of TechStackSignal.

Strategy
--------
The legacy TechStackSignal model used a free-text `tech_name`,
satisfaction enum, EAV-ish field set (usage / limitations /
workarounds / integrations / category). The new model is anchored on
a FK to the tenant-level TechCatalog and adds structured lifecycle
fields (usage_scope, usage_department, usage_start_year, renewal_date,
cost_description, is_discontinued, discontinued_date, notes).

The naive `makemigrations`-generated migration ran a series of
RemoveField / AddField operations and required a one-off default for
the new NOT NULL FK `tech_catalog_entry` — which was impossible to
satisfy with anything Django would accept as a UUID.

Since:
  * the project is in dev local
  * the prompt explicitly authorises a destructive migration
  * the legacy data has no carry-over value (catalog FK is required
    and there is no way to retroactively map free-text `tech_name` to
    a catalog entry)

…the right approach is to DROP the legacy table entirely and
CreateModel against the new schema. This is a "DeleteModel +
CreateModel" pair — Django will rebuild the table from the current
model annotations.

Operations
----------
1. DeleteModel('TechStackSignal')
   Drops the existing module_signals_tech_stack table.

2. CreateModel('TechStackSignal', ...)
   Recreates the table aligned on the current model. All fields are
   declared explicitly to keep this migration self-contained and
   reproducible.

3. AddIndex × 5
   Adds the indexes declared on TechStackSignal.Meta.indexes.

Re-apply note
-------------
This migration is destructive. Re-applying it on an environment that
already holds non-empty TechStackSignal data WILL silently delete
those rows. We accept this here because:
  * dev local
  * legacy schema cannot satisfy the new NOT NULL catalog FK anyway

Production deployment of this refactor would require a separate data
migration step (export → map to catalog → import), which is out of
scope for this sprint.

Compatibility with shadow-overrides
-----------------------------------
TechStackSignal shadow-overrides 5 inherited BaseSignal fields:
source_contact, source_department, decision_cycle, campaign,
signal_category. Those columns are intentionally absent from the
CreateModel below — Django treats `= None` shadowing as "the field
does not exist on the concrete model" and produces no schema for
them.
"""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_modules', '0001_initial'),
        ('module_accounts', '0003_alter_companyaccount_industry'),
        ('module_activities', '0017_activity_source_decision_cycle'),
        ('module_signals', '0007_objectivesignal'),
        ('tech_catalog', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ================================================================
        # 1. DROP the legacy table entirely
        # ================================================================
        migrations.DeleteModel(
            name='TechStackSignal',
        ),

        # ================================================================
        # 2. RECREATE the table aligned on the current model
        # ================================================================
        migrations.CreateModel(
            name='TechStackSignal',
            fields=[
                # --- Identity ---
                (
                    'id',
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),

                # --- Tenant scope ---
                (
                    'client_id',
                    models.UUIDField(
                        db_index=True,
                        editable=False,
                        verbose_name='Client ID',
                        help_text='ID of the client company this record belongs to',
                    ),
                ),

                # --- Audit timestamps ---
                (
                    'created_at',
                    models.DateTimeField(
                        auto_now_add=True,
                        verbose_name='Created At',
                    ),
                ),
                (
                    'updated_at',
                    models.DateTimeField(
                        auto_now=True,
                        verbose_name='Updated At',
                    ),
                ),

                # --- Inherited from BaseSignal: canonical_key (auto-computed) ---
                (
                    'canonical_key',
                    models.CharField(
                        blank=True,
                        db_index=True,
                        help_text=(
                            'Stable identifier used to group multiple observations of the '
                            'same fact for corroboration. Auto-computed by concrete model '
                            'save() for PeopleSignal and TechStackSignal. Set manually or '
                            'by LLM for PainSignal and ObjectiveSignal.'
                        ),
                        max_length=255,
                        null=True,
                        verbose_name='Canonical Key',
                    ),
                ),

                # --- Inherited from BaseSignal: source_quote, confidence, is_inferred ---
                (
                    'source_quote',
                    models.TextField(
                        blank=True,
                        help_text=(
                            'Exact excerpt from the transcript that supports this signal, '
                            'preserved in its original language'
                        ),
                        null=True,
                        verbose_name='Source Quote',
                    ),
                ),
                (
                    'confidence',
                    models.FloatField(
                        blank=True,
                        help_text=(
                            'LLM confidence score (0.0–1.0). '
                            'Null for manually entered signals.'
                        ),
                        null=True,
                        verbose_name='Confidence',
                    ),
                ),
                (
                    'is_inferred',
                    models.BooleanField(
                        default=False,
                        help_text=(
                            'False = verbatim from transcript. '
                            'True = deduced / inferred by LLM.'
                        ),
                        verbose_name='Is Inferred',
                    ),
                ),

                # --- Inherited from BaseSignal: metadata ---
                (
                    'metadata',
                    models.JSONField(
                        blank=True,
                        help_text='Flexible storage for merge history, LLM context, etc.',
                        null=True,
                        verbose_name='Metadata',
                    ),
                ),

                # --- Inherited from BaseSignal: source / language_original ---
                (
                    'source',
                    models.CharField(
                        choices=[
                            ('MANUAL', 'Manual entry'),
                            ('LLM_EXTRACTED', 'LLM extracted'),
                            ('LLM_MODIFIED', 'LLM modified'),
                            ('EXTERNAL_RESEARCH', 'External research'),
                        ],
                        default='MANUAL',
                        help_text='How the signal was created (manual entry vs. LLM)',
                        max_length=20,
                        verbose_name='Source',
                    ),
                ),
                (
                    'language_original',
                    models.CharField(
                        blank=True,
                        help_text='BCP-47 language tag of the source transcript (e.g. "fr", "en-US")',
                        max_length=10,
                        null=True,
                        verbose_name='Original Language',
                    ),
                ),

                # --- Inherited from BaseSignal: lifecycle ---
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('PENDING', 'Pending'),
                            ('VALIDATED', 'Validated'),
                            ('REJECTED', 'Rejected'),
                        ],
                        default='PENDING',
                        help_text=(
                            'PENDING = awaiting rep validation (LLM signals). '
                            'VALIDATED = approved (manual signals start here). '
                            'REJECTED = dismissed. '
                            'MERGED = absorbed into another signal.'
                        ),
                        max_length=20,
                        verbose_name='Status',
                    ),
                ),
                (
                    'validated_at',
                    models.DateTimeField(
                        blank=True,
                        help_text='When the signal was validated (was approved_at in legacy)',
                        null=True,
                        verbose_name='Validated At',
                    ),
                ),

                # --- Inherited from BaseSignal: modification tracking ---
                (
                    'last_modified_at',
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        verbose_name='Last Modified At',
                    ),
                ),
                (
                    'original_value',
                    models.JSONField(
                        blank=True,
                        help_text=(
                            'Snapshot of value before the first manual edit. '
                            'Null for signals that have never been edited.'
                        ),
                        null=True,
                        verbose_name='Original Value',
                    ),
                ),

                # --- TechStack-specific: lifecycle / usage / discontinuation ---
                (
                    'usage_scope',
                    models.CharField(
                        blank=True,
                        choices=[
                            ('TEAM', 'Team'),
                            ('DEPARTMENT', 'Department'),
                            ('COMPANY', 'Company-wide'),
                            ('UNKNOWN', 'Unknown'),
                        ],
                        help_text=(
                            'Organisational scope of the tool usage at this account. '
                            'When DEPARTMENT, usage_department must be set. '
                            'When TEAM / COMPANY / UNKNOWN, usage_department must be null.'
                        ),
                        max_length=20,
                        null=True,
                        verbose_name='Usage Scope',
                    ),
                ),
                (
                    'usage_start_year',
                    models.PositiveIntegerField(
                        blank=True,
                        help_text=(
                            'Year the account started using this tool, when mentioned '
                            '(e.g. 2019). Aggregated by the cluster service to expose '
                            'the earliest observed start year across all observations.'
                        ),
                        null=True,
                        verbose_name='Usage Start Year',
                    ),
                ),
                (
                    'renewal_date',
                    models.DateField(
                        blank=True,
                        help_text=(
                            'Next contract renewal date for this tool, when mentioned. '
                            'The cluster service exposes the most recent observation '
                            'and surfaces an urgency flag when within '
                            'TECHSTACK_RENEWAL_SOON_DAYS from today.'
                        ),
                        null=True,
                        verbose_name='Renewal Date',
                    ),
                ),
                (
                    'cost_description',
                    models.TextField(
                        blank=True,
                        help_text=(
                            'Free-text cost description as expressed during the conversation '
                            '(e.g. "around 3000€/month", "120k$/year", "free tier"). '
                            'Intentionally NOT a structured numeric field — costs are reported '
                            'with widely varying granularity and currency by reps; structured '
                            'capture would lose nuance and force false precision.'
                        ),
                        verbose_name='Cost Description',
                    ),
                ),
                (
                    'is_discontinued',
                    models.BooleanField(
                        default=False,
                        help_text=(
                            'True when the account has stopped using or plans to stop using '
                            'this tool. Drives the conditional discontinued_date requirement '
                            'and a strong negative weight in cluster priority scoring '
                            '(a discontinued tool is a closed door, not an open one).'
                        ),
                        verbose_name='Is Discontinued',
                    ),
                ),
                (
                    'discontinued_date',
                    models.DateField(
                        blank=True,
                        help_text=(
                            'Date of discontinuation — required when is_discontinued is True, '
                            'forbidden otherwise. Past dates indicate already-stopped usage; '
                            'future dates indicate a planned phase-out.'
                        ),
                        null=True,
                        verbose_name='Discontinued Date',
                    ),
                ),
                (
                    'notes',
                    models.TextField(
                        blank=True,
                        help_text='Additional qualitative context about this observation.',
                        verbose_name='Notes',
                    ),
                ),

                # ============================================================
                # FOREIGN KEYS
                # ============================================================
                # NOTE: Order matters in CreateModel — FKs must come AFTER
                # the simple fields above for readability, but Django
                # itself does not care.

                # --- Inherited from BaseSignal: account (required) ---
                (
                    'account',
                    models.ForeignKey(
                        help_text='Account this signal belongs to — required',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='techstacksignal_signals',
                        to='module_accounts.companyaccount',
                        verbose_name='Account',
                    ),
                ),

                # --- Inherited from BaseSignal: source_activity (optional) ---
                (
                    'source_activity',
                    models.ForeignKey(
                        blank=True,
                        help_text='Activity (call/meeting) from which this signal was extracted',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='techstacksignal_signals',
                        to='module_activities.activity',
                        verbose_name='Source Activity',
                    ),
                ),

                # --- Inherited from BaseSignal: audit FKs ---
                (
                    'created_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='signals_techstacksignal_created',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Created By',
                    ),
                ),
                (
                    'updated_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='signals_techstacksignal_updated',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Updated By',
                    ),
                ),
                (
                    'requested_by',
                    models.ForeignKey(
                        blank=True,
                        help_text='User who triggered the LLM extraction (null for manual signals)',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='techstacksignal_requested',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Requested By',
                    ),
                ),
                (
                    'validated_by',
                    models.ForeignKey(
                        blank=True,
                        help_text='Rep who validated this signal (was approved_by in legacy)',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='techstacksignal_validated',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Validated By',
                    ),
                ),
                (
                    'last_modified_by',
                    models.ForeignKey(
                        blank=True,
                        help_text='User who last edited the signal value after creation',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='techstacksignal_modified',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Last Modified By',
                    ),
                ),

                # --- TechStack-specific FKs ---
                (
                    'tech_catalog_entry',
                    models.ForeignKey(
                        help_text=(
                            'Tenant-level master catalog entry identifying the tool. '
                            'Drives canonical_key and cluster identity. Required.'
                        ),
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='tech_stack_signals',
                        to='tech_catalog.techcatalog',
                        verbose_name='Tech Catalog Entry',
                    ),
                ),
                (
                    'usage_department',
                    models.ForeignKey(
                        blank=True,
                        help_text=(
                            'Department using this tool — required when usage_scope=DEPARTMENT, '
                            'forbidden otherwise. Distinct from any inherited "source" '
                            'department (which describes who mentioned the tool, not who '
                            'uses it — and is shadow-overridden away on this signal).'
                        ),
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='tech_stack_signals_using',
                        to='core_modules.standarddepartment',
                        verbose_name='Usage Department',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Tech Stack Signal',
                'verbose_name_plural': 'Tech Stack Signals',
                'db_table': 'module_signals_tech_stack',
                'ordering': ['-created_at'],
                'abstract': False,
            },
        ),

        # ================================================================
        # 3. Indexes (declared on TechStackSignal.Meta.indexes)
        # ================================================================
        migrations.AddIndex(
            model_name='techstacksignal',
            index=models.Index(
                fields=['account'],
                name='tssig_account_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='techstacksignal',
            index=models.Index(
                fields=['tech_catalog_entry'],
                name='tssig_catalog_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='techstacksignal',
            index=models.Index(
                fields=['status'],
                name='tssig_status_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='techstacksignal',
            index=models.Index(
                fields=['is_discontinued'],
                name='tssig_discontinued_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='techstacksignal',
            index=models.Index(
                fields=['account', 'canonical_key'],
                name='tssig_account_canon_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='techstacksignal',
            index=models.Index(
                fields=['renewal_date'],
                name='tssig_renewal_idx',
            ),
        ),
    ]