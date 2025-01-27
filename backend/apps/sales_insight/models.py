from django.db import models
from django.utils.translation import gettext_lazy as _
from end_users.models import User
from apps.core_apps.models import BaseModelApp

class SalesInsight(BaseModelApp):
    """
    Stores sales insights related to an account, an organizational unit, or a sales qualification process.
    """

    class InsightType(models.TextChoices):
        ACCOUNT = 'ACCOUNT', _('Account-Wide Insight')
        ORG_UNIT = 'ORG_UNIT', _('Department-Level Insight')
        QUALIFICATION = 'QUALIFICATION', _('Sales Qualification Insight')

    insight_type = models.CharField(
        max_length=20, 
        choices=InsightType.choices, 
        verbose_name=_("Insight Type")
    )

    account = models.ForeignKey(
        'accounts.Account', on_delete=models.CASCADE, blank=True, null=True, related_name="insights_as_account"
    )
    # org_unit = models.ForeignKey(
    #     'OrgUnit', on_delete=models.CASCADE, blank=True, null=True, related_name="sales_insights"
    # )
    # sales_qualification = models.ForeignKey(
    #     'SalesQualification', on_delete=models.CASCADE, blank=True, null=True, related_name="sales_insights"
    # )

    buying_process = models.JSONField(blank=True, null=True, verbose_name=_("Buying Process"))
    pain_points = models.JSONField(blank=True, null=True, verbose_name=_("Pain Points"))
    business_impact = models.JSONField(blank=True, null=True, verbose_name=_("Business Impact"))
    success_criteria = models.JSONField(blank=True, null=True, verbose_name=_("Success Criteria"))
    strategic_goals = models.JSONField(blank=True, null=True, verbose_name=_("Strategic Goals"))
    technology_stack = models.JSONField(blank=True, null=True, verbose_name=_("Technology Stack"))
    budgets = models.JSONField(blank=True, null=True, verbose_name=_("Budgets"))


    class Meta:
        db_table = 'sales_insights'
        verbose_name = _("Sales Insight")
        verbose_name_plural = _("Sales Insights")
        indexes = [
            models.Index(fields=['account'])
            # models.Index(fields=['org_unit']),
            # models.Index(fields=['sales_qualification']),
        ]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Sales Insight ({self.insight_type}) - {self.account or self.org_unit or self.sales_qualification}"

