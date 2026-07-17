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
    Serializer COMPLET pour SalesQuota avec performance_data.
    ✅ CORRIGÉ : Target types, validations, performance optimisée.
    
    Usage: retrieve individual, actions performance - acceptable car 1 quota à la fois.
    """
    
    # ===== CHAMPS DISPLAY (READ-ONLY) =====
    
    target_type_display = serializers.CharField(
        source='get_target_type_display', 
        read_only=True
    )
    
    # Informations utilisateur via relations FK (optimisées avec select_related)
    user_name = serializers.SerializerMethodField(read_only=True)
    user_email = serializers.SerializerMethodField(read_only=True) 
    team_name = serializers.SerializerMethodField(read_only=True)
    team_id = serializers.SerializerMethodField(read_only=True)
    organization_name = serializers.SerializerMethodField(read_only=True)
    organization_id = serializers.SerializerMethodField(read_only=True)
    
    # Métriques calculées - UN SEUL appel service par instance
    performance_data = serializers.SerializerMethodField(read_only=True)
    
    # Statut du quota (calculé localement)
    is_active = serializers.SerializerMethodField(read_only=True)
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
            'name', 'target_type', 'target_type_display', 'target_value', 'unit',
            'recurrence_type', 'fiscal_year', 'period_number',
            'period_start', 'period_end', 'period_duration_days', 'period_type',
            
            # Statut et gestion
            'status', 'is_active', 'is_overdue', 'is_team_quota',
            'description', 'assigned_by', 'activation_date',
            
            # Performance (données consolidées)
            'performance_data',
            
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
        ✅ CORRIGÉ : UN SEUL appel au service qui retourne toutes les métriques.
        Usage acceptable pour retrieve individual (6 requêtes max par quota).
        """
        try:
            from backend.end_users.services.user_performance_service_obsolete import UserPerformanceService
            
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
    
    def get_is_active(self, obj):
        """✅ CORRIGÉ : is_active basé sur status (compatibilité)"""
        return obj.status == SalesQuota.QuotaStatus.ACTIVE
    
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
        """✅ CORRIGÉ : Validation croisée simplifiée pour MVP"""
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
            
            # ✅ MVP : Validation d'unicité simplifiée (un quota actif par user/période)
            user = data.get('user')
            if user and period_start and period_end:
                client_id = data.get('client_id')
                
                # Vérifier si un quota actif existe déjà pour cette période
                existing_quota_query = SalesQuota.objects.filter(
                    user=user,
                    client_id=client_id,
                    status='active'  # ✅ CORRIGÉ : utiliser status au lieu de is_active
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
    ✅ MVP OPTIMISÉ : Serializer pour listes SANS performance_data.
    
    Évite complètement le problème N+1 en utilisant seulement des calculs locaux.
    Usage: list, team_summary, nested representations.
    Performance: 1 seule requête SQL pour N quotas.
    """
    
    target_type_display = serializers.CharField(
        source='get_target_type_display', 
        read_only=True
    )
    
    # Expose the owner's id alongside user_name so a consumer can link a quota
    # to its user without a name-based join. The `user` FK already exists on the
    # model (it is the scope field); this only surfaces it in the list contract.
    user_id = serializers.PrimaryKeyRelatedField(source='user', read_only=True)
    user_name = serializers.SerializerMethodField(read_only=True)
    team_name = serializers.SerializerMethodField(read_only=True)
    performance_status = serializers.SerializerMethodField(read_only=True)
    days_remaining = serializers.SerializerMethodField(read_only=True)
    is_active = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SalesQuota
        fields = [
            'id', 'user_id', 'user_name', 'team_name', 'target_type', 'target_type_display',
            'target_value', 'unit', 'period_start', 'period_end',
            'performance_status', 'days_remaining', 'is_active', 'status',
            'created_at'
        ]
        read_only_fields = fields
    
    def get_user_name(self, obj):
        """Nom utilisateur (optimisé pour nested)"""
        return obj.user.get_full_name() if obj.user else None
    
    def get_team_name(self, obj):
        """Nom équipe (optimisé pour nested)"""
        return obj.user.team.name if obj.user and obj.user.team else None
    
    def get_is_active(self, obj):
        """✅ CORRIGÉ : is_active basé sur status"""
        return obj.status == SalesQuota.QuotaStatus.ACTIVE
    
    def get_performance_status(self, obj):
        """✅ Statut simplifié - calcul local sans service (zéro N+1)"""
        today = timezone.now().date()
        if today > obj.period_end:
            return 'overdue'
        elif (obj.period_end - today).days <= 7:
            return 'ending_soon'
        elif obj.status == SalesQuota.QuotaStatus.ACTIVE:
            return 'active'
        else:
            return 'inactive'
    
    def get_days_remaining(self, obj):
        """✅ Jours restants - calcul local optimisé (zéro N+1)"""
        today = timezone.now().date()
        if today > obj.period_end:
            return 0
        return (obj.period_end - today).days + 1


class SalesQuotaListSerializer(SalesQuotaSummarySerializer):
    """
    ✅ Serializer pour les listes - hérite de Summary pour cohérence.
    Ajoute quelques champs supplémentaires calculés localement.
    """
    
    period_type = serializers.SerializerMethodField(read_only=True)
    
    class Meta(SalesQuotaSummarySerializer.Meta):
        fields = SalesQuotaSummarySerializer.Meta.fields + [
            'period_type', 'name', 'description'
        ]
    
    def get_period_type(self, obj):
        """Type de période - calcul local optimisé (zéro N+1)"""
        duration = (obj.period_end - obj.period_start).days + 1
        if 28 <= duration <= 31:
            return 'monthly'
        elif 90 <= duration <= 92:
            return 'quarterly'
        elif 365 <= duration <= 366:
            return 'yearly'
        else:
            return 'custom'


class SalesQuotaViewSetSerializer(SalesQuotaSerializer):
    """
    ✅ Serializer spécialisé pour les ViewSets avec optimisations QuerySet.
    Hérite du serializer complet mais sera utilisé intelligemment par get_serializer_class().
    """
    
    class Meta(SalesQuotaSerializer.Meta):
        # Même structure mais conçu pour être utilisé avec des queryset optimisés
        pass
    
    @classmethod
    def get_optimized_queryset(cls):
        """
        ✅ Queryset optimisé pour ce serializer.
        À utiliser dans les ViewSets pour éviter N+1 queries sur les relations.
        """
        return SalesQuota.objects.select_related(
            'user',
            'user__team', 
            'user__organization',
            'assigned_by',
            'created_by',
            'updated_by'
        ).prefetch_related(
            # Ajouts futurs si relations M2M nécessaires
        )


# ===== SERIALIZERS UTILITAIRES =====

class SalesQuotaCreateSerializer(SalesQuotaSerializer):
    """
    ✅ Serializer optimisé pour la création.
    Simplifie les champs obligatoires pour MVP.
    """
    
    class Meta(SalesQuotaSerializer.Meta):
        fields = [
            'user_id', 'name', 'target_type', 'target_value', 
            'period_start', 'period_end', 'description'
        ]
        
    def create(self, validated_data):
        """Création avec valeurs par défaut intelligentes"""
        # Auto-set status à ACTIVE si pas spécifié
        if 'status' not in validated_data:
            validated_data['status'] = SalesQuota.QuotaStatus.ACTIVE
            validated_data['activation_date'] = timezone.now()
        
        return super().create(validated_data)


class SalesQuotaUpdateSerializer(SalesQuotaSerializer):
    """
    ✅ Serializer optimisé pour les updates.
    Permet de modifier sans casser les validations.
    """
    
    # Rendre user_id optionnel pour les updates
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.select_related('team', 'organization'),
        source='user',
        required=False
    )
    
    class Meta(SalesQuotaSerializer.Meta):
        # Tous les champs modifiables
        fields = [
            'user_id', 'name', 'target_type', 'target_value', 'unit',
            'period_start', 'period_end', 'status', 'description'
        ]


# ===== EXPORT POUR UTILISATION =====
__all__ = [
    'SalesQuotaSerializer',           # Complet avec performance_data
    'SalesQuotaSummarySerializer',    # MVP optimisé sans N+1
    'SalesQuotaListSerializer',       # Pour listes avec détails supplémentaires  
    'SalesQuotaViewSetSerializer',    # Pour ViewSets avec QuerySet optimisé
    'SalesQuotaCreateSerializer',     # Création simplifiée
    'SalesQuotaUpdateSerializer'      # Update optimisé
]