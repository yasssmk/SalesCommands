# app_modules/quotas/models.py
"""
Quota model — a user's PERSONAL Sales objective.

This is a personal planning tool, NOT a hierarchical salary quota system: each
user sets THEIR OWN objectives (metric, target, dates of their choosing). A
manager and an admin only READ within their scope; nobody assigns an objective
to someone else — the creator IS the owner.

A Quota can optionally be declined onto one campaign (``source_campaign``); when
null the objective is global.

Lifecycle state (past / current / future) is DERIVED from the window against
today — there is no stored ``is_current`` flag, and no overlap validation: a
user may hold several concurrent, overlapping objectives on purpose.
"""

from datetime import date

from django.db import models
from django.utils.translation import gettext_lazy as _

from app_modules.core_modules.models import ModuleBaseModel
from core.client_scope import ClientScopeManager

# Single source of truth for the six canonical metrics (sub-step 1). We import
# the vocabulary — we never re-declare a parallel list here.
from app_modules.bi.metrics import MetricKey


class QuotaState(models.TextChoices):
    """Derived lifecycle state of a quota's window relative to today."""
    PAST = 'PAST', _('Past')
    CURRENT = 'CURRENT', _('Current')
    FUTURE = 'FUTURE', _('Future')


class Quota(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """A user's personal, periodised Sales objective on one canonical metric."""

    # ==========================================================================
    # OWNERSHIP — the creator is the owner; there is no separate assigner.
    # ==========================================================================

    owner = models.ForeignKey(
        'end_users.User',
        on_delete=models.CASCADE,
        related_name='quotas',
        verbose_name=_('Owner'),
        help_text=_('User who owns this objective (always the creator).'),
    )

    # ==========================================================================
    # DEFINITION
    # ==========================================================================

    metric = models.CharField(
        max_length=30,
        choices=MetricKey.choices,
        verbose_name=_('Metric'),
        help_text=_('Which canonical Sales metric this objective targets.'),
    )

    target_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name=_('Target Value'),
        help_text=_('Target to reach (Decimal covers both amounts and counts).'),
    )

    period_start = models.DateField(
        verbose_name=_('Period Start'),
        help_text=_('First day of the objective window.'),
    )

    period_end = models.DateField(
        verbose_name=_('Period End'),
        help_text=_('Last day of the objective window.'),
    )

    # ==========================================================================
    # OPTIONAL CAMPAIGN DECLINATION — null = global objective.
    # ==========================================================================

    source_campaign = models.ForeignKey(
        'module_campaigns.Campaign',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quotas',
        verbose_name=_('Source Campaign'),
        help_text=_(
            'Optional campaign this objective is declined onto. When null the '
            'objective is global (measured across all of the owner\'s work).'
        ),
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints()):
        db_table = 'quotas'
        verbose_name = _('Quota')
        verbose_name_plural = _('Quotas')
        ordering = ['-period_start', '-created_at']
        indexes = [
            models.Index(fields=['owner'], name='quota_owner_idx'),
            models.Index(fields=['owner', 'metric'], name='quota_owner_metric_idx'),
            models.Index(fields=['period_start', 'period_end'], name='quota_window_idx'),
            models.Index(fields=['source_campaign'], name='quota_source_campaign_idx'),
        ]

    def __str__(self):
        return f"{self.owner_id} · {self.metric} · {self.target_value}"

    # ==========================================================================
    # DERIVED STATE — no stored flag; computed from the window vs today.
    # ==========================================================================

    def get_state(self, today=None):
        """Return the QuotaState of this objective relative to ``today``.

        CURRENT when the window covers today (inclusive on both bounds); PAST
        when the window ended before today; FUTURE when it starts after today.
        """
        today = today or date.today()
        if self.period_end < today:
            return QuotaState.PAST
        if self.period_start > today:
            return QuotaState.FUTURE
        return QuotaState.CURRENT

    @property
    def state(self):
        """Derived lifecycle state against today (see get_state)."""
        return self.get_state()

    @property
    def is_current(self):
        """True when the window covers today. Derived — NOT a stored field."""
        return self.get_state() == QuotaState.CURRENT
