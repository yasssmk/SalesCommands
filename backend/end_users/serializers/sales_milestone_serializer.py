# apps/end_users/serializers/sales_milestone_serializer.py

from rest_framework import serializers
from django.db.models import Q
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
    Architecture alignée sur SalesPlanSerializer - calculs via méthodes du modèle.
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
    
    # Informations Sales Plan via relations FK
    sales_plan_name = serializers.CharField(
        source='sales_plan.name',
        read_only=True
    )
    
    sales_plan_status = serializers.CharField(
        source='sales_plan.status',
        read_only=True
    )
    
    user_name = serializers.SerializerMethodField(read_only=True)
    user_email = serializers.SerializerMethodField(read_only=True)
    
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
    
    # Données calculées - via méthodes du modèle
    progress_data = serializers.SerializerMethodField(read_only=True)
    
    # Statut et métriques calculées (via propriétés du modèle)
    is_achieved = serializers.SerializerMethodField(read_only=True)
    is_overdue = serializers.SerializerMethodField(read_only=True)
    days_remaining = serializers.SerializerMethodField(read_only=True)
    gap_to_target = serializers.SerializerMethodField(read_only=True)
    daily_pace_required = serializers.SerializerMethodField(read_only=True)
    
    # Indicateurs visuels pour dashboard
    status_indicator = serializers.SerializerMethodField(read_only=True)
    urgency_level = serializers.SerializerMethodField(read_only=True)
    
    # Campagnes liées
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
            
            # Relations - Read
            'sales_plan_name', 'sales_plan_status', 'user_name', 'user_email',
            'quota_target_value', 'quota_target_type',
            
            # Relations - Write  
            'sales_plan_id', 'linked_campaigns_ids',
            
            # Données calculées
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
    
    # ===== MÉTHODES DE RÉCUPÉRATION DONNÉES UTILISATEUR =====
    
    def get_user_name(self, obj) -> str:
        """Nom complet de l'utilisateur via sales_plan"""
        if hasattr(obj, 'sales_plan') and obj.sales_plan and obj.sales_plan.user:
            return obj.sales_plan.user.get_full_name()
        return ""
    
    def get_user_email(self, obj) -> str:
        """Email de l'utilisateur via sales_plan"""
        if hasattr(obj, 'sales_plan') and obj.sales_plan and obj.sales_plan.user:
            return obj.sales_plan.user.email
        return ""
    
    # ===== MÉTHODES DE CALCUL PROGRESS =====
    
    def get_progress_data(self, obj) -> dict:
        """
        Données de progression via méthode update_progress() du modèle.
        """
        # Vérification du contexte pour éviter appels inutiles
        if not self.context.get('include_progress_data', True):
            return {}
        
        try:
            # Utilisation de la méthode du modèle pour mise à jour
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
                'error': f'Progress data unavailable: {str(e)}'
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
        # Logique simplifiée - peut être enrichie avec historique
        if obj.last_progress_update:
            hours_since_update = (timezone.now() - obj.last_progress_update).total_seconds() / 3600
            if hours_since_update < 24:
                return 'RECENT_UPDATE'
            elif hours_since_update < 72:
                return 'MODERATE_UPDATE'
            else:
                return 'STALE_UPDATE'
        return 'NO_UPDATE'
    
    # ===== MÉTHODES DE CALCUL STATUT =====
    
    def get_is_achieved(self, obj) -> bool:
        """Vérifie si le milestone est atteint"""
        return obj.is_achieved
    
    def get_is_overdue(self, obj) -> bool:
        """Vérifie si le milestone est en retard"""
        return obj.is_overdue
    
    def get_days_remaining(self, obj) -> int:
        """Jours restants jusqu'à la date cible"""
        return obj.days_remaining
    
    def get_gap_to_target(self, obj) -> str:
        """Écart restant formaté"""
        gap = obj.gap_to_target
        return f"{gap:.2f}"
    
    def get_daily_pace_required(self, obj) -> str:
        """Rythme quotidien requis formaté"""
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
        """Validation métier complète du Sales Milestone"""
        
        # 1. VALIDATION DATE DANS PÉRIODE DU SALES PLAN
        sales_plan = attrs.get('sales_plan')
        target_date = attrs.get('target_date')
        
        if sales_plan and target_date:
            # Vérification que la date cible est dans la période du plan
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
        
        # 3. VALIDATION COHÉRENCE TYPE MILESTONE AVEC QUOTA
        milestone_type = attrs.get('milestone_type')
        if sales_plan and milestone_type and sales_plan.quota:
            quota_type = sales_plan.quota.target_type
            
            # Vérification compatibilité (exemple de logique métier)
            compatible_types = {
                'closed_won': ['CLOSED_WON', 'PIPELINE_VALUE', 'OPPORTUNITIES_CREATED'],
                'pipeline': ['PIPELINE_VALUE', 'OPPORTUNITIES_CREATED'],
                'meetings': ['MEETINGS_SECURED', 'LEADS_GENERATED'],
                'leads_accepted': ['LEADS_GENERATED', 'MEETINGS_SECURED']
            }
            
            if quota_type in compatible_types:
                if milestone_type not in compatible_types[quota_type] and milestone_type != 'CUSTOM':
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field=f'milestone type {milestone_type} not compatible with quota type {quota_type}'
                        ),
                        field='milestone_type'
                    )
        
        return attrs
    
    def validate_name(self, value):
        """Validation du nom du milestone"""
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='name'),
                field='name'
            )
        
        # Validation unicité du nom par sales_plan
        sales_plan_id = self.initial_data.get('sales_plan_id')
        
        if sales_plan_id:
            existing = SalesMilestone.objects.filter(
                sales_plan_id=sales_plan_id,
                name__iexact=value.strip()
            )
            
            # Exclure l'instance actuelle si update
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise StandardizedValidationError(
                    CoreErrorMessages.UNIQUE_CONSTRAINT.format(fields='milestone name per plan'),
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
        
        # Ne peut pas être dans le passé (sauf si modification)
        if not self.instance and value < date.today():
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='target_date cannot be in the past'),
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
    
    # ===== MÉTHODES D'ACTION =====
    
    def mark_as_achieved(self, validated_data):
        """Marque le milestone comme atteint lors de la création/modification"""
        if validated_data.get('force_achieved', False):
            validated_data['status'] = SalesMilestone.Status.ACHIEVED
            validated_data['achievement_rate'] = Decimal('100.00')
        return validated_data
    
    # ===== OPTIMISATIONS QUERYSET =====
    
    @classmethod
    def setup_eager_loading(cls, queryset):
        """
        Optimisation des requêtes avec select_related et prefetch_related.
        À utiliser dans les ViewSets pour éviter les requêtes N+1.
        """
        return queryset.select_related(
            'sales_plan',
            'sales_plan__user',
            'sales_plan__user__team', 
            'sales_plan__user__organization',
            'sales_plan__quota'
        ).prefetch_related(
            'linked_campaigns'
        )
    
    def to_representation(self, instance):
        """
        Optimisation finale des données de sortie.
        Pré-calcul des compteurs pour éviter requêtes multiples.
        """
        # Pré-calcul des compteurs pour optimisation
        if hasattr(instance, 'linked_campaigns'):
            campaigns = list(instance.linked_campaigns.all())
            instance._campaigns_count = len(campaigns)
            instance._campaigns_names = [c.name for c in campaigns]
        
        return super().to_representation(instance)