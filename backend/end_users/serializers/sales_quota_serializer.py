# apps/end_users/serializers/sales_quota_serializer.py

from rest_framework import serializers
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import date, timedelta
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from end_users.models import SalesQuota, User


class SalesQuotaSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer pour SalesQuota optimisé à la source.
    Architecture cache-ready mais performance d'abord dans les méthodes.
    """
    
    # ===== CHAMPS DISPLAY (READ-ONLY) =====
    
    target_type_display = serializers.CharField(
        source='get_target_type_display', 
        read_only=True
    )
    
    # Informations utilisateur via relations FK
    user_name = serializers.SerializerMethodField(read_only=True)
    user_email = serializers.SerializerMethodField(read_only=True) 
    team_name = serializers.SerializerMethodField(read_only=True)
    team_id = serializers.SerializerMethodField(read_only=True)
    organization_name = serializers.SerializerMethodField(read_only=True)
    organization_id = serializers.SerializerMethodField(read_only=True)
    
    # Métriques calculées - UN SEUL appel service par instance
    performance_data = serializers.SerializerMethodField(read_only=True)
    
    # Statut du quota (calculé localement)
    is_active = serializers.BooleanField(read_only=True)
    is_overdue = serializers.SerializerMethodField(read_only=True)
    period_duration_days = serializers.SerializerMethodField(read_only=True)
    period_type = serializers.SerializerMethodField(read_only=True)
    
    # ===== CHAMPS WRITE =====
    
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.select_related('team', 'organization'),  # Optimisation préventive
        source='user',
        write_only=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='User'),
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='User ID')
        }
    )
    
    class Meta:
        model = SalesQuota
        fields = [
            # Identifiants
            'id', 'user_id', 'user_name', 'user_email', 
            'team_name', 'team_id', 'organization_name', 'organization_id',
            
            # Configuration du quota
            'target_type', 'target_type_display', 'target_value',
            'period_start', 'period_end', 'period_duration_days', 'period_type',
            
            # Performance (données consolidées)
            'performance_data', 'is_active', 'is_overdue',
            
            # Métadonnées
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'created_by', 'updated_by',
            'target_type_display', 'user_name', 'user_email', 
            'team_name', 'team_id', 'organization_name', 'organization_id',
            'performance_data', 'is_active', 'is_overdue', 
            'period_duration_days', 'period_type'
        ]
    
    # ===== MÉTHODES DISPLAY USER/TEAM/ORG (OPTIMISÉES) =====
    
    def get_user_name(self, obj):
        """Nom complet utilisateur (optimisé avec select_related)"""
        return obj.user.get_full_name() if obj.user else None
    
    def get_user_email(self, obj):
        """Email utilisateur (optimisé avec select_related)"""
        return obj.user.email if obj.user else None
    
    def get_team_name(self, obj):
        """Nom de l'équipe (optimisé avec select_related)"""
        return obj.user.team.name if obj.user and obj.user.team else None
    
    def get_team_id(self, obj):
        """ID de l'équipe (optimisé avec select_related)"""
        return obj.user.team.id if obj.user and obj.user.team else None
    
    def get_organization_name(self, obj):
        """Nom de l'organisation (optimisé avec select_related)"""
        return obj.user.organization.name if obj.user and obj.user.organization else None
    
    def get_organization_id(self, obj):
        """ID de l'organisation (optimisé avec select_related)"""
        return obj.user.organization.id if obj.user and obj.user.organization else None
    
    # ===== PERFORMANCE - UN SEUL APPEL SERVICE =====
    
    def get_performance_data(self, obj):
        """
        UN SEUL appel au service qui retourne toutes les métriques.
        Architecture cache-ready : point d'entrée unique pour futurs optimisations.
        """
        try:
            from end_users.services.user_performance_service import UserPerformanceService
            
            # Appel unique au service optimisé
            return UserPerformanceService.get_user_quota_performance(
                user_id=obj.user.id,
                quota_id=obj.id,
                client_id=str(obj.client_id)
            )
            
        except Exception as e:
            # Fallback data structure pour compatibilité
            return {
                'quota_performance': {
                    'current_value': 0,
                    'target_value': float(obj.target_value),
                    'progress_percentage': 0,
                    'gap_to_target': float(obj.target_value),
                    'is_achieved': False
                },
                'timing': {
                    'days_remaining': self._calculate_days_remaining(obj),
                    'pace_vs_expected': 0
                },
                'status': 'unknown',
                'forecast': {},
                'error': str(e) if hasattr(e, '__str__') else 'Performance calculation failed'
            }
    
    # ===== MÉTHODES CALCULÉES LOCALES (SANS SERVICE) =====
    
    def get_is_overdue(self, obj):
        """Quota en retard ? (calcul local optimisé)"""
        today = timezone.now().date()
        return today > obj.period_end
    
    def get_period_duration_days(self, obj):
        """Durée de la période en jours (calcul local)"""
        return (obj.period_end - obj.period_start).days + 1
    
    def get_period_type(self, obj):
        """Type de période (calcul local optimisé)"""
        duration = self.get_period_duration_days(obj)
        if 28 <= duration <= 31:
            return 'monthly'
        elif 90 <= duration <= 92:
            return 'quarterly'
        elif 365 <= duration <= 366:
            return 'yearly'
        else:
            return 'custom'
    
    def _calculate_days_remaining(self, obj):
        """Helper pour calcul jours restants (utilisé en fallback)"""
        today = timezone.now().date()
        if today > obj.period_end:
            return 0
        return (obj.period_end - today).days + 1
    
    # ===== VALIDATIONS =====
    
    def validate_target_value(self, value):
        """Valider que target_value est positif"""
        if value <= 0:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field="Target Value (must be greater than 0)"
                )
            )
        return value
    
    def validate_period_start(self, value):
        """Valider la date de début"""
        if not value:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="Period Start Date")
            )
        return value
    
    def validate_period_end(self, value):
        """Valider la date de fin"""
        if not value:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="Period End Date")
            )
        return value
    
    def validate_target_type(self, value):
        """Valider le type de target"""
        if not value:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="Target Type")
            )
        
        # Vérifier que le target_type est valide
        valid_types = [choice[0] for choice in SalesQuota.TargetType.choices]
        if value not in valid_types:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field=f"Target Type (must be one of: {', '.join(valid_types)})"
                )
            )
        
        return value
    
    def validate(self, data):
        """Validation croisée du quota"""
        try:
            # Ajouter client_id si absent
            if 'client_id' not in data:
                client_id = self._get_client_id_from_context()
                data['client_id'] = client_id
            
            # Valider les dates
            period_start = data.get('period_start')
            period_end = data.get('period_end')
            
            if period_start and period_end:
                # Période cohérente
                if period_start >= period_end:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field="Period (start date must be before end date)"
                        )
                    )
                
                # Durée minimum (1 jour)
                if (period_end - period_start).days < 1:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field="Period (minimum duration is 1 day)"
                        )
                    )
                
                # Durée maximum (1 an)
                if (period_end - period_start).days > 366:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field="Period (maximum duration is 1 year)"
                        )
                    )
            
            # Valider l'unicité du quota actif
            user = data.get('user')
            if user and period_start and period_end:
                client_id = data.get('client_id')
                
                # Vérifier si un quota actif existe déjà pour cette période
                existing_quota_query = SalesQuota.objects.filter(
                    user=user,
                    client_id=client_id,
                    is_active=True
                ).filter(
                    # Chevauchement de périodes
                    Q(
                        period_start__lte=period_end,
                        period_end__gte=period_start
                    )
                )
                
                # Exclure l'instance actuelle en cas d'update
                if self.instance:
                    existing_quota_query = existing_quota_query.exclude(pk=self.instance.pk)
                
                if existing_quota_query.exists():
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field="Period (user already has an active quota for this period)"
                        )
                    )
            
            # Valider le client_scope de l'utilisateur
            if user and hasattr(user, 'client_account_id'):
                if str(user.client_account_id) != str(data.get('client_id')):
                    raise StandardizedValidationError(
                        CoreErrorMessages.CLIENT_MISMATCH
                    )
            
            return super().validate(data)
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Quota validation failed: {str(e)}"
                )
            )


class SalesQuotaSummarySerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer simplifié pour nested representations.
    Aucun appel service - calculs locaux uniquement pour performance.
    """
    
    target_type_display = serializers.CharField(
        source='get_target_type_display', 
        read_only=True
    )
    
    user_name = serializers.SerializerMethodField(read_only=True)
    team_name = serializers.SerializerMethodField(read_only=True)
    performance_status = serializers.SerializerMethodField(read_only=True)
    days_remaining = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = SalesQuota
        fields = [
            'id', 'user_name', 'team_name', 'target_type', 'target_type_display',
            'target_value', 'period_start', 'period_end',
            'performance_status', 'days_remaining', 'is_active'
        ]
        read_only_fields = fields
    
    def get_user_name(self, obj):
        """Nom utilisateur (optimisé pour nested)"""
        return obj.user.get_full_name() if obj.user else None
    
    def get_team_name(self, obj):
        """Nom équipe (optimisé pour nested)"""
        return obj.user.team.name if obj.user and obj.user.team else None
    
    def get_performance_status(self, obj):
        """Statut simplifié - calcul local sans service"""
        today = timezone.now().date()
        if today > obj.period_end:
            return 'overdue'
        elif (obj.period_end - today).days <= 7:
            return 'ending_soon'
        else:
            return 'active'
    
    def get_days_remaining(self, obj):
        """Jours restants - calcul local optimisé"""
        today = timezone.now().date()
        if today > obj.period_end:
            return 0
        return (obj.period_end - today).days + 1


class SalesQuotaListSerializer(SalesQuotaSummarySerializer):
    """
    Serializer pour les listes - hérite de Summary pour cohérence.
    Ajoute quelques champs supplémentaires calculés localement.
    """
    
    period_type = serializers.SerializerMethodField(read_only=True)
    
    class Meta(SalesQuotaSummarySerializer.Meta):
        fields = SalesQuotaSummarySerializer.Meta.fields + [
            'period_type', 'created_at'
        ]
    
    def get_period_type(self, obj):
        """Type de période - calcul local optimisé"""
        duration = (obj.period_end - obj.period_start).days + 1
        if 28 <= duration <= 31:
            return 'monthly'
        elif 90 <= duration <= 92:
            return 'quarterly'
        elif 365 <= duration <= 366:
            return 'yearly'
        else:
            return 'custom'


# ===== SERIALIZER POUR VIEWSETS OPTIMISÉS =====

class SalesQuotaViewSetSerializer(SalesQuotaSerializer):
    """
    Serializer spécialisé pour les ViewSets avec optimisations QuerySet.
    Utilisera select_related/prefetch_related au niveau ViewSet.
    """
    
    class Meta(SalesQuotaSerializer.Meta):
        # Même structure mais conçu pour être utilisé avec des queryset optimisés
        pass
    
    @classmethod
    def get_optimized_queryset(cls):
        """
        Queryset optimisé pour ce serializer.
        À utiliser dans les ViewSets pour éviter N+1 queries.
        """
        return SalesQuota.objects.select_related(
            'user',
            'user__team', 
            'user__organization',
            'created_by',
            'updated_by'
        ).prefetch_related(
            # Ajouts futurs si relations M2M nécessaires
        )