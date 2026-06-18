# app_modules/ai_pipelines/migrations/0005_prep_call_snapshot.py
"""
Create PrepCallSnapshot table.

Activity-scoped snapshot storing the structured tactical brief
produced by the prep-call AI pipeline. Mirrors DealHealthSnapshot
(in decision_cycles) but scoped to an Activity.

Cross-app dependencies:
  - module_activities — Activity FK (CASCADE)
  - module_contacts   — Contact FK (SET_NULL)
  - module_ai_pipelines/0004 — AIPipelineRun FK (SET_NULL)
    and PREP_CALL in AIPipelineType choices
"""

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('module_ai_pipelines', '0004_add_prep_call_pipeline_type'),
        ('module_activities', '0019_add_demo_activity_type'),
        ('module_contacts', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PrepCallSnapshot',
            fields=[
                (
                    'id',
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    'client_id',
                    models.UUIDField(
                        db_index=True,
                        editable=False,
                        help_text='ID of the client company this record belongs to',
                        verbose_name='Client ID',
                    ),
                ),
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
                (
                    'brief_mode',
                    models.CharField(
                        choices=[
                            ('DISCOVERY', 'Discovery'),
                            ('CONVICTION', 'Conviction'),
                            ('PROOF', 'Proof'),
                            ('DECISION', 'Decision'),
                        ],
                        help_text=(
                            'Deterministic mode resolved from the maturity '
                            'snapshot before the LLM call.'
                        ),
                        max_length=20,
                        verbose_name='Brief Mode',
                    ),
                ),
                (
                    'brief',
                    models.JSONField(
                        help_text=(
                            'LLM output: context, objectives, rhetoric, '
                            'gaps, next_step.'
                        ),
                        verbose_name='Structured Brief',
                    ),
                ),
                (
                    'input_hash',
                    models.CharField(
                        help_text=(
                            'SHA-256 of the Prep Input Pack for idempotence '
                            '(DB-layer dedup).'
                        ),
                        max_length=64,
                        verbose_name='Input Hash',
                    ),
                ),
                (
                    'snapshot_date',
                    models.DateTimeField(
                        auto_now_add=True,
                        verbose_name='Snapshot Date',
                    ),
                ),
                (
                    'activity',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='prep_call_snapshots',
                        to='module_activities.activity',
                        verbose_name='Activity',
                    ),
                ),
                (
                    'created_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='%(app_label)s_%(class)s_created',
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
                        related_name='%(app_label)s_%(class)s_updated',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Updated By',
                    ),
                ),
                (
                    'pipeline_run',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='prep_call_snapshots',
                        to='module_ai_pipelines.aipipelinerun',
                        verbose_name='Pipeline Run',
                    ),
                ),
                (
                    'target_contact',
                    models.ForeignKey(
                        blank=True,
                        help_text=(
                            'Primary stakeholder this brief is prepared for. '
                            'Null when the AE did not specify a contact.'
                        ),
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='prep_call_briefs',
                        to='module_contacts.contact',
                        verbose_name='Target Contact',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Prep Call Snapshot',
                'verbose_name_plural': 'Prep Call Snapshots',
                'db_table': 'prep_call_snapshots',
                'ordering': ['-snapshot_date'],
                'indexes': [
                    models.Index(
                        fields=['activity', '-snapshot_date'],
                        name='pc_act_date_idx',
                    ),
                    models.Index(
                        fields=['input_hash'],
                        name='pc_input_hash_idx',
                    ),
                ],
            },
        ),
    ]
