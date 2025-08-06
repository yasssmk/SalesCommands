# apps/end_users/serializers/sales_plan_serializer.py

from rest_framework import serializers
from django.db.models import Q
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
    Architecture alignée sur SalesQuotaSerializer - source unique via UserPerformanceService.
    """
    
    # ===== CHAMPS DISPLAY (READ-ONLY) =====
    
    status_display = serializers.CharField(
        source='get_status_display', 
        read_only=True
    )
    
    # Informations utilisateur via relations FK
    user_name = serializers.SerializerMethodField(read_only=True)
    user_email = serializers.SerializerMethodField(read_only=True)
    team_name = serializers.SerializerMethodField(read_only=True)
    team_id = serializers.SerializerMethodField(read_only=True)
    organization_name = serializers.SerializerMethodField(read_only=True)
    organization_id = serializers.SerializerMethodField(read_only=True)
    
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
    
    # Données calculées - UN SEUL appel UserPerformanceService par instance
    performance_data = serializers.SerializerMethodField(read_only=True)
    
    # Statut et métriques du plan (calculés)
    is_active = serializers.BooleanField(read_only=True)
    is_current_period = serializers.SerializerMethodField(read_only=True)
    period_duration_days = serializers.SerializerMethodField(read_only=True)
    days_remaining = serializers.SerializerMethodField(read_only=True)
    
    # Compteurs milestones
    milestones_count = serializers.SerializerMethodField(read_only=True)
    milestones_achieved_count = serializers.SerializerMethodField(read_only=True)
    milestones_overdue_count = serializers.SerializerMethodField(read_only=True)
    
    # Campagnes liées
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
            
            # Relations - Read
            'user_name', 'user_email', 'team_name', 'team_id',
            'organization_name', 'organization_id',
            'quota_target_value', 'quota_target_type', 'quota_target_type_display',
            
            # Relations - Write  
            'user_id', 'quota_id', 'linked_campaigns_ids',
            
            # Données calculées
            'performance_data', 'is_active', 'is_current_period',
            'period_duration_days', 'days_remaining',
            
            # Compteurs
            'milestones_count', 'milestones_achieved_count', 'milestones_overdue_count',
            'linked_campaigns_count', 'linked_campaigns_names'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'last_progress_update'
        ]
    
    # ===== MÉTHODES DE RÉCUPÉRATION DONNÉES UTILISATEUR =====
    
    def get_user_name(self, obj) -> str:
        """Nom complet de l'utilisateur"""
        if hasattr(obj, 'user') and obj.user:
            return obj.user.get_full_name()
        return ""
    
    def get_user_email(self, obj) -> str:
        """Email de l'utilisateur"""
        if hasattr(obj, 'user') and obj.user:
            return obj.user.email
        return ""
    
    def get_team_name(self, obj) -> str:
        """Nom de l'équipe"""
        if hasattr(obj, 'user') and obj.user and hasattr(obj.user, 'team') and obj.user.team:
            return obj.user.team.name
        return ""
    
    def get_team_id(self, obj) -> int:
        """ID de l'équipe"""
        if hasattr(obj, 'user') and obj.user and hasattr(obj.user, 'team') and obj.user.team:
            return obj.user.team.id
        return None
    
    def get_organization_name(self, obj) -> str:
        """Nom de l'organisation"""
        if hasattr(obj, 'user') and obj.user and hasattr(obj.user, 'organization') and obj.user.organization:
            return obj.user.organization.name
        return ""
    
    def get_organization_id(self, obj) -> int:
        """ID de l'organisation"""
        if hasattr(obj, 'user') and obj.user and hasattr(obj.user, 'organization') and obj.user.organization:
            return obj.user.organization.id
        return None
    
    # ===== MÉTHODES DE CALCUL PERFORMANCE =====
    
    def get_performance_data(self, obj) -> dict:
        """
        Données de performance via UserPerformanceService - UN SEUL APPEL.
        Architecture identique à SalesQuotaSerializer.
        """
        # Vérification du contexte pour éviter appels inutiles
        if not self.context.get('include_performance_data', True):
            return {}
        
        if not hasattr(obj, 'user') or not obj.user:
            return {}
        
        try:
            # Utilisation du service centralisé pour toutes les données
            performance_data = UserPerformanceService.get_user_complete_performance(
                user=obj.user,
                period_start=obj.period_start,
                period_end=obj.period_end,
                target_type=obj.quota.target_type if obj.quota else None
            )
            
            # Enrichissement avec calculs spécifiques au Sales Plan
            if obj.quota:
                quota_target = float(obj.quota.target_value)
                current_performance = performance_data.get('current_performance', 0)
                
                # Calcul achievement rate
                achievement_rate = 0
                if quota_target > 0:
                    achievement_rate = (current_performance / quota_target) * 100
                
                # Calcul gap analysis
                performance_data.update({
                    'quota_target': quota_target,
                    'achievement_rate': round(achievement_rate, 2),
                    'target_gap': max(0, quota_target - current_performance),
                    'is_on_track': achievement_rate >= obj._calculate_period_progress(),
                })
            
            return performance_data
            
        except Exception as e:
            # Fallback sécurisé en cas d'erreur
            return {
                'error': f'Performance data unavailable: {str(e)}',
                'quota_target': float(obj.quota.target_value) if obj.quota else 0,
                'current_performance': 0,
                'achievement_rate': 0,
                'is_on_track': False
            }
    
    # ===== MÉTHODES DE CALCUL STATUT =====
    
    def get_is_current_period(self, obj) -> bool:
        """Vérifie si nous sommes dans la période du plan"""
        return obj.is_current_period
    
    def get_period_duration_days(self, obj) -> int:
        """Durée de la période en jours"""
        return obj.period_duration_days
    
    def get_days_remaining(self, obj) -> int:
        """Jours restants dans la période"""
        return obj.days_remaining
    
    # ===== MÉTHODES DE COMPTAGE MILESTONES =====
    
    def get_milestones_count(self, obj) -> int:
        """Nombre total de milestones"""
        if hasattr(obj, '_milestones_count'):
            return obj._milestones_count
        return obj.milestones.count()
    
    def get_milestones_achieved_count(self, obj) -> int:
        """Nombre de milestones atteints"""
        if hasattr(obj, '_milestones_achieved'):
            return obj._milestones_achieved
        return obj.milestones.filter(status='ACHIEVED').count()
    
    def get_milestones_overdue_count(self, obj) -> int:
        """Nombre de milestones en retard"""
        if hasattr(obj, '_milestones_overdue'):
            return obj._milestones_overdue
        return obj.milestones.filter(status='OVERDUE').count()
    
    # ===== MÉTHODES CAMPAGNES LIÉES =====
    
    def get_linked_campaigns_count(self, obj) -> int:
        """Nombre de campagnes liées"""
        if hasattr(obj, '_campaigns_count'):
            return obj._campaigns_count
        return obj.linked_campaigns.count()
    
    def get_linked_campaigns_names(self, obj) -> list:
        """Noms des campagnes liées"""
        if hasattr(obj, '_campaigns_names'):
            return obj._campaigns_names
        return list(obj.linked_campaigns.values_list('name', flat=True))
    
    # ===== VALIDATION MÉTIER =====
    
    def validate(self, attrs):
        """Validation métier complète du Sales Plan"""
        
        # 1. VALIDATION COHÉRENCE USER/QUOTA
        user = attrs.get('user')
        quota = attrs.get('quota')
        
        if user and quota:
            # Vérification que le quota appartient bien à l'utilisateur
            if quota.user != user:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field='quota_id'),
                    field='quota_id'
                )
        
        # 2. VALIDATION PÉRIODES COHÉRENTES AVEC QUOTA
        period_start = attrs.get('period_start')
        period_end = attrs.get('period_end')
        
        if quota and (period_start or period_end):
            # Utiliser les valeurs existantes si modification partielle
            if self.instance:
                period_start = period_start or self.instance.period_start 
                period_end = period_end or self.instance.period_end
            
            if period_start and period_end:
                # Vérification que les périodes sont dans la période du quota
                if (period_start < quota.period_start or 
                    period_end > quota.period_end):
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(field='period range'),
                        field='period_start'
                    )
        
        # 3. VALIDATION DATES COHÉRENTES
        if period_start and period_end:
            if period_start > period_end:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATE_RANGE.format(
                        start_date=period_start, 
                        end_date=period_end
                    ),
                    field='period_end'
                )
        
        # 4. VALIDATION UNICITÉ PLAN ACTIF
        status = attrs.get('status', self.instance.status if self.instance else 'DRAFT')
        if status == 'ACTIVE' and user and quota:
            
            # Vérification qu'il n'y a pas déjà un plan actif pour ce user/quota
            existing_active = SalesPlan.objects.filter(
                user=user,
                quota=quota,
                status='ACTIVE'
            )
            
            # Exclure l'instance actuelle si on est en update
            if self.instance:
                existing_active = existing_active.exclude(pk=self.instance.pk)
            
            if existing_active.exists():
                raise StandardizedValidationError(
                    CoreErrorMessages.UNIQUE_CONSTRAINT.format(fields='active plan for user/quota'),
                    field='status'
                )
        
        return attrs
    
    def validate_name(self, value):
        """Validation du nom du plan"""
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='name'),
                field='name'
            )
        
        # Validation unicité du nom par utilisateur (ClientScopeManager gère déjà le client_id)
        user = self.initial_data.get('user_id')
        
        if user:
            existing = SalesPlan.objects.filter(
                user_id=user,
                name__iexact=value.strip()
            )
            
            # Exclure l'instance actuelle si update
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise StandardizedValidationError(
                    CoreErrorMessages.UNIQUE_CONSTRAINT.format(fields='plan name'),
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
        
        # Ne peut pas être dans le passé (sauf si modification d'un plan existant)
        if not self.instance and value < date.today():
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='period_start'),
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
        Optimisation des requêtes avec select_related et prefetch_related.
        À utiliser dans les ViewSets pour éviter les requêtes N+1.
        """
        return queryset.select_related(
            'user',
            'user__team', 
            'user__organization',
            'quota'
        ).prefetch_related(
            'milestones',
            'linked_campaigns'
        )
    
    def to_representation(self, instance):
        """
        Optimisation finale des données de sortie.
        Pré-calcul des compteurs pour éviter requêtes multiples.
        """
        # Pré-calcul des compteurs pour optimisation
        if hasattr(instance, 'milestones'):
            milestones = list(instance.milestones.all())
            instance._milestones_count = len(milestones)
            instance._milestones_achieved = len([m for m in milestones if m.status == 'ACHIEVED'])
            instance._milestones_overdue = len([m for m in milestones if m.status == 'OVERDUE'])
        
        if hasattr(instance, 'linked_campaigns'):
            campaigns = list(instance.linked_campaigns.all())
            instance._campaigns_count = len(campaigns)
            instance._campaigns_names = [c.name for c in campaigns]
        
        return super().to_representation(instance)