# end_users/models/sales_quota_model.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages


class SalesQuota(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Quota de vente assigné à un utilisateur pour une période donnée.
    
    Définit les objectifs de performance (closed won, pipeline, meetings, leads)
    qu'un commercial doit atteindre sur une période spécifique.
    
    Intégré avec UserPerformanceService pour le tracking temps réel.
    Un utilisateur ne peut avoir qu'un seul quota actif par période.
    """
    
    class TargetType(models.TextChoices):
        """Types d'objectifs de quota supportés"""
        CLOSED_WON = 'closed_won', _('Closed Won Revenue')
        PIPELINE = 'pipeline', _('Pipeline Value')
        MEETINGS = 'meetings', _('Number of Meetings')
        LEADS_ACCEPTED = 'leads_accepted', _('Leads Accepted')
        OPPORTUNITIES = 'opportunities', _('Number of Opportunities')
        CONVERSION_RATE = 'conversion_rate', _('Conversion Rate %')
    
    class QuotaStatus(models.TextChoices):
        """Statuts de quota"""
        DRAFT = 'draft', _('Draft')
        ACTIVE = 'active', _('Active')
        COMPLETED = 'completed', _('Completed')
        CANCELLED = 'cancelled', _('Cancelled')
        EXPIRED = 'expired', _('Expired')
    
    class RecurrenceType(models.TextChoices):
        """Types de récurrence pour les quotas"""
        ANNUAL = 'annual', _('Annual (Yearly)')
        QUARTERLY = 'quarterly', _('Quarterly (Every 3 months)')
        MONTHLY = 'monthly', _('Monthly')
    
    # === RELATIONS PRINCIPALES ===
    
    user = models.ForeignKey(
        'end_users.User',
        on_delete=models.CASCADE,
        related_name='sales_quotas',
        verbose_name=_('User'),
        help_text=_('User this quota is assigned to')
    )
    
    # === DÉFINITION DU QUOTA ===
    
    name = models.CharField(
        max_length=100,
        verbose_name=_('Quota Name'),
        help_text=_('Descriptive name for this quota (e.g., "Q1 2024 Revenue Target")')
    )
    
    target_type = models.CharField(
        max_length=20,
        choices=TargetType.choices,
        verbose_name=_('Target Type'),
        help_text=_('Type of metric this quota tracks')
    )
    
    target_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('Target Value'),
        help_text=_('Target value to achieve (e.g., revenue amount, number of meetings)')
    )
    
    unit = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_('Unit'),
        help_text=_('Unit of measurement (e.g., "€", "meetings", "%")')
    )
    
    # === PÉRIODE ET TIMING - Configuration automatique ===
    
    recurrence_type = models.CharField(
        max_length=20,
        choices=RecurrenceType.choices,
        verbose_name=_('Recurrence Type'),
        help_text=_('How often this quota repeats (Annual/Quarterly/Monthly)')
    )
    
    fiscal_year = models.IntegerField(
        verbose_name=_('Fiscal Year'),
        help_text=_('Fiscal year this quota belongs to (e.g., 2024)')
    )
    
    period_number = models.IntegerField(
        default=1,
        verbose_name=_('Period Number'),
        help_text=_('Period within fiscal year (Q1=1, Q2=2 for quarterly; Month=1-12 for monthly)')
    )
    
    period_start = models.DateField(
        verbose_name=_('Period Start'),
        help_text=_('Start date of the quota period (auto-calculated from recurrence)')
    )
    
    period_end = models.DateField(
        verbose_name=_('Period End'),
        help_text=_('End date of the quota period (auto-calculated from recurrence)')
    )
    
    # === STATUT ET GESTION ===
    
    status = models.CharField(
        max_length=20,
        choices=QuotaStatus.choices,
        default=QuotaStatus.DRAFT,
        verbose_name=_('Status'),
        help_text=_('Current status of this quota')
    )
    
    is_team_quota = models.BooleanField(
        default=False,
        verbose_name=_('Is Team Quota'),
        help_text=_('Whether this is a team-wide quota (vs individual)')
    )
    
    # === MÉTADONNÉES ===
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description'),
        help_text=_('Optional description or notes about this quota')
    )
    
    assigned_by = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_quotas',
        verbose_name=_('Assigned By'),
        help_text=_('Manager who assigned this quota')
    )
    
    activation_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Activation Date'),
        help_text=_('When this quota was activated')
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['user', 'recurrence_type', 'fiscal_year', 'period_number'],
        index_fields=['user', 'fiscal_year', 'recurrence_type', 'status', 'target_type']
    )):
        db_table = 'sales_quotas'
        verbose_name = _('Sales Quota')
        verbose_name_plural = _('Sales Quotas')
        ordering = ['-fiscal_year', '-period_number', 'user__first_name', 'user__last_name']
        constraints = [
            # Un seul quota par utilisateur/type/année fiscale/période
            models.UniqueConstraint(
                fields=['user', 'recurrence_type', 'fiscal_year', 'period_number', 'client_id'],
                condition=models.Q(status__in=['draft', 'active']),
                name='unique_quota_per_user_period'
            ),
            # Validation période cohérente
            models.CheckConstraint(
                check=models.Q(period_end__gt=models.F('period_start')),
                name='valid_period_dates'
            ),
            # Target value positive
            models.CheckConstraint(
                check=models.Q(target_value__gt=0),
                name='positive_target_value'
            ),
            # Validation period_number selon recurrence_type
            models.CheckConstraint(
                check=(
                    models.Q(recurrence_type='annual', period_number=1) |
                    models.Q(recurrence_type='quarterly', period_number__in=[1, 2, 3, 4]) |
                    models.Q(recurrence_type='monthly', period_number__in=list(range(1, 13)))
                ),
                name='valid_period_number'
            )
        ]

    def __str__(self):
        period_display = self._get_period_display()
        return f"{self.user.get_full_name()}: {self.get_target_type_display()} ({period_display})"
    
    def _get_period_display(self):
        """Génère un affichage lisible de la période"""
        if self.recurrence_type == self.RecurrenceType.ANNUAL:
            return f"FY{self.fiscal_year}"
        elif self.recurrence_type == self.RecurrenceType.QUARTERLY:
            return f"Q{self.period_number} FY{self.fiscal_year}"
        elif self.recurrence_type == self.RecurrenceType.MONTHLY:
            month_names = [
                'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
            ]
            # Calculer le mois selon l'année fiscale du client
            fiscal_start_month = self.user.client_account.fiscal_year_start_month
            actual_month = ((fiscal_start_month - 1 + self.period_number - 1) % 12) + 1
            return f"{month_names[actual_month - 1]} {self.fiscal_year}"
        
        return f"{self.period_start.strftime('%b %Y')} - {self.period_end.strftime('%b %Y')}"

    # === VALIDATION MÉTIER ===
    
    def clean(self):
        """Validation métier du modèle"""
        super().clean()
        
        # Valider period_number selon recurrence_type
        if self.recurrence_type and self.period_number:
            if self.recurrence_type == self.RecurrenceType.ANNUAL and self.period_number != 1:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail="Annual quotas must have period_number = 1"
                    )
                )
            elif self.recurrence_type == self.RecurrenceType.QUARTERLY and self.period_number not in [1, 2, 3, 4]:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail="Quarterly quotas must have period_number between 1 and 4"
                    )
                )
            elif self.recurrence_type == self.RecurrenceType.MONTHLY and self.period_number not in range(1, 13):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail="Monthly quotas must have period_number between 1 and 12"
                    )
                )
        
        # Valider cohérence client entre user et quota
        if self.user and self.client_id:
            if str(self.user.client_id) != str(self.client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        
        # Calculer automatiquement les dates de période
        if self.user and self.recurrence_type and self.fiscal_year and self.period_number:
            self._calculate_period_dates()
        
        # Valider qu'il n'y a qu'un quota par utilisateur/récurrence/période
        if self.status in [self.QuotaStatus.DRAFT, self.QuotaStatus.ACTIVE]:
            existing = SalesQuota.objects.filter(
                user=self.user,
                recurrence_type=self.recurrence_type,
                fiscal_year=self.fiscal_year,
                period_number=self.period_number,
                client_id=self.client_id,
                status__in=[self.QuotaStatus.DRAFT, self.QuotaStatus.ACTIVE]
            )
            
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            
            if existing.exists():
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail=f"User already has a quota for {self._get_period_display()}"
                    )
                )
    
    def _calculate_period_dates(self):
        """
        Calcule automatiquement period_start et period_end basés sur la récurrence
        et l'année fiscale du client.
        """
        if not (self.user and self.recurrence_type and self.fiscal_year and self.period_number):
            return
        
        client_account = self.user.client_account
        
        try:
            if self.recurrence_type == self.RecurrenceType.ANNUAL:
                # Année fiscale complète
                self.period_start, self.period_end = client_account.get_fiscal_year_dates(self.fiscal_year)
                
            elif self.recurrence_type == self.RecurrenceType.QUARTERLY:
                # Trimestre spécifique
                quarters = client_account.get_fiscal_quarters(self.fiscal_year)
                if 1 <= self.period_number <= len(quarters):
                    self.period_start, self.period_end = quarters[self.period_number - 1]
                else:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_DATA.format(
                            detail=f"Invalid quarter number: {self.period_number}"
                        )
                    )
                    
            elif self.recurrence_type == self.RecurrenceType.MONTHLY:
                # Mois spécifique
                months = client_account.get_fiscal_months(self.fiscal_year)
                if 1 <= self.period_number <= len(months):
                    self.period_start, self.period_end = months[self.period_number - 1]
                else:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_DATA.format(
                            detail=f"Invalid month number: {self.period_number}"
                        )
                    )
        
        except Exception as e:
            if not isinstance(e, StandardizedValidationError):
                raise StandardizedValidationError(
                    CoreErrorMessages.UNEXPECTED_ERROR.format(
                        detail=f"Failed to calculate period dates: {str(e)}"
                    )
                )

    def save(self, *args, **kwargs):
        """Logique de sauvegarde avec cohérence automatique"""
        # Assurer cohérence client_id avec user
        if self.user and not self.client_id:
            self.client_id = self.user.client_id
        
        # Auto-générer nom si absent
        if not self.name and self.user and self.period_start:
            period_name = f"Q{((self.period_start.month - 1) // 3) + 1} {self.period_start.year}"
            self.name = f"{self.get_target_type_display()} - {period_name}"
        
        # Auto-set unit based on target_type
        if not self.unit and self.target_type:
            unit_mapping = {
                self.TargetType.CLOSED_WON: '€',
                self.TargetType.PIPELINE: '€',
                self.TargetType.MEETINGS: 'meetings',
                self.TargetType.LEADS_ACCEPTED: 'leads',
                self.TargetType.OPPORTUNITIES: 'opportunities',
                self.TargetType.CONVERSION_RATE: '%'
            }
            self.unit = unit_mapping.get(self.target_type, '')
        
        # Set activation_date si passage à ACTIVE
        if self.status == self.QuotaStatus.ACTIVE and not self.activation_date:
            self.activation_date = timezone.now()
        
        super().save(*args, **kwargs)

    # === MÉTHODES DE PERFORMANCE - Intégration UserPerformanceService ===
    
    def get_current_value(self):
        """
        Récupère la valeur actuelle pour ce quota via UserPerformanceService.
        
        Returns:
            float: Valeur actuelle selon le type de quota
        """
        try:
            from end_users.services import UserPerformanceService
            
            # Récupérer les performances sur la période du quota
            performance_data = UserPerformanceService.get_user_complete_performance(
                user_id=self.user.id,
                period_start=self.period_start,
                period_end=min(self.period_end, date.today()),  # Ne pas dépasser aujourd'hui
                client_id=self.client_id
            )
            
            # Extraire la métrique selon le type de quota
            if self.target_type == self.TargetType.CLOSED_WON:
                return performance_data['opportunities']['won_value']
            elif self.target_type == self.TargetType.PIPELINE:
                return performance_data['opportunities']['pipeline_value']
            elif self.target_type == self.TargetType.MEETINGS:
                return performance_data['meetings']['completed_count']
            elif self.target_type == self.TargetType.LEADS_ACCEPTED:
                return performance_data['leads']['qualified_count']
            elif self.target_type == self.TargetType.OPPORTUNITIES:
                return performance_data['opportunities']['created_count']
            elif self.target_type == self.TargetType.CONVERSION_RATE:
                return performance_data['leads']['conversion_rate_percentage']
            
            return 0
            
        except Exception:
            # Fallback gracieux en cas d'erreur
            return 0
    
    def get_progress_percentage(self):
        """
        Calcule le pourcentage de progression du quota.
        
        Returns:
            float: Pourcentage de progression (0-100)
        """
        try:
            current = self.get_current_value()
            target = float(self.target_value)
            
            if target == 0:
                return 0.0
            
            progress = (current / target) * 100
            return min(100.0, progress)  # Plafonner à 100%
            
        except Exception:
            return 0.0
    
    def get_progress_status(self):
        """
        Détermine le statut de progression du quota.
        
        Returns:
            str: 'EXCEEDED', 'ACHIEVED', 'ON_TRACK', 'AT_RISK', 'BEHIND'
        """
        progress = self.get_progress_percentage()
        
        if progress >= 100:
            return 'ACHIEVED'
        elif progress >= 120:  # Dépassement
            return 'EXCEEDED'
        elif progress >= 75:
            return 'ON_TRACK'
        elif progress >= 50:
            return 'AT_RISK'
        else:
            return 'BEHIND'
    
    def get_remaining_value(self):
        """
        Calcule la valeur restante à atteindre.
        
        Returns:
            float: Valeur restante (0 si quota déjà atteint)
        """
        try:
            current = self.get_current_value()
            target = float(self.target_value)
            remaining = target - current
            return max(0.0, remaining)
        except Exception:
            return float(self.target_value)
    
    def get_days_remaining(self):
        """
        Calcule le nombre de jours restants dans la période.
        
        Returns:
            int: Jours restants (0 si période expirée)
        """
        today = date.today()
        if today > self.period_end:
            return 0
        elif today < self.period_start:
            return (self.period_end - self.period_start).days
        else:
            return (self.period_end - today).days
    
    def get_daily_target_remaining(self):
        """
        Calcule la cible quotidienne pour atteindre l'objectif.
        
        Returns:
            float: Valeur à atteindre par jour restant
        """
        days_remaining = self.get_days_remaining()
        if days_remaining <= 0:
            return 0.0
        
        remaining_value = self.get_remaining_value()
        return remaining_value / days_remaining
    
    def is_achieved(self):
        """
        Vérifie si le quota est atteint.
        
        Returns:
            bool: True si quota atteint (>= 100%)
        """
        return self.get_progress_percentage() >= 100
    
    def is_expired(self):
        """
        Vérifie si la période du quota est expirée.
        
        Returns:
            bool: True si période expirée
        """
        return date.today() > self.period_end

    # === MÉTHODES UTILITAIRES ===
    
    def get_quota_summary(self):
        """
        Retourne un résumé complet du quota.
        
        Returns:
            dict: Résumé avec toutes les métriques
        """
        return {
            'quota_id': self.id,
            'quota_name': self.name,
            'user': {
                'id': self.user.id,
                'name': self.user.get_full_name(),
                'email': self.user.email
            },
            'target': {
                'type': self.target_type,
                'type_display': self.get_target_type_display(),
                'value': float(self.target_value),
                'unit': self.unit or ''
            },
            'recurrence': {
                'type': self.recurrence_type,
                'type_display': self.get_recurrence_type_display(),
                'fiscal_year': self.fiscal_year,
                'period_number': self.period_number,
                'period_display': self._get_period_display()
            },
            'period': {
                'start': self.period_start.isoformat(),
                'end': self.period_end.isoformat(),
                'days_total': (self.period_end - self.period_start).days + 1,
                'days_remaining': self.get_days_remaining()
            },
            'performance': {
                'current_value': self.get_current_value(),
                'progress_percentage': round(self.get_progress_percentage(), 1),
                'remaining_value': self.get_remaining_value(),
                'status': self.get_progress_status(),
                'is_achieved': self.is_achieved(),
                'daily_target_remaining': round(self.get_daily_target_remaining(), 2)
            },
            'meta': {
                'status': self.status,
                'is_team_quota': self.is_team_quota,
                'is_expired': self.is_expired(),
                'assigned_by': self.assigned_by.get_full_name() if self.assigned_by else None,
                'activation_date': self.activation_date.isoformat() if self.activation_date else None,
                'client_fiscal_info': {
                    'fiscal_start_month': self.user.client_account.fiscal_year_start_month,
                    'fiscal_start_day': self.user.client_account.fiscal_year_start_day,
                    'currency': self.user.client_account.default_quota_currency
                }
            }
        }
    
    # === MÉTHODES DE CLASSE POUR MANAGERS ===
    
    @classmethod
    def create_quota_with_recurrence(
        cls, 
        user, 
        target_type, 
        target_value, 
        recurrence_type, 
        fiscal_year=None, 
        period_number=1,
        **kwargs
    ):
        """
        Crée un quota avec calcul automatique des périodes.
        
        Args:
            user: Instance User
            target_type: Type d'objectif (TargetType)
            target_value: Valeur cible
            recurrence_type: Type de récurrence (RecurrenceType)
            fiscal_year: Année fiscale (défaut: année courante)
            period_number: Numéro de période (défaut: 1)
            **kwargs: Autres champs optionnels
            
        Returns:
            SalesQuota: Instance créée
        """
        if fiscal_year is None:
            fiscal_year = user.client_account.get_current_fiscal_year()
        
        # Auto-générer le nom si absent
        if 'name' not in kwargs:
            period_display = cls._generate_period_display(recurrence_type, fiscal_year, period_number)
            kwargs['name'] = f"{target_type.replace('_', ' ').title()} - {period_display}"
        
        quota = cls(
            user=user,
            target_type=target_type,
            target_value=target_value,
            recurrence_type=recurrence_type,
            fiscal_year=fiscal_year,
            period_number=period_number,
            client_id=user.client_id,
            **kwargs
        )
        
        # Les dates seront calculées automatiquement dans clean()
        quota.full_clean()
        quota.save()
        
        return quota
    
    @classmethod
    def _generate_period_display(cls, recurrence_type, fiscal_year, period_number):
        """Génère un affichage de période pour le nom"""
        if recurrence_type == cls.RecurrenceType.ANNUAL:
            return f"FY{fiscal_year}"
        elif recurrence_type == cls.RecurrenceType.QUARTERLY:
            return f"Q{period_number} FY{fiscal_year}"
        elif recurrence_type == cls.RecurrenceType.MONTHLY:
            return f"M{period_number} FY{fiscal_year}"
        return f"FY{fiscal_year}"
    
    @classmethod
    def create_annual_quotas_for_team(cls, team_users, target_type, target_values, fiscal_year=None):
        """
        Crée des quotas annuels pour toute une équipe.
        
        Args:
            team_users: Liste ou QuerySet d'utilisateurs
            target_type: Type d'objectif commun
            target_values: Dict {user_id: target_value} ou valeur unique
            fiscal_year: Année fiscale (défaut: courante)
            
        Returns:
            list: Liste des quotas créés
        """
        created_quotas = []
        
        for user in team_users:
            if isinstance(target_values, dict):
                target_value = target_values.get(user.id)
                if not target_value:
                    continue
            else:
                target_value = target_values
            
            try:
                quota = cls.create_quota_with_recurrence(
                    user=user,
                    target_type=target_type,
                    target_value=target_value,
                    recurrence_type=cls.RecurrenceType.ANNUAL,
                    fiscal_year=fiscal_year
                )
                created_quotas.append(quota)
            except StandardizedValidationError:
                # Ignorer les erreurs (quota déjà existant, etc.)
                continue
        
        return created_quotas
    
    @classmethod
    def get_active_quota_for_user(cls, user, date_filter=None, target_type=None):
        """
        Récupère le quota actif pour un utilisateur à une date donnée.
        
        Args:
            user: Instance User
            date_filter: Date à vérifier (défaut: aujourd'hui)
            target_type: Type d'objectif spécifique (optionnel)
            
        Returns:
            SalesQuota or None: Quota actif trouvé
        """
        from datetime import date as date_module
        
        if date_filter is None:
            date_filter = date_module.today()
        
        queryset = cls.objects.filter(
            user=user,
            status=cls.QuotaStatus.ACTIVE,
            period_start__lte=date_filter,
            period_end__gte=date_filter,
            client_id=user.client_id
        )
        
        if target_type:
            queryset = queryset.filter(target_type=target_type)
        
        try:
            return queryset.first()
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def get_quotas_for_fiscal_period(cls, user, recurrence_type, fiscal_year, period_number=None):
        """
        Récupère les quotas pour une période fiscale spécifique.
        
        Args:
            user: Instance User
            recurrence_type: Type de récurrence
            fiscal_year: Année fiscale
            period_number: Numéro de période (optionnel)
            
        Returns:
            QuerySet: Quotas correspondants
        """
        queryset = cls.objects.filter(
            user=user,
            recurrence_type=recurrence_type,
            fiscal_year=fiscal_year,
            client_id=user.client_id
        )
        
        if period_number:
            queryset = queryset.filter(period_number=period_number)
        
        return queryset.order_by('period_number')
    
    @classmethod
    def get_current_fiscal_quotas(cls, user, recurrence_type=None):
        """
        Récupère les quotas pour l'année fiscale courante.
        
        Args:
            user: Instance User
            recurrence_type: Type de récurrence (optionnel)
            
        Returns:
            QuerySet: Quotas de l'année fiscale courante
        """
        current_fiscal_year = user.client_account.get_current_fiscal_year()
        
        queryset = cls.objects.filter(
            user=user,
            fiscal_year=current_fiscal_year,
            client_id=user.client_id
        )
        
        if recurrence_type:
            queryset = queryset.filter(recurrence_type=recurrence_type)
        
        return queryset.order_by('recurrence_type', 'period_number')
    
    @classmethod
    def create_quarterly_quotas_for_user(cls, user, target_type, quarterly_values, fiscal_year=None):
        """
        Crée les 4 quotas trimestriels pour un utilisateur.
        
        Args:
            user: Instance User
            target_type: Type d'objectif
            quarterly_values: Liste de 4 valeurs ou valeur unique
            fiscal_year: Année fiscale (défaut: courante)
            
        Returns:
            list: Liste des 4 quotas créés
        """
        created_quotas = []
        
        if not isinstance(quarterly_values, (list, tuple)):
            quarterly_values = [quarterly_values] * 4
        
        for quarter in range(1, 5):
            if quarter <= len(quarterly_values):
                target_value = quarterly_values[quarter - 1]
                
                try:
                    quota = cls.create_quota_with_recurrence(
                        user=user,
                        target_type=target_type,
                        target_value=target_value,
                        recurrence_type=cls.RecurrenceType.QUARTERLY,
                        fiscal_year=fiscal_year,
                        period_number=quarter
                    )
                    created_quotas.append(quota)
                except StandardizedValidationError:
                    continue
        
        return created_quotas
    
    @classmethod
    def get_team_quotas_summary(cls, team_users, period_start=None, period_end=None):
        """
        Résumé des quotas pour une équipe.
        
        Args:
            team_users: QuerySet ou liste d'utilisateurs
            period_start: Début période (optionnel)
            period_end: Fin période (optionnel)
            
        Returns:
            dict: Résumé agrégé de l'équipe
        """
        user_ids = [user.id for user in team_users]
        
        quotas_qs = cls.objects.filter(
            user_id__in=user_ids,
            status=cls.QuotaStatus.ACTIVE
        )
        
        if period_start:
            quotas_qs = quotas_qs.filter(period_start__gte=period_start)
        if period_end:
            quotas_qs = quotas_qs.filter(period_end__lte=period_end)
        
        team_summary = {
            'total_quotas': quotas_qs.count(),
            'quotas_by_type': {},
            'total_target_value': 0,
            'total_current_value': 0,
            'team_progress_percentage': 0,
            'quotas_achieved': 0,
            'quotas_details': []
        }
        
        for quota in quotas_qs:
            quota_summary = quota.get_quota_summary()
            team_summary['quotas_details'].append(quota_summary)
            
            # Agréger par type
            target_type = quota.target_type
            if target_type not in team_summary['quotas_by_type']:
                team_summary['quotas_by_type'][target_type] = {
                    'count': 0,
                    'total_target': 0,
                    'total_current': 0
                }
            
            team_summary['quotas_by_type'][target_type]['count'] += 1
            team_summary['quotas_by_type'][target_type]['total_target'] += quota_summary['target']['value']
            team_summary['quotas_by_type'][target_type]['total_current'] += quota_summary['performance']['current_value']
            
            # Totaux globaux
            team_summary['total_target_value'] += quota_summary['target']['value']
            team_summary['total_current_value'] += quota_summary['performance']['current_value']
            
            if quota_summary['performance']['is_achieved']:
                team_summary['quotas_achieved'] += 1
        
        # Calculer progression équipe
        if team_summary['total_target_value'] > 0:
            team_summary['team_progress_percentage'] = round(
                (team_summary['total_current_value'] / team_summary['total_target_value']) * 100, 1
            )
        
        return team_summary
    
    # === ACTIONS DE GESTION ===
    
    def activate(self, activated_by=None):
        """
        Active ce quota.
        
        Args:
            activated_by: Utilisateur qui active (optionnel)
        """
        if self.status != self.QuotaStatus.DRAFT:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(
                    detail="Only draft quotas can be activated"
                )
            )
        
        # Vérifier unicité avant activation
        self.clean()
        
        self.status = self.QuotaStatus.ACTIVE
        self.activation_date = timezone.now()
        if activated_by:
            self.assigned_by = activated_by
        
        self.save()
    
    def complete(self):
        """Marque ce quota comme complété."""
        if self.status != self.QuotaStatus.ACTIVE:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(
                    detail="Only active quotas can be completed"
                )
            )
        
        self.status = self.QuotaStatus.COMPLETED
        self.save()
    
    def cancel(self, reason=None):
        """
        Annule ce quota.
        
        Args:
            reason: Raison d'annulation (optionnel)
        """
        if self.status in [self.QuotaStatus.COMPLETED, self.QuotaStatus.CANCELLED]:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(
                    detail="Cannot cancel completed or already cancelled quotas"
                )
            )
        
        self.status = self.QuotaStatus.CANCELLED
        if reason:
            self.description = f"{self.description or ''}\n\nCancelled: {reason}".strip()
        
        self.save()