# end_users/models/user_model.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from core.models import BaseModel, CentralizedUserManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.constants import CURRENCY


## METHODES MIGRATION VERS USER PERMISSION SCOPING METHODS ##

import warnings
from functools import wraps

# # Import du nouveau système de permissions (à ajouter après les imports Django)
# try:
#     from permissions import check_permission, resolve_tier, has_permission
#     from permissions.config import is_enabled
#     PERMISSIONS_SYSTEM_AVAILABLE = True
# except ImportError:
#     PERMISSIONS_SYSTEM_AVAILABLE = False
#     print("[WARNING] New permissions system not available, using legacy methods")


def deprecated(message="This method is deprecated"):
    """Decorator to mark methods as deprecated."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            warnings.warn(
                f"{func.__name__} is deprecated and will be removed in a future version. {message}",
                DeprecationWarning,
                stacklevel=2
            )
            return func(*args, **kwargs)
        return wrapper
    return decorator    

############################################


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

    # === CONFIGURATION ANNÉE FISCALE ===
    
    fiscal_year_start_month = models.IntegerField(
        default=1,
        choices=[(i, f"{i:02d}") for i in range(1, 13)],
        verbose_name=_('Fiscal Year Start Month'),
        help_text=_("Month when fiscal year starts (1=January, 2=February, etc.)")
    )
    
    fiscal_year_start_day = models.IntegerField(
        default=1,
        choices=[(i, str(i)) for i in range(1, 32)],
        verbose_name=_('Fiscal Year Start Day'),
        help_text=_("Day when fiscal year starts")
    )
    
    # === CONFIGURATION BUSINESS ===
    
    timezone = models.CharField(
        max_length=50,
        default='Europe/Paris',
        verbose_name=_('Timezone'),
        help_text=_("Client's business timezone (e.g., 'Europe/Paris', 'America/New_York')")
    )
    
    default_quota_currency = models.CharField(
        max_length=3,
        choices=CURRENCY,
        default='EUR',
        verbose_name=_('Default Quota Currency'),
        help_text=_("Default currency for quotas (EUR, USD, GBP, etc.)")
    )

    class Meta:
        db_table = 'client_accounts'
        verbose_name = _('client_account')
        verbose_name_plural = _('client_accounts')
        ordering = ['name']

    def __str__(self):
        return self.name
    
    ADMIN_ROLE_NAME = 'Admin'

    def get_or_create_admin_role(self):
        """
        Get or create the Admin role for this client account.
        
        Le rôle Admin devrait normalement être créé par le signal lors de la création
        du ClientAccount. Cette méthode garantit qu'il existe dans tous les cas.
        
        Returns:
            UserRole: The Admin role instance for this client
        """
        from end_users.models import UserRole
        
        # Le signal devrait avoir créé le rôle, mais on utilise get_or_create par sécurité
        admin_role, created = UserRole.objects.get_or_create(
            client_account=self,
            name='Admin',  # Nom fixe du rôle Admin
            defaults={
                'read': True,
                'write': True,
                'modify': True,
                'delete': True
            }
        )
        
        return admin_role

    def get_active_users_queryset(self):
        """Return queryset of active users for this client."""
        return self.users.filter(is_active=True)

    def count_active_users(self):
        """Number of active users for seats calculation."""
        return self.get_active_users_queryset().count()

    def seats_usage(self):
        """Simple seat usage snapshot."""
        active = self.count_active_users()
        maxu = self.max_users or 0
        return {
            'active': active,
            'max': maxu,
            'available': max(0, maxu - active)
        }

    def has_available_seat(self):
        """True if there is at least one available active seat."""
        maxu = self.max_users or 0
        # If max_users is 0, consider no seats available
        return self.count_active_users() < maxu

    def get_admins_queryset(self, active_only=True):
        """Return queryset of admin users (optionally active-only)."""
        qs = self.users.filter(role__name=self.ADMIN_ROLE_NAME)
        return qs.filter(is_active=True) if active_only else qs

    def count_admins(self, active_only=True):
        """Count admin users (optionally active-only)."""
        return self.get_admins_queryset(active_only=active_only).count()


    def ensure_admin_invariants(self):
        """
        Safety net: ensure there is at least one Admin user for this client.
        - If there is no admin (active or inactive), promote a user to Admin:
        prefer the most-recent active user; otherwise the most-recent user.
        - Does nothing if there are no users at all.
        Returns the promoted user or None.
        """
        # No users -> nothing to enforce
        if not self.users.exists():
            return None

        # If at least one superuser exists, nothing to do
        if self.users.filter(is_superuser=True).exists():
            return None

        # Need to promote someone to superuser
        # Prefer an active user; else any recent user
        candidate = self.get_active_users_queryset().order_by('-created_at').first()
        if candidate is None:
            candidate = self.users.order_by('-created_at').first()

        if candidate:
            # Make them superuser (keep their role as-is)
            candidate.is_superuser = True
            candidate.is_staff = True  # Also give staff access for Django admin
            candidate.save(update_fields=['is_superuser', 'is_staff', 'updated_at'])
            
            # Log this important action
            from django.utils import timezone
            print(f"[SECURITY] User {candidate.email} promoted to superuser for client {self.name} at {timezone.now()}")
            
            return candidate

        return None
    
    def get_superusers_queryset(self, active_only=True):
        """Return queryset of superuser users (optionally active-only)."""
        qs = self.users.filter(is_superuser=True)
        return qs.filter(is_active=True) if active_only else qs

    def count_superusers(self, active_only=True):
        """Count superuser users (optionally active-only)."""
        return self.get_superusers_queryset(active_only=active_only).count()
    
    def get_fiscal_year_dates(self, year=None):
        """
        Calcule les dates de début et fin d'année fiscale pour une année donnée.
        
        Args:
            year: Année fiscale (défaut: année courante)
            
        Returns:
            tuple: (fiscal_start_date, fiscal_end_date)
        """
        from datetime import date, timedelta
        import calendar
        
        if year is None:
            year = date.today().year
        
        # Date de début année fiscale
        fiscal_start = date(year, self.fiscal_year_start_month, self.fiscal_year_start_day)
        
        # Date de fin année fiscale (un an moins un jour)
        try:
            fiscal_end = date(year + 1, self.fiscal_year_start_month, self.fiscal_year_start_day) - timedelta(days=1)
        except ValueError:
            # Gérer le cas 29 février dans une année non bissextile
            fiscal_end = date(year + 1, self.fiscal_year_start_month, 28) - timedelta(days=1)
        
        return fiscal_start, fiscal_end
    
    def get_current_fiscal_year(self):
        """
        Détermine l'année fiscale actuelle basée sur la date d'aujourd'hui.
        
        Returns:
            int: Année fiscale actuelle
        """
        from datetime import date
        
        today = date.today()
        fiscal_start, fiscal_end = self.get_fiscal_year_dates(today.year)
        
        if today >= fiscal_start:
            return today.year
        else:
            # Si on est avant le début de l'année fiscale, on est dans l'année fiscale précédente
            return today.year - 1
    
    def get_fiscal_quarters(self, fiscal_year=None):
        """
        Calcule les 4 trimestres de l'année fiscale.
        
        Args:
            fiscal_year: Année fiscale (défaut: année courante)
            
        Returns:
            list: Liste de tuples (start_date, end_date) pour chaque trimestre
        """
        from datetime import date
        from dateutil.relativedelta import relativedelta
        
        if fiscal_year is None:
            fiscal_year = self.get_current_fiscal_year()
        
        fiscal_start, fiscal_end = self.get_fiscal_year_dates(fiscal_year)
        quarters = []
        
        for quarter in range(4):
            q_start = fiscal_start + relativedelta(months=quarter * 3)
            q_end = fiscal_start + relativedelta(months=(quarter + 1) * 3) - relativedelta(days=1)
            
            # S'assurer qu'on ne dépasse pas la fin de l'année fiscale
            if q_end > fiscal_end:
                q_end = fiscal_end
            
            quarters.append((q_start, q_end))
        
        return quarters
    
    def get_fiscal_months(self, fiscal_year=None):
        """
        Calcule les 12 mois de l'année fiscale.
        
        Args:
            fiscal_year: Année fiscale (défaut: année courante)
            
        Returns:
            list: Liste de tuples (start_date, end_date) pour chaque mois
        """
        from datetime import date
        from dateutil.relativedelta import relativedelta
        
        if fiscal_year is None:
            fiscal_year = self.get_current_fiscal_year()
        
        fiscal_start, fiscal_end = self.get_fiscal_year_dates(fiscal_year)
        months = []
        
        for month in range(12):
            m_start = fiscal_start + relativedelta(months=month)
            m_end = fiscal_start + relativedelta(months=month + 1) - relativedelta(days=1)
            
            # S'assurer qu'on ne dépasse pas la fin de l'année fiscale
            if m_end > fiscal_end:
                m_end = fiscal_end
            
            months.append((m_start, m_end))
        
        return months


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
    delete = models.BooleanField(default=False)

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
                'delete': self.delete,
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

class Organization(BaseModel):
    """
    Organisation SANS client scoping pour simplifier
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

    class Meta:
        db_table = 'organizations'
        verbose_name = _('organization')
        verbose_name_plural = _('organizations')
        unique_together = ('name', 'client_account')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.client_account.name})"
    
    @property
    def client_id(self):
        return self.client_account_id


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
        if self.role.is_admin:
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
        Vérifie si cet utilisateur peut accéder aux performances d'un autre
        Logic métier pour le UserPerformanceService
        """
        # Même client requis
        if self.client_account != target_user.client_account:
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
    
    @deprecated("Use check_permission(user, module, 'read') or resolve_tier(user) == 'admin' instead")
    def has_admin_rights(self):
        """
        Check if user has administrative rights in their tenant.
        Returns True if user is either:
        - A superuser (is_superuser=True)
        - Has Admin role
        """
        ###### Migration methods #########
        try:
            # Import localement pour éviter l'importation circulaire
            from permissions import resolve_tier
            from permissions.config import is_enabled
            
            if is_enabled():
                tier = resolve_tier(self)
                return tier == 'admin'
        except ImportError:
            # New system not available
            pass
        except Exception as e:
            # Fallback to legacy if new system fails
            print(f"[WARNING] Permission system check failed: {e}, falling back to legacy")
            

        ###############################

        # Superuser a toujours les droits admin
        if self.is_superuser:
            return True
        
        # Vérifier le rôle Admin
        if self.role and self.role.name == 'Admin':
            return True
        
        # Vérifier aussi via role_name (cache)
        if self.role_name == 'Admin':
            return True
        
        return False
    
    def can_grant_superuser(self):
        """
        Check if this user can grant or revoke superuser status to others.
        Only superusers and Admin role users can do this.
        """
        return self.has_admin_rights()
    
    @deprecated("Use check_permission(user, 'users', 'update', target_user) instead")
    def can_modify_user(self, target_user):
        """
        Check if this user can modify another user's data.
        
        Args:
            target_user: The user to be modified
            
        Returns:
            bool: True if modification is allowed
        """


        ###### Migration methods #########
        try:
            # Import localement pour éviter l'importation circulaire
            from permissions import check_permission
            from permissions.config import is_enabled
            
            if is_enabled():
                # For users module, check update permission
                scope = check_permission(self, 'users', 'update')
                
                # Apply scope-based logic
                if scope == 'none':
                    return False
                elif scope == 'client':
                    # Can modify anyone in same tenant
                    return self.client_account_id == target_user.client_account_id
                elif scope == 'team':
                    # Can modify self or team members
                    if self == target_user:
                        return True
                    return target_user in self.get_managed_users()
                elif scope == 'mine':
                    # Can only modify self
                    return self == target_user
                else:
                    return False
                    
        except ImportError:
            # New system not available
            pass
        except Exception as e:
            # Fallback to legacy if new system fails
            print(f"[WARNING] Permission check failed: {e}, falling back to legacy")
    

        ###############################


        # Peut modifier ses propres données
        if self == target_user:
            return True
        
        # Superuser peut modifier tout le monde dans son tenant
        if self.is_superuser:
            # Vérifier qu'ils sont dans le même tenant
            return self.client_account_id == target_user.client_account_id
        
        # Admin peut modifier tout le monde dans son tenant
        if self.role and self.role.name == 'Admin':
            return self.client_account_id == target_user.client_account_id
        
        # Manager peut modifier les membres de son équipe
        if self.is_manager():
            return target_user in self.get_managed_users()
        
        return False
    
    @deprecated("Use check_permission(user, 'users', 'delete', target_user) instead")
    def can_delete_user(self, target_user):
        """
        Check if this user can delete another user.
        
        Args:
            target_user: The user to be deleted
            
        Returns:
            bool: True if deletion is allowed
        """
        
        # Personne ne peut se supprimer soi-même
        if self == target_user:
            return False
        

         ###### Migration methods #########
        try:
            # Import localement pour éviter l'importation circulaire
            from permissions import check_permission
            from permissions.config import is_enabled
            
            if is_enabled():
                # For users module, check delete permission
                scope = check_permission(self, 'users', 'delete')
                
                # Apply scope-based logic
                if scope == 'none':
                    return False
                elif scope == 'client':
                    # Can delete anyone in same tenant (except self)
                    return self.client_account_id == target_user.client_account_id
                elif scope == 'team':
                    # Can delete team members (except self)
                    return target_user in self.get_managed_users()
                elif scope == 'mine':
                    # Cannot delete anyone (mine = self, but we can't delete ourselves)
                    return False
                else:
                    return False
                    
        except ImportError:
            # New system not available
            pass
        except Exception as e:
            # Fallback to legacy if new system fails
            print(f"[WARNING] Permission check failed: {e}, falling back to legacy")
        
        
        ###############################

        
        # Superuser peut supprimer tout le monde (sauf lui-même) dans son tenant
        if self.is_superuser:
            return self.client_account_id == target_user.client_account_id
        
        # Admin peut supprimer tout le monde (sauf lui-même) dans son tenant
        if self.role and self.role.name == 'Admin':
            return self.client_account_id == target_user.client_account_id
        
        # Manager peut supprimer les membres de son équipe
        if self.is_manager():
            return target_user in self.get_managed_users()
        
        return False
    
    def can_view_all_users(self):
        """
        Check if this user can view all users in their tenant.
        """
        # Superusers et Admins peuvent voir tous les utilisateurs
        return self.has_admin_rights()
    
    def can_manage_roles(self):
        """
        Check if this user can manage roles and permissions.
        """
        # Seuls les superusers et admins peuvent gérer les rôles
        return self.has_admin_rights()
    
    def can_manage_teams(self):
        """
        Check if this user can create/modify/delete teams.
        """
        # Superusers et Admins peuvent gérer toutes les équipes
        if self.has_admin_rights():
            return True
        
        # Les managers peuvent gérer leurs propres équipes
        return self.managed_teams.exists()
    
    def can_manage_organizations(self):
        """
        Check if this user can create/modify/delete organizations.
        """
        # Superusers et Admins peuvent gérer toutes les organisations
        if self.has_admin_rights():
            return True
        
        # Les directeurs peuvent gérer leurs propres organisations
        return self.managed_organizations.exists()
    
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