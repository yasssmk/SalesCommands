from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core_apps.models import BaseModelApp, AccountLinkedModel
from core.client_scope import ClientScopeManager

# Create your models here.
class Opportunity(BaseModelApp, AccountLinkedModel, ClientScopeManager.ModelMixin):

    """
    Represents a sales opportunity for an account.
    """
    name = models.CharField(
        max_length=255,
        verbose_name=_('Opportunity Name')
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Opportunity Description')
    )
    
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Opportunity Value')
    )
    
    probability = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name=_('Probability of Closing (%)')
    )
    
    expected_close_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Expected Close Date')
    )
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints()):
        verbose_name = _('Opportunity')
        verbose_name_plural = _('Opportunities')
        ordering = ['-updated_at']
        
    def __str__(self):
        return f"{self.name} - {self.account.company_name}"