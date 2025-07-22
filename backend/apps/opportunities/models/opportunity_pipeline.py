# backend/apps/opportunities/models/opportunity_pipeline.py

from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
from typing import List, Dict, Optional, Any
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import StandardizedValidationError
from core.error_messages import OpportunityErrorMessages, CoreErrorMessages
from ..config.pipeline_stages import PipelineStagesConfig


class OpportunityPipeline(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Tracker intelligent pour l'état et la progression d'un pipeline d'opportunité.
    
    Responsabilités LIMITÉES (processus de vente non-linéaire):
    - Observation et tracking de la position courante
    - Détection intelligente de l'avancement basée sur les activités
    - Métriques globales et vue d'ensemble
    - Accès centralisé aux métadonnées de tous les substages
    
    PHILOSOPHIE:
    - Pas d'avancement automatique (processus non-linéaire)
    - Détection: activité créée dans substage = position probable
    - Avancement manuel par l'utilisateur lors d'organisation de RDV
    - Mapping complet qualification → closing
    """
    
    PipelineStatus = PipelineStagesConfig.PipelineStatus
    
    # ===== RELATIONS PRINCIPALES =====
    
    opportunity = models.OneToOneField(
        'opportunities.Opportunity',
        on_delete=models.CASCADE,
        related_name='pipeline',
        verbose_name=_('Opportunity'),
        help_text=_('Opportunity this pipeline belongs to')
    )
    
    current_stage = models.ForeignKey(
        'opportunities.PipelineStage',
        on_delete=models.SET_NULL,
        related_name='current_opportunities',
        null=True,
        blank=True,
        verbose_name=_('Current Stage'),
        help_text=_('Current stage of this pipeline')
    )
    
    current_substage = models.ForeignKey(
        'opportunities.PipelineSubStage',
        on_delete=models.SET_NULL,
        related_name='current_opportunities',
        null=True,
        blank=True,
        verbose_name=_('Current SubStage'),
        help_text=_('Current substage of this pipeline for precise tracking')
    )
    
    # ===== STATUT ET TRACKING =====
    
    status = models.CharField(
        max_length=20,
        choices=PipelineStatus.choices,
        default=PipelineStatus.ACTIVE,
        verbose_name=_('Pipeline Status'),
        help_text=_('Current status of this pipeline')
    )
    
    # ===== DATES IMPORTANTES =====
    
    started_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Started At'),
        help_text=_('When this pipeline was started')
    )
    
    last_updated = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Last Updated'),
        help_text=_('When this pipeline was last updated')
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Completed At'),
        help_text=_('When this pipeline was completed')
    )
    
    expected_close_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Expected Close Date'),
        help_text=_('Calculated expected completion date based on substage durations')
    )
    
    # ===== MÉTRIQUES DE TRACKING =====
    
    actual_duration_days = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Actual Duration (Days)'),
        help_text=_('Actual number of days since pipeline started')
    )
    
    # ===== PERSONNALISATION =====
    
    is_customized = models.BooleanField(
        default=False,
        verbose_name=_('Is Customized'),
        help_text=_('Whether this pipeline has been customized from the template')
    )
    
    customization_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Customization Notes'),
        help_text=_('Notes about customizations made to this pipeline')
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=['opportunity', 'current_stage', 'current_substage', 'status']
    )):
        db_table = 'opportunity_pipelines'
        verbose_name = _('Opportunity Pipeline')
        verbose_name_plural = _('Opportunity Pipelines')
        ordering = ['-last_updated', 'opportunity__title']

    def __str__(self):
        return f"Pipeline: {self.opportunity.title} ({self.get_status_display()})"

    # ===== OPTIMISATIONS PREFETCH =====

    @classmethod
    def get_optimized_queryset(cls):
        """
        Queryset optimisé avec tous les prefetch nécessaires pour éviter les N+1
        """
        return cls.objects.select_related(
            'opportunity',
            'opportunity__contact',
            'opportunity__deal_owner',
            'current_stage',
            'current_stage__template',
            'current_substage',
            'current_substage__stage'
        ).prefetch_related(
            'opportunity__pipeline_templates__stages__substages',
            'opportunity__pipeline_templates__stages__substages__metadata',
            'opportunity__pipeline_templates__stages__substages__activities',
            'opportunity__activities'
        )

    # ===== PROPRIÉTÉS CALCULÉES - PROGRESSION =====

    @property
    def progress_percentage(self) -> Decimal:
        """
        Calcule le pourcentage de progression du pipeline
        Basé sur les substages complétées
        """
        total_substages = self.get_total_substages_count()
        if total_substages == 0:
            return Decimal('0.00')
        
        completed_substages = self.get_completed_substages_count()
        return Decimal(completed_substages / total_substages * 100).quantize(Decimal('0.01'))

    @property
    def days_since_started(self) -> int:
        """Nombre de jours depuis le début du pipeline"""
        if not self.started_at:
            return 0
        return (timezone.now() - self.started_at).days

    @property
    def days_until_expected_close(self) -> Optional[int]:
        """Nombre de jours jusqu'à la date de clôture prévue"""
        if not self.expected_close_date:
            return None
        delta = self.expected_close_date - date.today()
        return delta.days

    # ===== MÉTHODES DE CALCUL - PROGRESSION =====

    def get_total_stages_count(self) -> int:
        """Compte le nombre total d'étapes dans le pipeline"""
        template = self.get_pipeline_template()
        if not template:
            return 0
        return template.stages.filter(is_active=True).count()

    def get_completed_stages_count(self) -> int:
        """Compte le nombre d'étapes complétées"""
        template = self.get_pipeline_template()
        if not template:
            return 0
        
        return template.stages.filter(
            is_active=True,
            status=PipelineStagesConfig.StageStatus.COMPLETED
        ).count()

    def get_total_substages_count(self) -> int:
        """Compte le nombre total de sous-étapes dans le pipeline"""
        template = self.get_pipeline_template()
        if not template:
            return 0
        
        from .pipeline_substage import PipelineSubStage
        return PipelineSubStage.objects.filter(
            stage__template=template,
            is_active=True
        ).count()

    def get_completed_substages_count(self) -> int:
        """Compte le nombre de sous-étapes complétées"""
        template = self.get_pipeline_template()
        if not template:
            return 0
        
        from .pipeline_substage import PipelineSubStage
        return PipelineSubStage.objects.filter(
            stage__template=template,
            is_active=True,
            status=PipelineStagesConfig.SubStageStatus.COMPLETED
        ).count()

    # ===== MÉTHODES DE CALCUL - RETARDS GLOBAUX =====

    def is_pipeline_overdue(self) -> bool:
        """
        Détermine si le pipeline global est en retard
        Délègue aux stages/substages individuels
        """
        template = self.get_pipeline_template()
        if not template:
            return False

        # Vérifier si au moins une substage est en retard
        from .pipeline_substage import PipelineSubStage
        overdue_substages = PipelineSubStage.objects.filter(
            stage__template=template,
            is_active=True
        )
        
        return any(substage.is_overdue() for substage in overdue_substages)

    def get_overdue_summary(self) -> Dict[str, Any]:
        """
        Retourne un résumé des retards sans gérer les détails individuels
        """
        template = self.get_pipeline_template()
        if not template:
            return {'has_overdue': False, 'count': 0}

        from .pipeline_substage import PipelineSubStage
        substages = PipelineSubStage.objects.filter(
            stage__template=template,
            is_active=True
        )
        
        overdue_count = sum(1 for substage in substages if substage.is_overdue())
        
        return {
            'has_overdue': overdue_count > 0,
            'overdue_count': overdue_count,
            'total_active_substages': substages.count()
        }

    # ===== MÉTHODES DE CALCUL - PRÉDICTIONS =====

    def calculate_expected_completion(self) -> Optional[date]:
        """
        Calcule la date de fin prévue basée sur les durées des substages restantes
        """
        from .pipeline_substage import PipelineSubStage
        
        template = self.get_pipeline_template()
        if not template:
            return None

        # Récupérer les substages non complétées
        remaining_substages = PipelineSubStage.objects.filter(
            stage__template=template,
            is_active=True,
            status__in=[
                PipelineStagesConfig.SubStageStatus.NOT_STARTED,
                PipelineStagesConfig.SubStageStatus.IN_PROGRESS
            ]
        )

        total_remaining_days = 0
        for substage in remaining_substages:
            if substage.expected_duration_days:
                total_remaining_days += substage.expected_duration_days

        if total_remaining_days > 0:
            return date.today() + timedelta(days=total_remaining_days)
        
        return None

    # ===== DÉTECTION POSITION SIMPLE =====

    def get_current_position(self) -> Dict[str, Any]:
        """
        Détecte la position courante basée sur les activités IN_PROGRESS
        Prend celle avec le stage le plus avancé
        """
        from .substage_activity import SubStageActivity
        
        template = self.get_pipeline_template()
        if not template:
            return {
                'current_stage': self.current_stage.name if self.current_stage else None,
                'current_substage': self.current_substage.name if self.current_substage else None,
                'detected_from_activities': False
            }

        # Filtrer les activités IN_PROGRESS liées aux substages
        in_progress_activities = SubStageActivity.objects.filter(
            substage__stage__template=template,
            activity__status='IN_PROGRESS'
        ).select_related(
            'substage', 'substage__stage'
        ).order_by('-substage__stage__order', '-substage__order')

        detected_substage = None
        if in_progress_activities.exists():
            # Prendre celle avec le stage le plus avancé
            detected_substage = in_progress_activities.first().substage

        return {
            'current_stage': self.current_stage.name if self.current_stage else None,
            'current_substage': self.current_substage.name if self.current_substage else None,
            'detected_from_activities': detected_substage is not None,
            'detected_stage': detected_substage.stage.name if detected_substage else None,
            'detected_substage': detected_substage.name if detected_substage else None
        }

    # ===== MÉTRIQUES SIMPLES =====

    def get_pipeline_summary(self) -> Dict[str, Any]:
        """
        Retourne un résumé simple du pipeline
        """
        overdue_summary = self.get_overdue_summary()
        position = self.get_current_position()
        
        return {
            'current_position': position,
            'progress': {
                'percentage': float(self.progress_percentage),
                'completed_stages': self.get_completed_stages_count(),
                'total_stages': self.get_total_stages_count()
            },
            'health': {
                'is_overdue': overdue_summary['has_overdue'],
                'overdue_count': overdue_summary['overdue_count'],
                'status': self.status
            },
            'timeline': {
                'days_elapsed': self.days_since_started,
                'expected_close': self.expected_close_date,
                'days_until_close': self.days_until_expected_close
            }
        }

    # ===== MÉTHODES UTILITAIRES =====

    def get_pipeline_template(self):
        """Récupère le template du pipeline (via l'opportunité)"""
        try:
            return self.opportunity.pipeline_templates.first()
        except Exception:
            return None

    def _update_expected_completion(self):
        """Met à jour la date de fin prévue basée sur le mapping complet"""
        self.expected_close_date = self.calculate_expected_completion()
        self.actual_duration_days = self.days_since_started
        self.save(update_fields=['expected_close_date', 'actual_duration_days'])

    # ===== MÉTHODES DE VALIDATION =====

    def save(self, *args, **kwargs):
        """
        Sauvegarde avec validation et mise à jour automatique des métriques
        """
        # Validation de cohérence
        if self.current_substage and self.current_stage:
            if self.current_substage.stage != self.current_stage:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_REQUEST.format(
                        reason=_("Current substage must belong to the current stage")
                    ),
                )
        
        # Mise à jour du client_id depuis l'opportunité
        if self.opportunity and not self.client_id:
            self.client_id = self.opportunity.client_id
        
        # Mise à jour automatique des métriques
        self.actual_duration_days = self.days_since_started
        
        super().save(*args, **kwargs)