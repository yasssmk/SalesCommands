from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import BaseModel
from .organization import Organization
from .client_account import ClientAccount


class Team(BaseModel):
    """
    Équipe SANS client scoping pour simplifier
    """
    name = models.CharField(
        max_length=100, 
        help_text=_("Name of the team")
    )

    client_account = models.ForeignKey(
        ClientAccount,
        on_delete=models.CASCADE,
        related_name='teams',
        help_text=_("Client this team belongs to."),
    )

    # organization = models.ForeignKey(
    #     Organization,
    #     on_delete=models.CASCADE,
    #     related_name='teams',
    #     help_text=_("Organization this team belongs to."),
    # )

    parent_team = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='direct_child_teams',
        help_text=_("Direct parent team in the hierarchy."),
    )

    manager = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_teams',
        help_text=_("Manager of the team."),
    )

    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Process Description')
    )

    class Meta:
        db_table = 'teams'
        verbose_name = _('team')
        verbose_name_plural = _('teams')
        unique_together = ('name', 'client_account')
        ordering = ['name']

    def __str__(self):
        """
        Human-readable team representation.
        """
        return f"{self.name} ({self.client_account.name})"
    
    @property
    def client_id(self):
        return self.client_account_id
    
    def get_full_hierarchy(self):
        """
        Return ancestor teams and direct child teams for this team.
        
        This helper is MVP-level and meant for read-only use.
        It does not enforce business rules or validation.
        """
        hierarchy = {
            'parents': [],
            'children': list(self.direct_child_teams.all())
        }

        current = self
        while current.parent_team:
            hierarchy['parents'].append(current.parent_team)
            current = current.parent_team

        return hierarchy