# apps/account/models/buyingprocess.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core_apps.models import BaseModelApp, AccountLinkedModel
from core.client_scope import ClientScopeManager
from apps.accounts.models.contacts import Contact 

class BuyingProcessStep(BaseModelApp, AccountLinkedModel, ClientScopeManager.ModelMixin):
    """
    Model to track steps in an account's buying process.
    """
    step_index = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_('Step Index'),
        help_text=_('Order of this step in the process')
    )
    
    stakeholder = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Stakeholder')
    )
    
    department_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Department Name')
    )
    
    step_description = models.TextField(
        verbose_name=_('Step Description')
    )
    
    step_goal = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Step Goal')
    )
    
    influence_score = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_('Influence Score'),
        help_text=_('Score from 0-100 indicating influence level')
    )
    
    criterias = models.JSONField(
        blank=True,
        null=True,
        default=list,
        verbose_name=_('Criterias')
    )
    
    metrics = models.JSONField(
        blank=True,
        null=True,
        default=list,
        verbose_name=_('metrics')
    )
    
    average_time_in_days = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Average Time in Days')
    )
    
    contacts = models.ManyToManyField(
        Contact,
        through='BuyingProcessStepContact',
        related_name='buying_process_steps',
        verbose_name=_('Contacts')
    )
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints()):
        verbose_name = _('Buying Process Step')
        verbose_name_plural = _('Buying Process Steps')
        ordering = ['account', 'step_index']
        
    def __str__(self):
        return f"{self.account.company_name} - Step {self.step_index}: {self.step_description[:30]}"


class BuyingProcessStepContact(BaseModelApp):
    """Junction table linking buying process steps to contacts."""
    step = models.ForeignKey(
        'accounts_new.BuyingProcessStep',  
        on_delete=models.CASCADE,
        related_name='step_contacts',
        verbose_name=_('Step')
    )
    
    contact = models.ForeignKey(
        'accounts_new.Contact',
        on_delete=models.CASCADE,
        related_name='contact_steps',
        verbose_name=_('Contact')
    )
    
    
    class Meta:
        verbose_name = _('Buying Process Step Contact')
        verbose_name_plural = _('Buying Process Step Contacts')
        unique_together = ('step', 'contact')
        
    def __str__(self):
        return f"{self.step} - {self.contact}"