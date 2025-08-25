# end_users/models/user_model.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from core.models import BaseModel, CentralizedUserManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.constants import CURRENCY


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
    Rôles utilisateur SANS client scoping pour simplifier
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

    class Meta:
        db_table = 'users_roles'
        verbose_name = _('user_role')
        verbose_name_plural = _('users_roles')
        unique_together = ('name', 'client_account')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.client_account.name})"


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