from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import BaseModel
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from apps.core_apps.models import BaseModelApp
from .client_account import ClientAccount


class UserRole(BaseModel):
    """
    Rôles utilisateur avec gestion explicite des tiers.
    PAS d'auto-détection dans le modèle - la validation se fait dans les serializers.
    """
    name = models.CharField(
        max_length=50, 
        help_text=_("Role name")
    )
    read = models.BooleanField(default=True)
    write = models.BooleanField(default=False)
    modify = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)

    # Champs de tier - exactement UN doit être True
    is_admin = models.BooleanField(
        default=False,
        help_text="Administrator tier - full client access"
    )
    is_manager = models.BooleanField(
        default=False,
        help_text="Manager tier - team access"
    )
    is_individual = models.BooleanField(
        default=False,
        help_text="Individual tier - personal access"
    )

    is_locked = models.BooleanField(
        default=False,
        help_text="System role - cannot be modified or deleted"
    )

    # Référence vers ClientAccount pour compatibilité
    client_account = models.ForeignKey(
        ClientAccount,
        on_delete=models.CASCADE,
        related_name='roles',
        help_text=_("Client this role belongs to."),
    )
    

    class Meta:
        db_table = 'users_roles'
        verbose_name = _('user_role')
        verbose_name_plural = _('users_roles')
        unique_together = ('name', 'client_account')
        ordering = ['name']
        constraints = [
            # Assurer qu'exactement un tier est actif
            models.CheckConstraint(
                check=(
                    models.Q(is_admin=True, is_manager=False, is_individual=False) |
                    models.Q(is_admin=False, is_manager=True, is_individual=False) |
                    models.Q(is_admin=False, is_manager=False, is_individual=True)
                ),
                name='exactly_one_tier_active'
            )
        ]

    def __str__(self):
        tier = self.get_tier()
        return f"{self.name} ({tier}) - {self.client_account.name}"
    
    def save(self, *args, **kwargs):
        """
        Save method simplifiée - PAS d'auto-détection des tiers.
        La validation des tiers se fait dans les serializers.
        La contrainte DB s'assure qu'exactement un tier est actif.
        """
        # Validation basique : au moins un tier doit être actif
        tier_count = sum([self.is_admin, self.is_manager, self.is_individual])
        
        if tier_count == 0:
            # Si aucun tier n'est défini, forcer individual par défaut
            # Ceci ne devrait arriver que pour des opérations directes sur le modèle
            # (bypassing serializers), comme dans les tests ou migrations
            self.is_individual = True
            self.is_admin = False
            self.is_manager = False
        elif tier_count > 1:
            # Si plusieurs tiers sont actifs, lever une exception standard
            active_tiers = []
            if self.is_admin:
                active_tiers.append('is_admin')
            if self.is_manager:
                active_tiers.append('is_manager')
            if self.is_individual:
                active_tiers.append('is_individual')
            
            # Utiliser l'exception standard du projet
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(
                    detail=f"Only one tier can be active. Currently active: {', '.join(active_tiers)}"
                )
            )
        
        super().save(*args, **kwargs)
    
    def get_tier(self) -> str:
        """
        Get the active tier as a string.
        Returns 'admin', 'manager', or 'individual'.
        """
        if self.is_admin:
            return 'admin'
        elif self.is_manager:
            return 'manager'
        elif self.is_individual:
            return 'individual'
        else:
            # Ne devrait jamais arriver grâce à la contrainte DB
            return 'unknown'
    
    def get_permissions_summary(self) -> dict:
        """
        Get a summary of permissions for this role.
        Useful for debugging and display.
        """
        return {
            'tier': self.get_tier(),
            'permissions': {
                'read': self.read,
                'write': self.write,
                'modify': self.modify,
                'delete': self.can_delete,
            },
            'tier_flags': {
                'is_admin': self.is_admin,
                'is_manager': self.is_manager,
                'is_individual': self.is_individual,
            }
        }
    
    def clean(self):
        """
        Django model validation.
        S'assure qu'exactement un tier est actif.
        Utilise les exceptions standard du projet.
        """
        super().clean()
        
        tier_count = sum([self.is_admin, self.is_manager, self.is_individual])
        
        if tier_count == 0:
            # Utiliser ValidationError standard de Django pour clean()
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(
                    detail="At least one tier must be active (is_admin, is_manager, or is_individual)."
                )
            )
        elif tier_count > 1:
            active_tiers = []
            if self.is_admin:
                active_tiers.append('is_admin')
            if self.is_manager:
                active_tiers.append('is_manager')
            if self.is_individual:
                active_tiers.append('is_individual')
            
            # Utiliser ValidationError standard de Django pour clean()
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(
                    detail=f"Only one tier can be active. Currently active: {', '.join(active_tiers)}"
                )
            )
    
    @property
    def client_id(self):
        """Helper property for client ID access."""
        return self.client_account_id

    # @property
    # def client_account(self):
    #     return self.client_id
