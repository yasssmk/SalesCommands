# apps/end_users/serializers/sales_milestone_serializer.py

from rest_framework import serializers
from django.db.models import Q, Count
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from end_users.models import SalesMilestone, SalesPlan
from apps.campaign.models import Campaign


class SalesMilestoneSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer pour SalesMilestone avec validation métier et tracking automatique.
    
    ✅ ARCHITECTURE CORRECTE : Délègue calculs au modèle SalesMilestone (déjà corrigé)
    ✅ PAS d'appel direct UserPerformanceService (bonne séparation des responsabilités)
    
    OPTIMISATIONS MINEURES :
    - Relations via select_related au lieu de méthodes 
    - Cohérence avec SalesPlanSerializer corrigé
    """
    
    # ===== CHAMPS DISPLAY (READ-ONLY) =====
    
    milestone_type_display = serializers.CharField(
        source='get_milestone_type_display', 
        read_only=True
    )
    
    status_display = serializers.CharField(
        source='get_status_display', 
        read_only=True
    )
    
    # ✅ OPTIMISÉ : Relations via select_related
    sales_plan_name = serializers.CharField(
        source='sales_plan.name',
        read_only=True
    )
    
    sales_plan_status = serializers.CharField(
        source='sales_plan.status',
        read_only=True
    )
    
    # ✅ OPTIMISÉ : Relations directes au lieu de méthodes
    user_name = serializers.CharField(
        source='sales_plan.user.get_full_name',
        read_only=True
    )
    
    user_email = serializers.CharField(
        source='sales_plan.user.email',
        read_only=True
    )
    
    # Informations quota via relations Sales Plan
    quota_target_value = serializers.DecimalField(
        source='sales_plan.quota.target_value',
        max_digits=15,
        decimal_places=2,
        read_only=True
    )
    
    quota_target_type = serializers.CharField(
        source='sales_plan.quota.target_type',
        read_only=True
    )
    
    # ✅ CORRECT : Données calculées via méthodes du modèle (déjà corrigé)
    progress_data = serializers.SerializerMethodField(read_only=True)
    
    # ✅ CORRECT : Statut via propriétés du modèle (pas de service direct)
    is_achieved = serializers.BooleanField(read_only=True)
    is_overdue = serializers.SerializerMethodField(read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)
    gap_to_target = serializers.SerializerMethodField(read_only=True)
    daily_pace_required = serializers.SerializerMethodField(read_only=True)
    
    # Indicateurs visuels pour dashboard
    status_indicator = serializers.SerializerMethodField(read_only=True)
    urgency_level = serializers.SerializerMethodField(read_only=True)
    
    # ✅ OPTIMISÉ : Campagnes avec annotations si disponibles
    linked_campaigns_count = serializers.SerializerMethodField(read_only=True)
    linked_campaigns_names = serializers.SerializerMethodField(read_only=True)
    
    # ===== CHAMPS WRITE =====
    
    sales_plan_id = serializers.PrimaryKeyRelatedField(
        queryset=SalesPlan.objects.select_related('user', 'quota'),
        source='sales_plan',
        write_only=True,
        required=True
    )
    
    linked_campaigns_ids = serializers.PrimaryKeyRelatedField(
        queryset=Campaign.objects.all(),
        source='linked_campaigns',
        many=True,
        write_only=True,
        required=False
    )
    
    class Meta:
        model = SalesMilestone
        fields = [
            # Champs de base
            'id', 'name', 'description', 'milestone_type', 'milestone_type_display',
            'status', 'status_display', 'target_value', 'target_date',
            'current_value', 'achievement_rate', 'last_progress_update',
            'created_at', 'updated_at',
            
            # Relations - Read (✅ optimisé via select_related)
            'sales_plan_name', 'sales_plan_status', 'user_name', 'user_email',
            'quota_target_value', 'quota_target_type',
            
            # Relations - Write  
            'sales_plan_id', 'linked_campaigns_ids',
            
            # Données calculées (✅ via modèle)
            'progress_data', 'is_achieved', 'is_overdue', 'days_remaining',
            'gap_to_target', 'daily_pace_required',
            
            # Indicateurs dashboard
            'status_indicator', 'urgency_level',
            
            # Campagnes
            'linked_campaigns_count', 'linked_campaigns_names'
        ]
        read_only_fields = [
            'id', 'current_value', 'achievement_rate', 'last_progress_update',
            'created_at', 'updated_at', 'status'  # Status calculé automatiquement
        ]
    
    # ===== MÉTHODES DE CALCUL PROGRESS =====
    
    def get_progress_data(self, obj) -> dict:
        """
        ✅ CORRECT : Données de progression via méthode update_progress() du modèle.
        Le modèle SalesMilestone a été corrigé avec la bonne signature UserPerformanceService.
        """
        # Vérification du contexte pour éviter appels inutiles
        if not self.context.get('include_progress_data', True):
            return {}
        
        try:
            # ✅ Utilisation de la méthode corrigée du modèle
            progress_result = obj.update_progress()
            
            # Enrichissement avec données contextuelles
            return {
                **progress_result,
                'target_completion_rate': self._calculate_target_completion_rate(obj),
                'performance_vs_timeline': self._calculate_performance_vs_timeline(obj),
                'trend_indicator': self._calculate_trend_indicator(obj)
            }
            
        except Exception as e:
            # Fallback sécurisé
            return {
                'milestone_id': obj.id,
                'current_value': float(obj.current_value),
                'target_value': float(obj.target_value),
                'achievement_rate': float(obj.achievement_rate),
                'status': obj.status,
                'error': f'Progress data unavailable: {str(e)}',
                'success': False
            }
    
    def _calculate_target_completion_rate(self, obj) -> float:
        """Calcule le taux de completion attendu à cette date"""
        if not obj.sales_plan or not obj.target_date:
            return 0
        
        today = date.today()
        if today >= obj.target_date:
            return 100
        
        total_days = (obj.target_date - obj.sales_plan.period_start).days
        elapsed_days = (today - obj.sales_plan.period_start).days
        
        if total_days > 0:
            return min(100, max(0, (elapsed_days / total_days) * 100))
        return 0
    
    def _calculate_performance_vs_timeline(self, obj) -> str:
        """Compare performance actuelle vs timeline attendue"""
        target_rate = self._calculate_target_completion_rate(obj)
        actual_rate = float(obj.achievement_rate)
        
        if actual_rate >= target_rate * 1.1:
            return 'AHEAD'
        elif actual_rate >= target_rate * 0.9:
            return 'ON_TRACK'
        else:
            return 'BEHIND'
    
    def _calculate_trend_indicator(self, obj) -> str:
        """Indicateur de tendance basé sur la progression récente"""
        if obj.last_progress_update:
            hours_since_update = (timezone.now() - obj.last_progress_update).total_seconds() / 3600
            if hours_since_update < 24:
                return 'RECENT_UPDATE'
            elif hours_since_update < 72:
                return 'MODERATE_UPDATE'
            else:
                return 'STALE_UPDATE'
        return 'NO_UPDATE'
    
    # ===== MÉTHODES DE CALCUL STATUT (SIMPLIFIÉES) =====
    
    def get_is_overdue(self, obj) -> bool:
        """✅ CORRECT : Propriété du modèle"""
        return obj.is_overdue
    
    def get_gap_to_target(self, obj) -> str:
        """✅ CORRECT : Propriété du modèle formatée"""
        gap = obj.gap_to_target
        return f"{gap:.2f}"
    
    def get_daily_pace_required(self, obj) -> str:
        """✅ CORRECT : Propriété du modèle formatée"""
        pace = obj.daily_pace_required
        return f"{pace:.2f}"
    
    # ===== INDICATEURS DASHBOARD =====
    
    def get_status_indicator(self, obj) -> str:
        """Indicateur coloré pour dashboard (GREEN/YELLOW/RED)"""
        if obj.is_achieved:
            return 'GREEN'
        elif obj.is_overdue:
            return 'RED'
        elif obj.days_remaining <= 3:
            return 'YELLOW'
        elif float(obj.achievement_rate) >= 80:
            return 'GREEN'
        elif float(obj.achievement_rate) >= 50:
            return 'YELLOW'
        else:
            return 'RED'
    
    def get_urgency_level(self, obj) -> str:
        """Niveau d'urgence pour priorisation"""
        if obj.is_achieved:
            return 'COMPLETED'
        elif obj.is_overdue:
            return 'CRITICAL'
        elif obj.days_remaining <= 1:
            return 'URGENT'
        elif obj.days_remaining <= 7:
            return 'HIGH'
        else:
            return 'NORMAL'
    
    # ===== MÉTHODES CAMPAGNES LIÉES (OPTIMISÉES) =====
    
    def get_linked_campaigns_count(self, obj) -> int:
        """✅ OPTIMISÉ : Utilise annotation si disponible"""
        if hasattr(obj, '_campaigns_count'):
            return obj._campaigns_count
        if hasattr(obj, 'campaigns_count_annotated'):
            return obj.campaigns_count_annotated
        return obj.linked_campaigns.count()
    
    def get_linked_campaigns_names(self, obj) -> list:
        """✅ OPTIMISÉ : Utilise prefetch si disponible"""
        if hasattr(obj, '_campaigns_names'):
            return obj._campaigns_names
        return list(obj.linked_campaigns.values_list('name', flat=True))
    
    # ===== VALIDATION MÉTIER (SIMPLIFIÉE POUR MVP) =====
    
    def validate(self, attrs):
        """✅ SIMPLIFIÉ : Validation métier essentielle pour MVP"""
        
        # 1. VALIDATION DATE DANS PÉRIODE DU SALES PLAN
        sales_plan = attrs.get('sales_plan')
        target_date = attrs.get('target_date')
        
        if sales_plan and target_date:
            if (target_date < sales_plan.period_start or 
                target_date > sales_plan.period_end):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATE_RANGE.format(
                        start_date=sales_plan.period_start,
                        end_date=sales_plan.period_end
                    ),
                    field='target_date'
                )
        
        # 2. VALIDATION VALEUR CIBLE POSITIVE
        target_value = attrs.get('target_value')
        if target_value is not None and target_value <= 0:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='target_value must be positive'),
                field='target_value'
            )
        
        # ✅ SIMPLIFIÉ : Suppression validation compatibilité complexe pour MVP
        # La logique métier reste dans le modèle
        
        return attrs
    
    def validate_name(self, value):
        """Validation du nom du milestone"""
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='name'),
                field='name'
            )
        return value.strip()
    
    def validate_target_date(self, value):
        """Validation de la date cible"""
        if not value:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='target_date'),
                field='target_date'
            )
        return value
    
    def validate_target_value(self, value):
        """Validation de la valeur cible"""
        if not value:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='target_value'),
                field='target_value'
            )
        
        if value <= 0:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='target_value must be positive'),
                field='target_value'
            )
        
        return value
    
    def validate_milestone_type(self, value):
        """Validation du type de milestone"""
        if not value:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='milestone_type'),
                field='milestone_type'
            )
        
        # Vérification que c'est un choix valide
        valid_choices = [choice[0] for choice in SalesMilestone.MilestoneType.choices]
        if value not in valid_choices:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field=f'milestone_type must be one of {valid_choices}'),
                field='milestone_type'
            )
        
        return value
    
    # ===== OPTIMISATIONS QUERYSET =====
    
    @classmethod
    def setup_eager_loading(cls, queryset):
        """
        ✅ OPTIMISÉ : Requêtes avec select_related et annotations
        À utiliser dans les ViewSets pour éviter les requêtes N+1
        """
        return queryset.select_related(
            'sales_plan',
            'sales_plan__user',
            'sales_plan__user__team', 
            'sales_plan__user__organization',
            'sales_plan__quota'
        ).prefetch_related(
            'linked_campaigns'
        ).annotate(
            # ✅ Annotations pour éviter les requêtes de comptage
            campaigns_count_annotated=Count('linked_campaigns')
        )
    
    def to_representation(self, instance):
        """
        ✅ OPTIMISÉ : Pré-calcul des compteurs si pas d'annotations
        """
        # Si pas d'annotations, pré-calculer pour éviter N+1
        if not hasattr(instance, 'campaigns_count_annotated'):
            try:
                campaigns = list(instance.linked_campaigns.all())
                instance._campaigns_count = len(campaigns)
                instance._campaigns_names = [c.name for c in campaigns]
            except Exception:
                # Silence les erreurs pour éviter de casser la sérialisation
                pass
        
        return super().to_representation(instance)