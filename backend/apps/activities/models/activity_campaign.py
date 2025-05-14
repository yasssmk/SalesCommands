from core_apps.models import BaseModelApp
from core.client_scope import ClientScopeManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.activities.models import Activity

class ActivityCampaign(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Tracks campaign-related information for activities
    Separate model to keep Activity clean
    """
    activity = models.OneToOneField(
        Activity,
        on_delete=models.CASCADE,
        related_name='campaign_info',
        verbose_name=_('Activity')
    )
    
    campaign = models.ForeignKey(
        'campaign.Campaign',
        on_delete=models.CASCADE,
        related_name='activity_campaigns',
        verbose_name=_('Campaign')
    )
    
    campaign_target = models.ForeignKey(
        'campaign.CampaignTarget',
        on_delete=models.CASCADE,
        related_name='activity_campaigns',
        verbose_name=_('Campaign Target')
    )
    
    # Tracking campaign-specific outcomes
    meeting_scheduled = models.BooleanField(
        default=False,
        verbose_name=_('Meeting Scheduled')
    )
    
    opportunity_created = models.BooleanField(
        default=False,
        verbose_name=_('Opportunity Created')
    )
    
    class Meta:
        verbose_name = _('Activity Campaign Information')
        verbose_name_plural = _('Activity Campaign Information')
        indexes = [
            models.Index(fields=['campaign', 'activity']),
            models.Index(fields=['campaign_target']),
        ]