# app_modules/signals/migrations/0015_blockersignal.py
"""
Introduce BlockerSignal — concrete signal for deal-blocking objections.

BlockerSignal sits alongside PainSignal / ObjectiveSignal / ImpactSignal /
TechStackSignal but intentionally does NOT participate in cluster
aggregation:

  * `signal_category` is shadow-overridden to None on the concrete model
    — no column is created here.
  * `canonical_key` is inherited from BaseSignal for shape consistency
    (the column exists and is indexed) but is never populated — see
    BlockerSignal.save().
  * Cache invalidation is wired to SIGNALS_CACHE_TAG only, never to
    SIGNAL_CLUSTERS_CACHE_TAG (see app_modules/signals/signals/cache_invalidation.py).

Schema notes:

  * source_activity FK is nullable in the DB (mirror of the BaseSignal
    abstract definition). The model's clean() enforces "required" at
    the application layer for blockers, exactly like PainSignal.clean()
    does. The DB-level nullable matches the abstract base and avoids a
    bespoke ALTER TABLE here.

  * `contact` is a SET_NULL FK to module_contacts.Contact. Optional —
    not every blocker is attributable to a single contact.

  * No `what` / `dimension` columns — blockers carry no canonical axes.
"""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('decision_cycles', '0012_decisioncycle_source_campaign'),
        ('module_accounts', '0003_alter_companyaccount_industry'),
        ('module_activities', '0017_activity_source_decision_cycle'),
        ('module_campaigns', '0014_campaign_channel_override'),
        ('module_contacts', '0002_remove_contact_module_cont_first_n_da6ea2_idx_and_more'),
        ('module_signals', '0014_drop_painimpact_add_impactsignal_and_scope'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BlockerSignal',
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
                ('summary', models.TextField(help_text='Free-text description of the blocker as raised during the conversation (objection, hesitation, missing information, budget concern, timing constraint, etc.). No canonical taxonomy — blockers are captured verbatim.', verbose_name='Summary')),
            ],
            options={
                'verbose_name': 'Blocker Signal',
                'verbose_name_plural': 'Blocker Signals',
                'db_table': 'module_signals_blocker',
                'ordering': ['-created_at'],
                'abstract': False,
            },
        ),

        # --- BlockerSignal FKs ---
        migrations.AddField(
            model_name='blockersignal',
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
            model_name='blockersignal',
            name='source_activity',
            field=models.ForeignKey(
                blank=True,
                help_text='Activity (call/meeting) from which this signal was extracted',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='%(class)s_signals',
                to='module_activities.activity',
                verbose_name='Source Activity',
            ),
        ),
        migrations.AddField(
            model_name='blockersignal',
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
            model_name='blockersignal',
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
            model_name='blockersignal',
            name='contact',
            field=models.ForeignKey(
                blank=True,
                help_text='Optional FK to the Contact who raised the blocker. Nullable: not every blocker is attributable to a single contact (a company-wide budget stance has no single originator). SET_NULL preserves the blocker as a deal-level observation even when its attribution is lost.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='blocker_signals',
                to='module_contacts.contact',
                verbose_name='Contact',
            ),
        ),
        migrations.AddField(
            model_name='blockersignal',
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
            model_name='blockersignal',
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
            model_name='blockersignal',
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
        migrations.AddField(
            model_name='blockersignal',
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

        # --- BlockerSignal indexes ---
        migrations.AddIndex(
            model_name='blockersignal',
            index=models.Index(fields=['account'], name='blksig_account_idx'),
        ),
        migrations.AddIndex(
            model_name='blockersignal',
            index=models.Index(fields=['status'], name='blksig_status_idx'),
        ),
        migrations.AddIndex(
            model_name='blockersignal',
            index=models.Index(fields=['contact'], name='blksig_contact_idx'),
        ),
        migrations.AddIndex(
            model_name='blockersignal',
            index=models.Index(
                fields=['account', 'source_activity'],
                name='blksig_account_activity_idx',
            ),
        ),
    ]
