# end_users/models.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from core.models import BaseModel, CentralizedUserManager
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages


class ClientAccount(BaseModel):
    """
    Compte client - reste avec BaseModel car c'est le point d'entrée du multi-tenant
    """
    name = models.CharField(
        max_length=255, 
        unique=True, 
        help_text=_("Name of the company")
    )
    is_b2b = models.BooleanField(
        default=True, 
        help_text=_("True if the client is B2B; False for B2C.")
    )
    max_users = models.PositiveIntegerField(
        default=10, 
        help_text=_("Maximum number of users allowed for this client.")
    )

    class Meta:
        db_table = 'client_accounts'
        verbose_name = _('client_account')
        verbose_name_plural = _('client_accounts')
        ordering = ['name']

    def __str__(self):
        return self.name


class UserRole(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Rôles utilisateur avec client scoping
    """
    name = models.CharField(
        max_length=50, 
        help_text=_("Role name")
    )
    read = models.BooleanField(default=True)
    write = models.BooleanField(default=False)
    modify = models.BooleanField(default=False)
    delete = models.BooleanField(default=False)
    
    # Référence vers ClientAccount pour compatibilité
    client_account = models.ForeignKey(
        ClientAccount,
        on_delete=models.CASCADE,
        related_name='roles',
        help_text=_("Client this role belongs to."),
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['name'], 
        index_fields=['name']
    )):
        db_table = 'users_roles'
        verbose_name = _('user_role')
        verbose_name_plural = _('users_roles')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.client_account.name})"
    
    def save(self, *args, **kwargs):
        """Assurer la cohérence client_id avec client_account"""
        if self.client_account and not self.client_id:
            self.client_id = self.client_account.id
        super().save(*args, **kwargs)


class Organization(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Organisation avec client scoping
    """
    name = models.CharField(
        max_length=100, 
        help_text=_("Name of the organization (e.g., Sales, Management).")
    )
    client_account = models.ForeignKey(
        ClientAccount,
        on_delete=models.CASCADE,
        related_name='organizations',
        help_text=_("Client this organization belongs to."),
    )
    manager = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_organizations',
        help_text=_("Director or main manager of the organization."),
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['name'],
        index_fields=['name', 'manager']
    )):
        db_table = 'organizations'
        verbose_name = _('organization')
        verbose_name_plural = _('organizations')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.client_account.name})"
    
    def save(self, *args, **kwargs):
        """Assurer la cohérence client_id avec client_account"""
        if self.client_account and not self.client_id:
            self.client_id = self.client_account.id
        super().save(*args, **kwargs)


class Team(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Équipe avec client scoping
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

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['name', 'organization'],
        index_fields=['organization', 'manager']
    )):
        db_table = 'teams'
        verbose_name = _('team')
        verbose_name_plural = _('teams')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.organization.name} - {self.organization.client_account.name})"
    
    def save(self, *args, **kwargs):
        """Assurer la cohérence client_id avec organisation"""
        if self.organization and not self.client_id:
            self.client_id = self.organization.client_id
        super().save(*args, **kwargs)


