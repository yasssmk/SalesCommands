# app_modules/campaigns/models/campaign_objective.py
"""
CampaignObjective model — measurable goals for a campaign.

6 objective types aligned with DecisionCycle and Activity tracking:
- MEETINGS: Activity.type=MEETING + COMPLETED
- DECISION_CYCLES: DecisionCycle created via campaign
- CONTACTS_REACHED: Distinct contacts with COMPLETED activities
- PIPELINE_VALUE: SUM(DecisionCycle.estimated_value) open cycles
- REVENUE_WON: SUM(DecisionCycle.estimated_value) WHERE outcome=WON
- NEW_LOGOS: CompanyAccount.type PROSPECT → CLIENT via campaign

Each campaign can have multiple objectives, but only one is_primary.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from app_modules.core_modules.models import ModuleBaseModel
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignModuleErrorMessages


class ObjectiveType(models.TextChoices):
    """Campaign objective type choices."""
    MEETINGS = 'MEETINGS', _('Number of Meetings')
    DECISION_CYCLES = 'DECISION_CYCLES', _('Decision Cycles Opened')
    CONTACTS_REACHED = 'CONTACTS_REACHED', _('Contacts Reached')
    PIPELINE_VALUE = 'PIPELINE_VALUE', _('Pipeline Value')
    REVENUE_WON = 'REVENUE_WON', _('Revenue Won')
    NEW_LOGOS = 'NEW_LOGOS', _('New Logos')


class CampaignObjective(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Measurable objective for a campaign.

    Features:
        - 6 objective types covering the full sales funnel
        - Target value with dynamic current_value calculation
        - One primary objective per campaign (enforced via constraint)
        - Multi-tenant isolation via ClientScopeManager.ModelMixin
    """

    # ==========================================================================
    # RELATIONSHIPS
    # ==========================================================================

    campaign = models.ForeignKey(
        'module_campaigns.Campaign',
        on_delete=models.CASCADE,
        related_name='objectives',
        verbose_name=_('Campaign')
    )

    # ==========================================================================
    # CORE FIELDS
    # ==========================================================================

    name = models.CharField(
        max_length=100,
        verbose_name=_('Objective Name')
    )

    objective_type = models.CharField(
        max_length=30,
        choices=ObjectiveType.choices,
        verbose_name=_('Objective Type')
    )

    target_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('Target Value')
    )

    is_primary = models.BooleanField(
        default=False,
        verbose_name=_('Is Primary'),
        help_text=_('Only one primary objective per campaign')
    )

    # ==========================================================================
    # META
    # ==========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['campaign', 'objective_type'],
        index_fields=['is_primary']
    )):
        db_table = 'module_campaign_objectives'
        verbose_name = _('Campaign Objective')
        verbose_name_plural = _('Campaign Objectives')
        ordering = ['campaign', '-is_primary', 'created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['campaign'],
                condition=models.Q(is_primary=True),
                name='mod_unique_primary_objective_per_campaign'
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_objective_type_display()}) - Target: {self.target_value}"

    # ==========================================================================
    # CALCULATED VALUES
    # ==========================================================================

    def get_current_value(self):
        """
        Calculate current value based on objective type.

        Delegates to CampaignAnalyticsService to avoid duplicating query logic.
        Uses deferred import to avoid circular dependency.
        """
        from app_modules.campaigns.services.campaign_analytics_service import CampaignAnalyticsService
        service = CampaignAnalyticsService(client_id=self.client_id)
        return service._calculate_objective_value(self.campaign, self)

    def get_progress_percentage(self):
        """Calculate progress as percentage of target."""
        if not self.target_value or self.target_value == 0:
            return 0.0

        current = self.get_current_value()
        return round((current / float(self.target_value)) * 100, 1)

    # ==========================================================================
    # VALIDATION
    # ==========================================================================

    def clean(self):
        """Validate objective data."""
        super().clean()

        if self.target_value is not None and self.target_value <= 0:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.OBJECTIVE_TARGET_VALUE_INVALID
            )