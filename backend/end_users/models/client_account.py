from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import BaseModel
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
    
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY,
        default='EUR',
        verbose_name=_('Currency'),
        help_text=_(
            "The tenant's single currency (ISO-4217). EVERY amount this client "
            "owns — product prices, deal lines, cycle totals, KPI figures, quota "
            "targets — is expressed in it. There is no conversion and no "
            "per-deal currency: amounts are stored as plain numbers and this is "
            "the context that gives them a unit. Renamed from "
            "default_quota_currency: the currency belongs to the tenant, not to "
            "the quota that happened to read it first."
        )
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