class User(BaseModelApp, ClientScopeManager.ModelMixin, AbstractBaseUser, PermissionsMixin):
    """
    Utilisateur avec client scoping et patterns standards
    
    Hérite de :
    - BaseModelApp : pour client_id, timestamps, created_by, updated_by
    - ClientScopeManager.ModelMixin : pour les contraintes et indexes client-scoped
    - AbstractBaseUser, PermissionsMixin : pour l'authentification Django
    """
    
    # === CHAMPS AUTHENTICATION ===
    email = models.EmailField(
        unique=True,
        verbose_name=_('Email Address'),
        help_text=_('Unique email address for authentication')
    )
    password = models.CharField(max_length=255)
    
    # === INFORMATIONS PERSONNELLES ===
    first_name = models.CharField(
        max_length=50, 
        null=True, 
        blank=True,
        verbose_name=_('First Name')
    )
    last_name = models.CharField(
        max_length=50, 
        null=True, 
        blank=True,
        verbose_name=_('Last Name')
    )
    
    # === STATUT COMPTE ===
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active Status'),
        help_text=_('Designates whether this user should be treated as active')
    )
    is_staff = models.BooleanField(
        default=False,
        verbose_name=_('Staff Status'),
        help_text=_('Designates whether the user can log into admin site')
    )
    
    # === RELATIONS CLIENT ET HIÉRARCHIE ===
    client_account = models.ForeignKey(
        ClientAccount,
        on_delete=models.CASCADE,
        related_name='users',
        verbose_name=_('Client Account'),
        help_text=_("The client this user belongs to."),
    )
    
    role = models.ForeignKey(
        UserRole,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        verbose_name=_('User Role'),
        help_text=_("Role assigned to the user."),
    )
    
    role_name = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_('Role Name'),
        help_text=_("Cached name of the role for performance."),
    )
    
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
        verbose_name=_('Organization'),
        help_text=_("Organization the user belongs to."),
    )
    
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
        verbose_name=_('Team'),
        help_text=_("Team the user belongs to."),
    )

    # === PERMISSIONS DJANGO ===
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='end_users_user_set',
        blank=True,
        help_text=_('The groups this user belongs to.'),
        verbose_name=_('groups'),
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='end_users_user_set',
        blank=True,
        help_text=_('Specific permissions for this user.'),
        verbose_name=_('user permissions'),
    )

    # === MANAGER ET CONFIG DJANGO AUTH ===
    objects = CentralizedUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['email'],
        index_fields=['email', 'team', 'organization', 'role']
    )):
        db_table = 'users'
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-created_at']
        indexes = [
            # Index spécifiques pour les performances
            models.Index(fields=['client_id', 'is_active'], name='users_client_active_idx'),
            models.Index(fields=['client_id', 'team', 'is_active'], name='users_team_active_idx'),
            models.Index(fields=['client_id', 'organization', 'is_active'], name='users_org_active_idx'),
        ]

    def __str__(self):
        full_name = self.get_full_name()
        return f"{full_name} ({self.email})" if full_name else self.email

    def clean(self):
        """Validation métier du modèle"""
        super().clean()
        
        # Vérifier la cohérence hiérarchique
        if self.team and self.organization:
            if self.team.organization != self.organization:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail="Team must belong to the selected organization"
                    )
                )
        
        # Vérifier la cohérence client
        if self.role and self.client_account:
            if self.role.client_account != self.client_account:
                raise StandardizedValidationError(
                    CoreErrorMessages.CLIENT_MISMATCH
                )

    def save(self, *args, **kwargs):
        """
        Logique de sauvegarde avec cohérence automatique
        """
        # Assurer la cohérence client_id
        if self.client_account and not self.client_id:
            self.client_id = self.client_account.id
        
        # Auto-assignment de l'organisation depuis l'équipe
        if self.team and not self.organization:
            self.organization = self.team.organization
            
        # Cache du nom de rôle pour performance
        if self.role and self.role.name != self.role_name:
            self.role_name = self.role.name
        elif not self.role:
            self.role_name = None
            
        super().save(*args, **kwargs)

    # === MÉTHODES UTILITAIRES ===
    
    def get_full_name(self):
        """
        Retourne le nom complet de l'utilisateur
        """
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return ""
    
    def get_short_name(self):
        """
        Retourne le nom court (prénom ou email)
        """
        return self.first_name or self.email.split('@')[0]
    
    def get_display_name(self):
        """
        Retourne le nom d'affichage optimal
        """
        full_name = self.get_full_name()
        return full_name if full_name else self.email
    
    def is_manager(self):
        """
        Vérifie si l'utilisateur est manager d'équipe ou organisation
        """
        return (
            self.managed_teams.exists() or 
            self.managed_organizations.exists()
        )
    
    def get_managed_users(self):
        """
        Retourne tous les utilisateurs managés (équipe + organisation)
        """
        from django.db.models import Q
        
        managed_users = User.objects.filter(
            client_id=self.client_id
        ).filter(
            Q(team__in=self.managed_teams.all()) |
            Q(organization__in=self.managed_organizations.all())
        ).exclude(id=self.id).distinct()
        
        return managed_users
    
    def can_access_user_performance(self, target_user):
        """
        Vérifie si cet utilisateur peut accéder aux performances d'un autre
        Logic métier pour le UserPerformanceService
        """
        # Même client requis
        if self.client_id != target_user.client_id:
            return False
            
        # L'utilisateur peut toujours voir ses propres performances
        if self == target_user:
            return True
            
        # Manager peut voir ses équipes
        if target_user in self.get_managed_users():
            return True
            
        # Ajout de logiques supplémentaires selon les besoins
        # Ex: Admin peut voir tous les utilisateurs de son client
        if self.role and self.role.name == 'Admin':
            return True
            
        return False