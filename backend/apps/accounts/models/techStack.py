# apps/accounts_app/accounts/models.py (or in a new file tech_stack.py if you prefer)

from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core_apps.models import BaseModelApp
from core.client_scope import ClientScopeManager
from .accounts import Account
from apps.core_apps.models import AccountLinkedModel

class TechStack(BaseModelApp, AccountLinkedModel, ClientScopeManager.ModelMixin):
    """
    Model to track technologies used by an account.
    """
    tech_name = models.CharField(
        max_length=255,
        verbose_name=_('Technology Name')
    )
    
    purpose = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Purpose')
    )
    
    pros = models.JSONField(
        blank=True,
        null=True,
        default=list,
        verbose_name=_('Pros')
    )
    
    cons = models.JSONField(
        blank=True,
        null=True,
        default=list,
        verbose_name=_('Cons')
    )
    
    annual_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_('Annual Cost')
    )
    
    renewal_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Renewal Date')
    )
    
    years_of_usage = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_('Years of Usage')
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes')
    )
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints()):
        verbose_name = _('Tech Stack')
        verbose_name_plural = _('Tech Stacks')
        ordering = ['tech_name']
    
    def __str__(self):
        return f"{self.tech_name} ({self.account.company_name})"