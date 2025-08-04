# apps/core_apps/models/base_objective.py

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages


class BaseObjective(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Modèle abstrait pour tous les types d'objectifs (Campaign, Sales Plan, etc.)
    
    Fournit la structure commune et les méthodes de base pour :
    - Tracking des objectifs avec valeurs cibles
    - Calcul de progression automatique
    - Support GenericForeignKey pour flexibilité
    - Validation client-scope et contraintes
    
    Usage:
        class CampaignObjective(BaseObjective):
            campaign = models.ForeignKey(...)
            def get_current_value(self): return actual_value
            
        class SalesObjective(BaseObjective):  # Phase 2
            sales_plan = models.ForeignKey(...)
            def get_current_value(self): return performance_value
    """
    
    # === CHAMPS COMMUNS OBJECTIFS ===
    
    name = models.CharField(
        max_length=100,
        verbose_name=_('Objective Name'),
        help_text=_('Descriptive name for this objective')
    )
    
    target_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('Target Value'),
        help_text=_('The target value to achieve for this objective')
    )
    
    unit = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Unit of Measurement'),
        help_text=_('Optional unit (e.g., "leads", "€", "meetings")')
    )
    
    # === GENERIC RELATION - Flexibilité pour différents parents ===
    
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name=_('Related Object Type'),
        help_text=_('Type of object this objective belongs to (Campaign, Sales Plan, etc.)')
    )
    
    object_id = models.PositiveIntegerField(
        verbose_name=_('Related Object ID'),
        help_text=_('ID of the object this objective belongs to')
    )
    
    related_object = GenericForeignKey(
        'content_type', 
        'object_id'
    )
    
    # === METADATA ET TRACKING ===
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active'),
        help_text=_('Whether this objective is currently active')
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes'),
        help_text=_('Optional notes about this objective')
    )

    class Meta:
        abstract = True
        verbose_name = _('Base Objective')
        verbose_name_plural = _('Base Objectives')
        ordering = ['-created_at']
        indexes = [
            # Index pour les requêtes GenericForeignKey
            models.Index(fields=['content_type', 'object_id'], name='%(class)s_generic_idx'),
            # Index pour les requêtes actives
            models.Index(fields=['is_active', 'created_at'], name='%(class)s_active_idx'),
        ]

    def __str__(self):
        """Représentation string intelligente"""
        unit_display = f" {self.unit}" if self.unit else ""
        return f"{self.name}: {self.target_value}{unit_display}"

    # === MÉTHODES ABSTRAITES - À implémenter dans les sous-classes ===
    
    def get_current_value(self):
        """
        Récupère la valeur actuelle pour cet objectif.
        
        MÉTHODE ABSTRAITE - Chaque sous-classe doit l'implémenter selon sa logique :
        - CampaignObjective : utilise CampaignResultTracking  
        - SalesObjective : utilise UserPerformanceService
        - Autres : logique spécifique
        
        Returns:
            float: Valeur actuelle de l'objectif
            
        Raises:
            NotImplementedError: Si pas implémentée dans la sous-classe
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement get_current_value() method"
        )
    
    # === MÉTHODES CONCRÈTES - Logique commune réutilisable ===
    
    def get_progress_percentage(self):
        """
        Calcule le pourcentage de progression de cet objectif.
        
        Utilise get_current_value() implémentée par la sous-classe pour calculer
        automatiquement le pourcentage de progression.
        
        Returns:
            float: Pourcentage de progression (0-100), plafonné à 100%
        """
        try:
            current = self.get_current_value()
            target = float(self.target_value)
            
            if target == 0:
                return 0.0
                
            progress = (current / target) * 100
            return min(100.0, progress)  # Plafonner à 100%
            
        except Exception:
            # En cas d'erreur, retourner 0 plutôt que faire planter
            return 0.0
    
    def get_progress_status(self):
        """
        Détermine le statut de progression basé sur le pourcentage.
        
        Returns:
            str: Statut parmi 'ACHIEVED', 'ON_TRACK', 'AT_RISK', 'BEHIND'
        """
        progress = self.get_progress_percentage()
        
        if progress >= 100:
            return 'ACHIEVED'
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
            float: Valeur restante (0 si objectif déjà atteint)
        """
        try:
            current = self.get_current_value()
            target = float(self.target_value)
            remaining = target - current
            return max(0.0, remaining)  # Pas de valeurs négatives
        except Exception:
            return float(self.target_value)
    
    def is_achieved(self):
        """
        Vérifie si l'objectif est atteint.
        
        Returns:
            bool: True si l'objectif est atteint (>= 100%)
        """
        return self.get_progress_percentage() >= 100
    
    def get_progress_summary(self):
        """
        Retourne un résumé complet de la progression.
        
        Returns:
            dict: Résumé avec toutes les métriques calculées
        """
        try:
            current_value = self.get_current_value()
            target_value = float(self.target_value)
            progress_percentage = self.get_progress_percentage()
            
            return {
                'objective_id': self.id,
                'objective_name': self.name,
                'current_value': current_value,
                'target_value': target_value,
                'progress_percentage': round(progress_percentage, 1),
                'remaining_value': self.get_remaining_value(),
                'status': self.get_progress_status(),
                'is_achieved': self.is_achieved(),
                'unit': self.unit or '',
                'is_active': self.is_active
            }
        except Exception as e:
            # Fallback gracieux en cas d'erreur
            return {
                'objective_id': self.id,
                'objective_name': self.name,
                'current_value': 0,
                'target_value': float(self.target_value),
                'progress_percentage': 0.0,
                'remaining_value': float(self.target_value),
                'status': 'ERROR',
                'is_achieved': False,
                'unit': self.unit or '',
                'is_active': self.is_active,
                'error': str(e)
            }

    # === VALIDATION MÉTIER ===
    
    def clean(self):
        """Validation métier du modèle"""
        super().clean()
        
        # Valider target_value positive
        if self.target_value is not None and self.target_value <= 0:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(
                    detail="Target value must be greater than 0"
                )
            )
        
        # Valider que l'objet lié existe (si on a les IDs)
        if self.content_type_id and self.object_id:
            try:
                model_class = self.content_type.model_class()
                if not model_class.objects.filter(id=self.object_id).exists():
                    raise StandardizedValidationError(
                        CoreErrorMessages.OBJECT_NOT_FOUND
                    )
            except Exception:
                # Si erreur de validation, laisser Django gérer
                pass

    # === MÉTHODES UTILITAIRES POUR SOUS-CLASSES ===
    
    @classmethod
    def get_objectives_for_object(cls, obj):
        """
        Récupère tous les objectifs pour un objet donné.
        
        Args:
            obj: Instance du modèle parent (Campaign, SalesPlan, etc.)
            
        Returns:
            QuerySet: ObjectSet filtré pour cet objet
        """
        content_type = ContentType.objects.get_for_model(obj)
        return cls.objects.filter(
            content_type=content_type,
            object_id=obj.id,
            is_active=True
        )
    
    @classmethod 
    def calculate_objectives_summary(cls, objectives_queryset):
        """
        Calcule un résumé pour plusieurs objectifs.
        
        Args:
            objectives_queryset: QuerySet d'objectifs
            
        Returns:
            dict: Résumé agrégé des objectifs
        """
        if not objectives_queryset.exists():
            return {
                'total_objectives': 0,
                'achieved_objectives': 0,
                'overall_progress_percentage': 0.0,
                'objectives_by_status': {}
            }
        
        objectives_data = []
        status_counts = {}
        total_progress = 0
        achieved_count = 0
        
        for objective in objectives_queryset:
            summary = objective.get_progress_summary()
            objectives_data.append(summary)
            
            # Compter par statut
            status = summary['status'] 
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Accumuler pour moyennes
            total_progress += summary['progress_percentage']
            if summary['is_achieved']:
                achieved_count += 1
        
        total_objectives = len(objectives_data)
        overall_progress = total_progress / total_objectives if total_objectives > 0 else 0
        
        return {
            'total_objectives': total_objectives,
            'achieved_objectives': achieved_count,
            'overall_progress_percentage': round(overall_progress, 1),
            'objectives_by_status': status_counts,
            'objectives_details': objectives_data
        }