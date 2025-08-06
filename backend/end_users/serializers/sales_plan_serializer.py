# apps/end_users/serializers/sales_plan_serializer.py

from rest_framework import serializers
from django.db.models import Q, Count, Sum
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from ..services import UserPerformanceService
from end_users.models import SalesPlan, SalesQuota, User
from apps.campaign.models import Campaign


class SalesPlanSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer pour SalesPlan avec validation métier complète.
    
    CORRECTIONS CRITIQUES :
    - Signature UserPerformanceService corrigée
    - Suppression méthodes get_* redondantes (optimisation N+1)
    - Mapping performance_data selon vraie structure 
    - Architecture alignée sur SalesQuotaSerializer
    
    OPTIMISATIONS :
    - Source unique via UserPerformanceService (UN SEUL appel)
    - Relations via select_related au lieu de méthodes multiples
    - Annotations pour compteurs au lieu de queries séparées
    """
    
    # ===== CHAMPS DISPLAY (READ-ONLY) - OPTIMISÉS =====
    
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    
    # ✅ OPTIMISÉ : Relations via select_related (suppression méthodes get_*)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True) 
    team_name = serializers.CharField(source='user.team.name', read_only=True)
    team_id = serializers.IntegerField(source='user.team.id', read_only=True)
    organization_name = serializers.CharField(source='user.organization.name', read_only=True)
    organization_id = serializers.IntegerField(source='user.organization.id', read_only=True)
    
    # Informations quota via relations FK
    quota_target_value = serializers.DecimalField(
        source='quota.target_value',
        max_digits=15,
        decimal_places=2,
        read_only=True
    )
    quota_target_type = serializers.CharField(
        source='quota.target_type',
        read_only=True
    )
    quota_target_type_display = serializers.CharField(
        source='quota.get_target_type_display',
        read_only=True
    )
    
    # ✅ CORRIGÉ : Données calculées - UN SEUL appel UserPerformanceService
    performance_data = serializers.SerializerMethodField(read_only=True)
    
    # Statut et métriques du plan (calculés)
    is_active = serializers.BooleanField(read_only=True)
    is_current_period = serializers.SerializerMethodField(read_only=True)
    period_duration_days = serializers.SerializerMethodField(read_only=True)
    days_remaining = serializers.SerializerMethodField(read_only=True)
    
    # ✅ OPTIMISÉ : Compteurs via annotations (setup dans ViewSet)
    milestones_count = serializers.SerializerMethodField(read_only=True)
    milestones_achieved_count = serializers.SerializerMethodField(read_only=True)
    milestones_overdue_count = serializers.SerializerMethodField(read_only=True)
    
    linked_campaigns_count = serializers.SerializerMethodField(read_only=True)
    linked_campaigns_names = serializers.SerializerMethodField(read_only=True)
    
    # ===== CHAMPS WRITE =====
    
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.select_related('team', 'organization'),
        source='user',
        write_only=True,
        required=True
    )
    
    quota_id = serializers.PrimaryKeyRelatedField(
        queryset=SalesQuota.objects.select_related('user'),
        source='quota',
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
        model = SalesPlan
        fields = [
            # Champs de base
            'id', 'name', 'description', 'status', 'status_display',
            'period_start', 'period_end', 'created_at', 'updated_at',
            'last_progress_update',
            
            # Relations - Read (✅ optimisé via select_related)
            'user_name', 'user_email', 'team_name', 'team_id',
            'organization_name', 'organization_id',
            'quota_target_value', 'quota_target_type', 'quota_target_type_display',
            
            # Relations - Write
            'user_id', 'quota_id', 'linked_campaigns_ids',
            
            # Données calculées
            'performance_data', 'is_active', 'is_current_period',
            'period_duration_days', 'days_remaining',
            
            # Compteurs (✅ optimisé via annotations)
            'milestones_count', 'milestones_achieved_count', 'milestones_overdue_count',
            'linked_campaigns_count', 'linked_campaigns_names'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'last_progress_update'
        ]
    
    # ===== MÉTHODE PERFORMANCE CORRIGÉE =====
    
    def get_performance_data(self, obj) -> dict:
        """
        ✅ CORRECTION CRITIQUE : Données de performance via UserPerformanceService
        
        AVANT (❌ ERREURS) :
        - user=obj.user (signature incorrecte)
        - target_type=obj.quota.target_type (paramètre inexistant)
        - mapping incohérent des métriques
        
        APRÈS (✅ CORRIGÉ) :
        - user_id=obj.user.id (signature correcte)
        - client_id=obj.client_id (ajouté)
        - mapping selon vraie structure UserPerformanceService
        """
        # Vérification du contexte pour éviter appels inutiles
        if not self.context.get('include_performance_data', True):
            return {}
        if not hasattr(obj, 'user') or not obj.user:
            return {}
        
        try:
            # ✅ SIGNATURE CORRIGÉE - UserPerformanceService
            performance_data = UserPerformanceService.get_user_complete_performance(
                user_id=obj.user.id,  # ✅ Corrigé : user_id au lieu de user
                period_start=obj.period_start,
                period_end=obj.period_end,
                client_id=obj.client_id  # ✅ Ajouté : client_id manquant
                # ✅ Supprimé : target_type (paramètre inexistant)
            )
            
            # ✅ ENRICHISSEMENT CORRIGÉ avec calculs spécifiques au Sales Plan
            if obj.quota:
                quota_target = float(obj.quota.target_value)
                
                # ✅ Extraction selon vraie structure UserPerformanceService
                current_performance = self._extract_quota_performance_value(
                    performance_data, obj.quota.target_type
                )
                
                # Calcul achievement rate
                achievement_rate = 0
                if quota_target > 0:
                    achievement_rate = (current_performance / quota_target) * 100
                
                # ✅ Calcul gap analysis corrigé
                performance_data.update({
                    'quota_target': quota_target,
                    'achievement_rate': round(achievement_rate, 2),
                    'target_gap': max(0, quota_target - current_performance),
                    'is_on_track': achievement_rate >= obj.calculate_period_progress(),
                    'current_performance': current_performance,  # ✅ Ajouté pour clarté
                })
            
            return performance_data
            
        except Exception as e:
            # Fallback sécurisé en cas d'erreur
            return {
                'error': f'Performance data unavailable: {str(e)}',
                'quota_target': float(obj.quota.target_value) if obj.quota else 0,
                'current_performance': 0,
                'achievement_rate': 0,
                'is_on_track': False,
                'leads': {'qualified_count': 0, 'converted_count': 0},
                'opportunities': {'created_count': 0, 'won_value': 0, 'pipeline_value': 0},
                'meetings': {'completed_count': 0, 'total_managed': 0},
                'campaigns': {'total_managed': 0}
            }
    
    def _extract_quota_performance_value(self, performance_data: dict, quota_type: str) -> float:
        """
        ✅ NOUVEAU : Extraction selon la vraie structure UserPerformanceService
        
        Cohérent avec SalesPlan._extract_quota_performance_value()
        """
        try:
            if quota_type == 'closed_won':
                return float(performance_data.get('opportunities', {}).get('won_value', 0))
            elif quota_type == 'pipeline':
                return float(performance_data.get('opportunities', {}).get('pipeline_value', 0))
            elif quota_type == 'meetings':
                return float(performance_data.get('meetings', {}).get('completed_count', 0))
            elif quota_type == 'leads_accepted':
                return float(performance_data.get('leads', {}).get('qualified_count', 0))
            elif quota_type == 'opportunities':
                return float(performance_data.get('opportunities', {}).get('created_count', 0))
            elif quota_type == 'conversion_rate':
                return float(performance_data.get('leads', {}).get('conversion_rate_percentage', 0))
            else:
                return 0.0
        except (KeyError, TypeError, ValueError):
            return 0.0
    
    # ===== MÉTHODES DE CALCUL STATUT (SIMPLIFIÉES) =====
    
    def get_is_current_period(self, obj) -> bool:
        """Vérifie si nous sommes dans la période du plan"""
        return obj.is_current_period
    
    def get_period_duration_days(self, obj) -> int:
        """Durée de la période en jours"""
        return obj.period_duration_days
    
    def get_days_remaining(self, obj) -> int:
        """Jours restants dans la période"""
        return obj.days_remaining
    
    # ===== MÉTHODES DE COMPTAGE - OPTIMISÉES AVEC ANNOTATIONS =====
    
    def get_milestones_count(self, obj) -> int:
        """✅ OPTIMISÉ : Utilise annotation si disponible"""
        if hasattr(obj, '_milestones_count'):
            return obj._milestones_count
        if hasattr(obj, 'milestones_count_annotated'):
            return obj.milestones_count_annotated
        return obj.milestones.count()
    
    def get_milestones_achieved_count(self, obj) -> int:
        """✅ OPTIMISÉ : Utilise annotation si disponible"""
        if hasattr(obj, '_milestones_achieved'):
            return obj._milestones_achieved
        if hasattr(obj, 'milestones_achieved_annotated'):
            return obj.milestones_achieved_annotated
        return obj.milestones.filter(status='ACHIEVED').count()
    
    def get_milestones_overdue_count(self, obj) -> int:
        """✅ OPTIMISÉ : Utilise annotation si disponible"""
        if hasattr(obj, '_milestones_overdue'):
            return obj._milestones_overdue
        if hasattr(obj, 'milestones_overdue_annotated'):
            return obj.milestones_overdue_annotated
        return obj.milestones.filter(status='OVERDUE').count()
    
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
    
    # ===== VALIDATION MÉTIER (SIMPLIFIÉE) =====
    
    def validate(self, attrs):
        """
        ✅ SIMPLIFIÉ : Validation métier essentielle seulement
        Suppression validations complexes pour MVP
        """
        # 1. VALIDATION COHÉRENCE USER/QUOTA
        user = attrs.get('user')
        quota = attrs.get('quota')
        if user and quota and quota.user != user:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='quota_id'),
                field='quota_id'
            )
        
        # 2. VALIDATION PÉRIODES COHÉRENTES AVEC QUOTA
        period_start = attrs.get('period_start')
        period_end = attrs.get('period_end')
        
        if quota and period_start and period_end:
            # Utiliser les valeurs existantes si modification partielle
            if self.instance:
                period_start = period_start or self.instance.period_start
                period_end = period_end or self.instance.period_end
            
            # Vérifier que les périodes sont dans la période du quota
            if (period_start < quota.period_start or period_end > quota.period_end):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field='period range'),
                    field='period_start'
                )
        
        # 3. VALIDATION DATES COHÉRENTES
        if period_start and period_end and period_start > period_end:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATE_RANGE.format(
                    start_date=period_start,
                    end_date=period_end
                ),
                field='period_end'
            )
        
        return attrs
    
    def validate_name(self, value):
        """Validation du nom du plan"""
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='name'),
                field='name'
            )
        return value.strip()
    
    def validate_period_start(self, value):
        """Validation de la date de début"""
        if not value:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='period_start'),
                field='period_start'
            )
        return value
    
    def validate_period_end(self, value):
        """Validation de la date de fin"""
        if not value:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='period_end'),
                field='period_end'
            )
        return value
    
    # ===== OPTIMISATIONS QUERYSET =====
    
    @classmethod
    def setup_eager_loading(cls, queryset):
        """
        ✅ OPTIMISATION des requêtes avec select_related et annotations
        À utiliser dans les ViewSets pour éviter les requêtes N+1
        """
        return queryset.select_related(
            'user',
            'user__team', 
            'user__organization',
            'quota'
        ).prefetch_related(
            'linked_campaigns'
        ).annotate(
            # ✅ Annotations pour éviter les requêtes de comptage
            milestones_count_annotated=Count('milestones'),
            milestones_achieved_annotated=Count(
                'milestones', 
                filter=Q(milestones__status='ACHIEVED')
            ),
            milestones_overdue_annotated=Count(
                'milestones',
                filter=Q(milestones__status='OVERDUE')
            ),
            campaigns_count_annotated=Count('linked_campaigns')
        )
    
    def to_representation(self, instance):
        """
        ✅ OPTIMISÉ : Pré-calcul des compteurs si pas d'annotations
        Fallback pour compatibilité avec queries sans annotations
        """
        # Si pas d'annotations, pré-calculer pour éviter N+1
        if not hasattr(instance, 'milestones_count_annotated'):
            try:
                milestones = list(instance.milestones.all())
                instance._milestones_count = len(milestones)
                instance._milestones_achieved = len([m for m in milestones if m.status == 'ACHIEVED'])
                instance._milestones_overdue = len([m for m in milestones if m.status == 'OVERDUE'])
                
                campaigns = list(instance.linked_campaigns.all())
                instance._campaigns_count = len(campaigns)
                instance._campaigns_names = [c.name for c in campaigns]
            except Exception:
                # Silence les erreurs pour éviter de casser la sérialisation
                pass
        
        return super().to_representation(instance)