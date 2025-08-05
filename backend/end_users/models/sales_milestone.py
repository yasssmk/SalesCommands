# apps/end_users/models/sales_milestone.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
from typing import Dict, Any, Optional
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from apps.core_apps.services import UserPerformanceService


class SalesMilestone(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Jalon intermédiaire dans un Sales Plan.
    Permet de définir des objectifs datés et de suivre leur progression.
    Architecture MVP - Calculs automatiques via UserPerformanceService.
    """
    
    class MilestoneType(models.TextChoices):
        LEADS_GENERATED = 'LEADS_GENERATED', _('Leads Generated')
        MEETINGS_SECURED = 'MEETINGS_SECURED', _('Meetings Secured')
        OPPORTUNITIES_CREATED = 'OPPORTUNITIES_CREATED', _('Opportunities Created')
        PIPELINE_VALUE = 'PIPELINE_VALUE', _('Pipeline Value')
        CLOSED_WON = 'CLOSED_WON', _('Closed Won')
        CUSTOM = 'CUSTOM', _('Custom Milestone')
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        ACHIEVED = 'ACHIEVED', _('Achieved')
        OVERDUE = 'OVERDUE', _('Overdue')
        CANCELLED = 'CANCELLED', _('Cancelled')
    
    # === INFORMATIONS DE BASE ===
    
    sales_plan = models.ForeignKey(
        'end_users.SalesPlan',
        on_delete=models.CASCADE,
        related_name='milestones',
        verbose_name=_('Sales Plan')
    )
    
    name = models.CharField(
        max_length=200,
        verbose_name=_('Milestone Name'),
        help_text=_('Descriptive name for this milestone')
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description'),
        help_text=_('Detailed description of what needs to be achieved')
    )
    
    milestone_type = models.CharField(
        max_length=30,
        choices=MilestoneType.choices,
        verbose_name=_('Milestone Type'),
        help_text=_('Type of metric to track for this milestone')
    )
    
    # === OBJECTIFS ET DATES ===
    
    target_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name=_('Target Value'),
        help_text=_('Numeric target to achieve (count or monetary value)')
    )
    
    target_date = models.DateField(
        verbose_name=_('Target Date'),
        help_text=_('Date by which this milestone should be achieved')
    )
    
    # === STATUT ET SUIVI ===
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_('Status')
    )
    
    current_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Current Value'),
        help_text=_('Current achievement level (updated automatically)')
    )
    
    achievement_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Achievement Rate %'),
        help_text=_('Percentage of target achieved (updated automatically)')
    )
    
    last_progress_update = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last Progress Update'),
        help_text=_('When progress was last calculated')
    )
    
    # === RELATIONS OPTIONNELLES ===
    
    linked_campaigns = models.ManyToManyField(
        'campaign.Campaign',
        related_name='milestones',
        blank=True,
        verbose_name=_('Linked Campaigns'),
        help_text=_('Campaigns contributing to this milestone')
    )
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['sales_plan', 'name'],
        index_fields=['milestone_type', 'status', 'target_date']
    )):
        db_table = 'sales_milestones'
        verbose_name = _('Sales Milestone')
        verbose_name_plural = _('Sales Milestones')
        ordering = ['target_date', 'name']
        indexes = [
            models.Index(fields=['sales_plan', 'status']),
            models.Index(fields=['milestone_type', 'target_date']),
            models.Index(fields=['target_date', 'status']),
            models.Index(fields=['achievement_rate']),
            models.Index(fields=['last_progress_update']),
        ]
        constraints = [
            # Valeur cible positive
            models.CheckConstraint(
                check=models.Q(target_value__gt=0),
                name='milestone_target_value_positive'
            ),
            # Taux d'achievement entre 0 et 999.99%
            models.CheckConstraint(
                check=models.Q(achievement_rate__gte=0, achievement_rate__lte=999.99),
                name='milestone_achievement_rate_bounds'
            )
        ]
    
    def clean(self):
        """Validation des données cohérentes"""
        super().clean()
        
        # Validation date dans période du plan
        if self.sales_plan and self.target_date:
            if (self.target_date < self.sales_plan.period_start or 
                self.target_date > self.sales_plan.period_end):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATE_RANGE,
                    field='target_date'
                )
        
        # Validation valeur cible positive
        if self.target_value and self.target_value <= 0:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD,
                field='target_value'
            )
    
    def save(self, *args, **kwargs):
        """Override save pour validation et mise à jour auto"""
        # Validation avant sauvegarde
        self.full_clean()
        
        # Mise à jour automatique du statut basé sur la date
        self._update_status_based_on_date()
        
        super().save(*args, **kwargs)
    
    # === MÉTHODES DE CALCUL PRINCIPALES ===
    
    def update_progress(self) -> Dict[str, Any]:
        """
        Met à jour la progression du milestone via UserPerformanceService.
        Calcule current_value et achievement_rate automatiquement.
        """
        try:
            # Period jusqu'à la target_date pour calcul progressif
            period_end = min(self.target_date, date.today())
            
            # Données de performance via service centralisé
            performance_data = UserPerformanceService.get_user_complete_performance(
                user=self.sales_plan.user,
                period_start=self.sales_plan.period_start,
                period_end=period_end,
                target_type=self._get_performance_metric_key()
            )
            
            # Extraction de la valeur selon le type de milestone
            current_value = self._extract_current_value_from_performance(performance_data)
            
            # Calcul du taux d'achievement
            achievement_rate = 0
            if self.target_value > 0:
                achievement_rate = min(999.99, (current_value / float(self.target_value)) * 100)
            
            # Mise à jour des champs
            self.current_value = Decimal(str(current_value))
            self.achievement_rate = Decimal(str(round(achievement_rate, 2)))
            self.last_progress_update = timezone.now()
            
            # Mise à jour du statut selon progression
            self._update_status_based_on_progress()
            
            # Sauvegarde avec update_fields pour éviter récursion
            self.save(update_fields=[
                'current_value', 
                'achievement_rate', 
                'last_progress_update',
                'status'
            ])
            
            return {
                'milestone_id': self.id,
                'current_value': float(self.current_value),
                'target_value': float(self.target_value),
                'achievement_rate': float(self.achievement_rate),
                'status': self.status,
                'is_achieved': self.is_achieved,
                'days_remaining': self.days_remaining,
                'updated_at': self.last_progress_update.isoformat()
            }
            
        except Exception as e:
            # Fallback sécurisé en cas d'erreur
            return {
                'milestone_id': self.id,
                'current_value': float(self.current_value),
                'target_value': float(self.target_value),
                'achievement_rate': float(self.achievement_rate),
                'status': self.status,
                'error': str(e),
                'updated_at': timezone.now().isoformat()
            }
    
    def _get_performance_metric_key(self) -> Optional[str]:
        """Mappe le type de milestone vers la clé de métrique dans UserPerformanceService"""
        mapping = {
            self.MilestoneType.LEADS_GENERATED: 'leads',
            self.MilestoneType.MEETINGS_SECURED: 'meetings', 
            self.MilestoneType.OPPORTUNITIES_CREATED: 'opportunities',
            self.MilestoneType.PIPELINE_VALUE: 'pipeline',
            self.MilestoneType.CLOSED_WON: 'closed_won',
            self.MilestoneType.CUSTOM: None
        }
        return mapping.get(self.milestone_type)
    
    def _extract_current_value_from_performance(self, performance_data: Dict[str, Any]) -> float:
        """Extrait la valeur actuelle selon le type de milestone"""
        if self.milestone_type == self.MilestoneType.LEADS_GENERATED:
            return performance_data.get('leads_count', 0)
        elif self.milestone_type == self.MilestoneType.MEETINGS_SECURED:
            return performance_data.get('meetings_count', 0)
        elif self.milestone_type == self.MilestoneType.OPPORTUNITIES_CREATED:
            return performance_data.get('opportunities_count', 0)
        elif self.milestone_type == self.MilestoneType.PIPELINE_VALUE:
            return performance_data.get('pipeline_total', 0)
        elif self.milestone_type == self.MilestoneType.CLOSED_WON:
            return performance_data.get('current_performance', 0)
        else:
            # Pour CUSTOM, on garde la valeur actuelle
            return float(self.current_value)
    
    def _update_status_based_on_date(self):
        """Met à jour le statut basé sur la date cible"""
        today = date.today()
        
        if self.status == self.Status.ACHIEVED:
            return  # Ne pas changer si déjà achieved
        
        if today > self.target_date and self.achievement_rate < 100:
            self.status = self.Status.OVERDUE
        elif self.achievement_rate >= 100:
            self.status = self.Status.ACHIEVED
        elif today >= self.target_date - timedelta(days=7):  # 7 jours avant échéance
            self.status = self.Status.IN_PROGRESS
        else:
            self.status = self.Status.PENDING
    
    def _update_status_based_on_progress(self):
        """Met à jour le statut basé sur la progression"""
        if self.achievement_rate >= 100:
            self.status = self.Status.ACHIEVED
        elif self.achievement_rate > 0:
            # Vérifie si en retard
            today = date.today()
            if today > self.target_date:
                self.status = self.Status.OVERDUE
            else:
                self.status = self.Status.IN_PROGRESS
    
    # === PROPRIÉTÉS CALCULÉES ===
    
    @property
    def is_achieved(self) -> bool:
        """Vérifie si le milestone est atteint"""
        return self.achievement_rate >= 100
    
    @property
    def is_overdue(self) -> bool:
        """Vérifie si le milestone est en retard"""
        return date.today() > self.target_date and not self.is_achieved
    
    @property
    def days_remaining(self) -> int:
        """Nombre de jours restants jusqu'à la date cible"""
        today = date.today()
        if today > self.target_date:
            return 0
        return (self.target_date - today).days
    
    @property
    def gap_to_target(self) -> Decimal:
        """Écart restant pour atteindre l'objectif"""
        return max(Decimal('0'), self.target_value - self.current_value)
    
    @property
    def daily_pace_required(self) -> Decimal:
        """Rythme quotidien requis pour atteindre l'objectif"""
        if self.days_remaining <= 0:
            return Decimal('0')
        return self.gap_to_target / self.days_remaining
    
    # === MÉTHODES D'ACTION ===
    
    def mark_as_achieved(self, user=None) -> bool:
        """Marque manuellement le milestone comme atteint"""
        try:
            self.status = self.Status.ACHIEVED
            self.achievement_rate = Decimal('100.00')
            if user:
                self.updated_by = user
            self.save(update_fields=['status', 'achievement_rate', 'updated_by'])
            return True
        except Exception:
            return False
    
    def cancel(self, user=None) -> bool:
        """Annule le milestone"""
        try:
            self.status = self.Status.CANCELLED
            if user:
                self.updated_by = user
            self.save(update_fields=['status', 'updated_by'])
            return True
        except Exception:
            return False
    
    def __str__(self):
        return f"{self.name} - {self.sales_plan.name} ({self.achievement_rate}%)"
    
    def __repr__(self):
        return f"<SalesMilestone: {self.name} [{self.status}] {self.achievement_rate}%>"