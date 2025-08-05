# apps/end_users/models/sales_plan.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date, timedelta
from typing import Dict, Any, Optional
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from apps.core_apps.services import UserPerformanceService


class SalesPlan(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Plan d'action commercial lié à un quota actif.
    Centralise la planification, le suivi et le pilotage des actions commerciales.
    Architecture MVP - Simple et fonctionnel.
    """
    
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', _('Draft')
        ACTIVE = 'ACTIVE', _('Active')
        PAUSED = 'PAUSED', _('Paused')
        COMPLETED = 'COMPLETED', _('Completed')
        CANCELLED = 'CANCELLED', _('Cancelled')
    
    # === INFORMATIONS DE BASE ===
    
    user = models.ForeignKey(
        'end_users.User',
        on_delete=models.CASCADE,
        related_name='sales_plans',
        verbose_name=_('User')
    )
    
    quota = models.ForeignKey(
        'end_users.SalesQuota',
        on_delete=models.CASCADE,
        related_name='sales_plans',
        verbose_name=_('Sales Quota'),
        help_text=_('The quota this plan is designed to achieve')
    )
    
    name = models.CharField(
        max_length=200,
        verbose_name=_('Plan Name'),
        help_text=_('Descriptive name for this sales plan')
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description'),
        help_text=_('Detailed description of the plan strategy')
    )
    
    # === PÉRIODE ET STATUT ===
    
    period_start = models.DateField(
        verbose_name=_('Period Start'),
        help_text=_('Start date of the plan period')
    )
    
    period_end = models.DateField(
        verbose_name=_('Period End'),
        help_text=_('End date of the plan period')
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name=_('Status')
    )
    
    # === MÉTRIQUES CALCULÉES (READ-ONLY) ===
    
    last_progress_update = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last Progress Update'),
        help_text=_('When progress was last calculated')
    )
    
    # === RELATIONS AVEC DONNÉES CRM ===
    
    linked_campaigns = models.ManyToManyField(
        'campaign.Campaign',
        related_name='sales_plans',
        blank=True,
        verbose_name=_('Linked Campaigns'),
        help_text=_('Campaigns associated with this sales plan')
    )
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['user', 'quota', 'name'],
        index_fields=['status', 'period_start', 'period_end']
    )):
        db_table = 'sales_plans'
        verbose_name = _('Sales Plan')
        verbose_name_plural = _('Sales Plans')
        ordering = ['-period_start', 'name']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['quota', 'status']),
            models.Index(fields=['period_start', 'period_end']),
            models.Index(fields=['last_progress_update']),
        ]
        constraints = [
            # Un seul plan actif par utilisateur/quota
            models.UniqueConstraint(
                fields=['user', 'quota'],
                condition=models.Q(status='ACTIVE'),
                name='unique_active_plan_per_user_quota'
            ),
            # Période cohérente
            models.CheckConstraint(
                check=models.Q(period_end__gte=models.F('period_start')),
                name='sales_plan_period_coherent'
            )
        ]
    
    def clean(self):
        """Validation des données cohérentes"""
        super().clean()
        
        if self.period_start and self.period_end:
            if self.period_start > self.period_end:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATE_RANGE,
                    field='period_end'
                )
        
        # Validation cohérence avec quota
        if self.quota and (self.period_start or self.period_end):
            if (self.period_start < self.quota.period_start or 
                self.period_end > self.quota.period_end):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATE_RANGE,
                    field='period_start'
                )
        
        # Validation utilisateur cohérent
        if self.quota and self.user and self.quota.user != self.user:
            raise StandardizedValidationError(
                CoreErrorMessages.PERMISSION_DENIED,
                field='user'
            )
    
    def save(self, *args, **kwargs):
        """Override save pour validation et cohérence"""
        # Validation avant sauvegarde
        self.full_clean()
        
        # Auto-fill periods depuis quota si non définis
        if self.quota and not self.period_start:
            self.period_start = self.quota.period_start
        if self.quota and not self.period_end:
            self.period_end = self.quota.period_end
            
        super().save(*args, **kwargs)
    
    # === MÉTHODES DE CALCUL PRINCIPALES ===
    
    def get_current_progress(self) -> Dict[str, Any]:
        """
        Calcule l'avancement actuel du plan via UserPerformanceService.
        Retourne données consolidées pour dashboard.
        """
        try:
            # Utilisation du service centralisé existant
            performance_data = UserPerformanceService.get_user_complete_performance(
                user=self.user,
                period_start=self.period_start,
                period_end=self.period_end,
                target_type=self.quota.target_type if self.quota else None
            )
            
            # Extraction des métriques clés
            current_progress = {
                'quota_target': float(self.quota.target_value) if self.quota else 0,
                'current_value': performance_data.get('current_performance', 0),
                'achievement_rate': performance_data.get('achievement_rate', 0),
                'pipeline_value': performance_data.get('pipeline_total', 0),
                'leads_count': performance_data.get('leads_count', 0),
                'opportunities_count': performance_data.get('opportunities_count', 0),
                'meetings_count': performance_data.get('meetings_count', 0),
                'period_progress': self._calculate_period_progress(),
                'is_on_track': performance_data.get('is_on_track', False),
                'last_updated': timezone.now().isoformat()
            }
            
            # Mise à jour timestamp
            self.last_progress_update = timezone.now()
            self.save(update_fields=['last_progress_update'])
            
            return current_progress
            
        except Exception as e:
            # Fallback sécurisé en cas d'erreur
            return {
                'quota_target': float(self.quota.target_value) if self.quota else 0,
                'current_value': 0,
                'achievement_rate': 0,
                'pipeline_value': 0,
                'leads_count': 0,
                'opportunities_count': 0,
                'meetings_count': 0,
                'period_progress': self._calculate_period_progress(),
                'is_on_track': False,
                'error': str(e),
                'last_updated': timezone.now().isoformat()
            }
    
    def calculate_gaps(self) -> Dict[str, Any]:
        """
        Calcule les écarts par rapport aux objectifs.
        Utilise les données de performance actuelles.
        """
        progress = self.get_current_progress()
        quota_target = progress['quota_target']
        current_value = progress['current_value']
        pipeline_value = progress['pipeline_value']
        period_progress = progress['period_progress']
        
        # Calculs d'écarts
        target_gap = max(0, quota_target - current_value)
        pipeline_gap = max(0, quota_target - current_value - pipeline_value)
        
        # Taux de conversion requis
        required_conversion_rate = 0
        if pipeline_value > 0 and target_gap > 0:
            required_conversion_rate = min(100, (target_gap / pipeline_value) * 100)
        
        # Rythme requis vs rythme actuel
        expected_value_at_date = quota_target * (period_progress / 100)
        pace_deviation = current_value - expected_value_at_date
        
        return {
            'target_gap': target_gap,
            'pipeline_gap': pipeline_gap,
            'required_conversion_rate': round(required_conversion_rate, 1),
            'pace_deviation': pace_deviation,
            'is_behind_pace': pace_deviation < 0,
            'expected_value_at_date': expected_value_at_date,
            'period_progress': period_progress,
            'calculated_at': timezone.now().isoformat()
        }
    
    def _calculate_period_progress(self) -> float:
        """Calcule le pourcentage d'avancement dans la période"""
        if not self.period_start or not self.period_end:
            return 0
            
        today = date.today()
        if today <= self.period_start:
            return 0
        elif today >= self.period_end:
            return 100
        else:
            total_days = (self.period_end - self.period_start).days
            elapsed_days = (today - self.period_start).days
            return round((elapsed_days / total_days) * 100, 1)
    
    # === MÉTHODES D'ÉTAT ===
    
    @property
    def is_active(self) -> bool:
        """Vérifie si le plan est actif"""
        return self.status == self.Status.ACTIVE
    
    @property
    def is_current_period(self) -> bool:
        """Vérifie si nous sommes dans la période du plan"""
        today = date.today()
        return self.period_start <= today <= self.period_end
    
    @property 
    def days_remaining(self) -> int:
        """Nombre de jours restants dans la période"""
        if not self.period_end:
            return 0
        today = date.today()
        if today > self.period_end:
            return 0
        return (self.period_end - today).days
    
    @property
    def period_duration_days(self) -> int:
        """Durée totale de la période en jours"""
        if not self.period_start or not self.period_end:
            return 0
        return (self.period_end - self.period_start).days + 1
    
    # === MÉTHODES D'ACTION ===
    
    def activate(self) -> bool:
        """Active le plan (désactive les autres plans actifs du même utilisateur/quota)"""
        try:
            # Désactiver autres plans actifs pour même user/quota
            SalesPlan.objects.filter(
                user=self.user,
                quota=self.quota,
                status=self.Status.ACTIVE
            ).exclude(pk=self.pk).update(status=self.Status.PAUSED)
            
            # Activer ce plan
            self.status = self.Status.ACTIVE
            self.save(update_fields=['status'])
            return True
            
        except Exception:
            return False
    
    def __str__(self):
        return f"{self.name} - {self.user.get_full_name()} ({self.get_status_display()})"
    
    def __repr__(self):
        return f"<SalesPlan: {self.name} [{self.status}]>"