# app_modules/ai_pipelines/models/prep_call.py
"""
PrepCallSnapshot — activity-scoped snapshot storing the structured
tactical brief produced by the prep-call AI pipeline.

One PrepCallSnapshot per (activity, run). Multiple runs on the same
Activity create multiple snapshots — the latest one is exposed via
the by-activity endpoint.

Mirrors the DealHealthSnapshot pattern (in decision_cycles/models.py)
but scoped to an Activity instead of a DecisionCycle, and storing a
tactical brief instead of a diagnostic.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from app_modules.core_modules.models.moduleBaseModels import ModuleBaseModel
from core.client_scope import ClientScopeManager

from ..constants import PREP_CALL_SCHEMA_V1, PrepCallBriefMode, PrepCallOutputKind


class PrepCallSnapshot(ModuleBaseModel, ClientScopeManager.ModelMixin):

    activity = models.ForeignKey(
        'module_activities.Activity',
        on_delete=models.CASCADE,
        related_name='prep_call_snapshots',
        verbose_name=_('Activity'),
    )

    pipeline_run = models.ForeignKey(
        'module_ai_pipelines.AIPipelineRun',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prep_call_snapshots',
        verbose_name=_('Pipeline Run'),
    )

    target_contact = models.ForeignKey(
        'module_contacts.Contact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prep_call_briefs',
        verbose_name=_('Target Contact'),
        help_text=_(
            'Primary stakeholder this brief is prepared for. '
            'Null when the AE did not specify a contact.'
        ),
    )

    brief_mode = models.CharField(
        max_length=20,
        choices=PrepCallBriefMode.choices,
        null=True,
        blank=True,
        verbose_name=_('Brief Mode'),
        help_text=_(
            'v1 only: the deterministic mode resolved from the maturity '
            'snapshot before the LLM call. Empty from v2 (single mode).'
        ),
    )

    # -------------------------------------------------------------------------
    # v2 — sprint 2 Game Plan, G2
    # -------------------------------------------------------------------------

    schema_version = models.PositiveSmallIntegerField(
        default=PREP_CALL_SCHEMA_V1,
        verbose_name=_('Schema Version'),
        help_text=_(
            'Shape of `brief`: 1 = the v1 tactical brief, 2 = the Game Plan / '
            'message (constants PREP_CALL_SCHEMA_V*).'
        ),
    )

    output_kind = models.CharField(
        max_length=20,
        choices=PrepCallOutputKind.choices,
        default=PrepCallOutputKind.PLAN,
        verbose_name=_('Output Kind'),
        help_text=_('PLAN (a conversation) or MESSAGE (an email / LinkedIn message).'),
    )

    deal_health_snapshot = models.ForeignKey(
        'decision_cycles.DealHealthSnapshot',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prep_call_snapshots',
        verbose_name=_('Deal Health Snapshot read'),
        help_text=_('The deal-health snapshot the generation read (trace).'),
    )

    deal_health_schema_version = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Deal Health Schema Version read'),
        help_text=_(
            'schema_version of that deal-health snapshot at generation time '
            '(kept if the snapshot is deleted).'
        ),
    )

    brief = models.JSONField(
        verbose_name=_('Structured Brief'),
        help_text=_(
            'LLM output: context, objectives, rhetoric, gaps, next_step.'
        ),
    )

    input_hash = models.CharField(
        max_length=64,
        verbose_name=_('Input Hash'),
        help_text=_(
            'SHA-256 of the Prep Input Pack for idempotence '
            '(DB-layer dedup).'
        ),
    )

    snapshot_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Snapshot Date'),
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        index_fields=[],
    )):
        app_label = 'module_ai_pipelines'
        db_table = 'prep_call_snapshots'
        verbose_name = _('Prep Call Snapshot')
        verbose_name_plural = _('Prep Call Snapshots')
        ordering = ['-snapshot_date']
        indexes = [
            models.Index(
                fields=['activity', '-snapshot_date'],
                name='pc_act_date_idx',
            ),
            models.Index(
                fields=['input_hash'],
                name='pc_input_hash_idx',
            ),
        ]

    def __str__(self):
        return (
            f"PrepCall {self.snapshot_date} — "
            f"{self.get_brief_mode_display() or self.get_output_kind_display()} — "
            f"{self.activity_id}"
        )
