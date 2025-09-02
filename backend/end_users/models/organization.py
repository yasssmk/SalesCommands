from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core_apps.models import BaseModelApp
from .client_account import ClientAccount
from core.models import BaseModel

class Organization(BaseModel):
    """
    Organisation SANS client scoping pour simplifier
    """
    name = models.CharField(
        max_length=100, 
        help_text=_("Name of the organization (e.g., Sales, Management).")
    )

    manager = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_organizations',
        help_text=_("Director or main manager of the organization."),
    )

    client_account = models.ForeignKey(
        ClientAccount,
        on_delete=models.CASCADE,
        related_name='organizations',
        help_text=_("Client this organization belongs to."),
    )

    class Meta:
        db_table = 'organizations'
        verbose_name = _('organization')
        verbose_name_plural = _('organizations')
        unique_together = ('name', 'client_account')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.client_account.name})"
    
    # @property
    # def client_account(self):
    #     return self.client_id

    @property
    def client_id(self):
        """Helper property for client ID access."""
        return self.client_account_id