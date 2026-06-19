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
        choices=[
            ('DISCOVERY', _('Discovery')),
            ('CONVICTION', _('Conviction')),
            ('PROOF', _('Proof')),
            ('DECISION', _('Decision')),
        ],
        verbose_name=_('Brief Mode'),
        help_text=_(
            'Deterministic mode resolved from the maturity snapshot '
            'before the LLM call.'
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
            f"{self.get_brief_mode_display()} — "
            f"{self.activity_id}"
        )
