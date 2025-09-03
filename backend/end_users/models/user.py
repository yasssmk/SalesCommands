from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from core.models import BaseModel, CentralizedUserManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from .client_account import ClientAccount
from .team import Team
from .organization import Organization
from .role import UserRole


class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    """
    Utilisateur SANS client scoping complexe pour simplifier
    
    Hérite de :
    - BaseModel : pour id, timestamps de base
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

    class Meta:
        db_table = 'users'
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-created_at']
        indexes = [
            # Index simples pour les performances
            models.Index(fields=['client_account', 'is_active'], name='users_client_active_idx'),
            models.Index(fields=['client_account', 'team', 'is_active'], name='users_team_active_idx'),
            models.Index(fields=['client_account', 'organization', 'is_active'], name='users_org_active_idx'),
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

    @property
    def client_id(self):
        return self.client_account_id

    @client_id.setter
    def client_id(self, value):
        self.client_account_id = value
    
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
        from permissions import resolve_tier
        user_tier = resolve_tier(self)
        
        # Admin peut voir tous les utilisateurs de son client
        if user_tier == 'manager':
            return True
        
        else:
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
            client_account=self.client_account
        ).filter(
            Q(team__in=self.managed_teams.all()) |
            Q(organization__in=self.managed_organizations.all())
        ).exclude(id=self.id).distinct()
        
        return managed_users
    
    def can_access_user_performance(self, target_user):
        """
        Vérifie si cet utilisateur peut accéder aux performances d'un autre.
        Utilise resolve_tier() au lieu de vérifier le nom du rôle.
        Logic métier pour le UserPerformanceService.
        """
        # Même client requis (toujours vérifier en premier)
        if self.client_account != target_user.client_account:
            return False
            
        # L'utilisateur peut toujours voir ses propres performances
        if self == target_user:
            return True
        
        # Utiliser resolve_tier pour déterminer les permissions basées sur le tier
        from permissions import resolve_tier
        user_tier = resolve_tier(self)
        
        # Admin peut voir tous les utilisateurs de son client
        if user_tier == 'admin':
            return True
            
        # Manager peut voir son équipe et les utilisateurs qu'il manage
        if user_tier == 'manager':
            # Check si target_user est dans les users managés
            if target_user in self.get_managed_users():
                return True
            # Check si target_user est dans la même équipe
            if self.team and target_user.team and self.team == target_user.team:
                return True
                
        # Individual ne peut voir que lui-même (déjà traité plus haut)
        return False
    
    
    def can_grant_superuser(self):
        """
        Check if this user can grant or revoke superuser status to others.
        Only superusers and Admin role users can do this.
        """
        # return self.has_admin_rights()
        from permissions import resolve_tier
        return resolve_tier(self) == 'admin'
    
    
    def can_manage_roles(self):
        """
        Check if this user can manage roles and permissions.
        """
        # Seuls les superusers et admins peuvent gérer les rôles
        # return self.has_admin_rights()
        from permissions import resolve_tier
        return resolve_tier(self) == 'admin'
    
    def can_manage_teams(self):
        """
        Check if this user can create/modify/delete teams.
        Utilise resolve_tier() au lieu de has_admin_rights().
        """
        from permissions import resolve_tier
        user_tier = resolve_tier(self)
        
        # Admins peuvent gérer toutes les équipes
        if user_tier == 'admin':
            return True
        
        # Les managers peuvent gérer leurs propres équipes
        if user_tier == 'manager':
            return self.managed_teams.exists()
        
        # Individual ne peut pas gérer d'équipes
        return False
    
    def can_manage_organizations(self):
        """
        Check if this user can create/modify/delete organizations.
        Utilise resolve_tier() au lieu de has_admin_rights().
        """
        from permissions import resolve_tier
        user_tier = resolve_tier(self)
        
        # Admins peuvent gérer toutes les organisations
        if user_tier == 'admin':
            return True
        
        # Les managers peuvent gérer leurs propres organisations
        if user_tier == 'manager':
            return self.managed_organizations.exists()
        
        # Individual ne peut pas gérer d'organisations  
        return False
    
    def get_permission_level(self):
        """
        Get a string representation of the user's permission level.
        Useful for UI display.
        
        Returns:
            str: Permission level description
        """
        if self.is_superuser:
            return "Superuser (Full Admin)"
        elif self.role and self.role.name == 'Admin':
            return "Administrator"
        elif self.is_manager():
            if self.managed_organizations.exists():
                return "Organization Manager"
            elif self.managed_teams.exists():
                return "Team Manager"
        elif self.role:
            return self.role.name
        else:
            return "User"
    
    def get_permission_summary(self):
        """
        Get a detailed summary of user's permissions.
        Useful for security audits and UI display.
        
        Returns:
            dict: Detailed permission summary
        """
        return {
            'is_superuser': self.is_superuser,
            'is_staff': self.is_staff,
            'has_admin_rights': self.has_admin_rights(),
            'permission_level': self.get_permission_level(),
            'role': {
                'name': self.role.name if self.role else None,
                'read': self.role.read if self.role else False,
                'write': self.role.write if self.role else False,
                'modify': self.role.modify if self.role else False,
                'delete': self.role.delete if self.role else False,
            } if self.role else None,
            'capabilities': {
                'can_grant_superuser': self.can_grant_superuser(),
                'can_manage_roles': self.can_manage_roles(),
                'can_view_all_users': self.can_view_all_users(),
                'can_manage_teams': self.can_manage_teams(),
                'can_manage_organizations': self.can_manage_organizations(),
            },
            'management': {
                'is_manager': self.is_manager(),
                'managed_teams_count': self.managed_teams.count(),
                'managed_organizations_count': self.managed_organizations.count(),
                'managed_users_count': self.get_managed_users().count(),
            }
        }
    
    def ensure_superuser_consistency(self):
        """
        Ensure consistency of superuser-related fields.
        Called after save to maintain data integrity.
        """
        updated = False
        
        # Si superuser, doit avoir is_staff
        if self.is_superuser and not self.is_staff:
            self.is_staff = True
            updated = True
        
        if updated:
            self.save(update_fields=['is_staff', 'updated_at'])
    
    def is_last_superuser(self):
        """
        Check if this user is the last superuser in their tenant.
        """
        if not self.is_superuser:
            return False
        
        other_superusers = User.objects.filter(
            client_account_id=self.client_account_id,
            is_superuser=True
        ).exclude(id=self.id).count()
        
        return other_superusers == 0
    
    def is_last_active_admin(self):
        """
        Check if this user is the last active admin (superuser OR Admin role).
        """
        if not self.is_active:
            return False
        
        if not self.has_admin_rights():
            return False
        
        from django.db.models import Q
        other_active_admins = User.objects.filter(
            client_account_id=self.client_account_id,
            is_active=True
        ).filter(
            Q(is_superuser=True) | Q(role__name='Admin')
        ).exclude(id=self.id).count()
        
        return other_active_admins == 0