# apps/account/models/buyingprocess.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core_apps.models import BaseModelApp, AccountLinkedModel, HistoricalTrackingModel
from core.client_scope import ClientScopeManager
from apps.accounts.models.contacts import Contact
from apps.core_apps.models import StandardDepartment
from django.db.models import Sum

class BuyingProcess(BaseModelApp, AccountLinkedModel, HistoricalTrackingModel, ClientScopeManager.ModelMixin):
    """
    Model to represent a buying process for an account.
    An account can have multiple buying processes (e.g., for different products/divisions).
    """
    name = models.CharField(
        max_length=255,
        verbose_name=_('Process Name')
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Process Description')
    )
    
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='buying_processes',
        verbose_name=_('Related Product')
    )
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints()):
        verbose_name = _('Buying Process')
        verbose_name_plural = _('Buying Processes')
        ordering = ['-updated_at']
        unique_together = [('account', 'name'), ('account', 'product')]
        
    def __str__(self):
        return f"{self.name} - {self.account.company_name}"
    
    @property
    def estimated_timeline_days(self):
        """
        Calculate the estimated timeline days by summing the average_time_in_days of all steps.
        Returns None if any step has a missing average_time_in_days.
        """
        steps = self.steps.all()
        
        # Check if any step has a null/zero average_time_in_days
        if steps.filter(average_time_in_days__isnull=True).exists() or steps.filter(average_time_in_days=0).exists():
            return None
            
        # If no steps, return 0
        if not steps.exists():
            return 0
            
        # Sum the average_time_in_days of all steps
        total_days = steps.aggregate(Sum('average_time_in_days'))['average_time_in_days__sum']
        return total_days
    
class BuyingProcessStep(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Model to track steps in an account's buying process.
    """
    process = models.ForeignKey(
        BuyingProcess,
        on_delete=models.CASCADE,
        related_name='steps',
        verbose_name=_('Buying Process')
    )
    
    account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        verbose_name=_('Account'),
        related_name='buying_process_steps'
    )
    
    previous_step = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='next_steps',
        blank=True,
        null=True,
        verbose_name=_('Previous Step')
    )
    
    stakeholder = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Stakeholder')
    )
    
    standard_department = models.ForeignKey(
        StandardDepartment,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_('Department')
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
        blank=True,
        null=True,
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
        ordering = ['id']  # Default ordering by ID
        
    def __str__(self):
        return f"{self.process.name} - {self.step_description[:30]}"
    
    @property
    def next_step(self):
        """Get the next step in the process."""
        try:
            return self.next_steps.first()
        except:
            return None
    
    def save(self, *args, **kwargs):
        """Override save to ensure account matches process account."""
        if self.process and not self.account_id:
            self.account = self.process.account
        super().save(*args, **kwargs)


class BuyingProcessStepContact(BaseModelApp, ClientScopeManager.ModelMixin):
    """Junction table linking buying process steps to contacts."""
    step = models.ForeignKey(
        'accounts.BuyingProcessStep',  
        on_delete=models.CASCADE,
        related_name='step_contacts',
        verbose_name=_('Step')
    )
    
    contact = models.ForeignKey(
        'accounts.Contact',
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