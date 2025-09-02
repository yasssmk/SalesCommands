from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import BaseModel
from .organization import Organization


class Team(BaseModel):
    """
    Équipe SANS client scoping pour simplifier
    """
    name = models.CharField(
        max_length=100, 
        help_text=_("Name of the team")
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='teams',
        help_text=_("Organization this team belongs to."),
    )
    manager = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_teams',
        help_text=_("Manager of the team."),
    )

    class Meta:
        db_table = 'teams'
        verbose_name = _('team')
        verbose_name_plural = _('teams')
        unique_together = ('name', 'organization')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.organization.name} - {self.organization.client_account.name})"
    
    @property
    def client_id(self):
        return self.client_account_id