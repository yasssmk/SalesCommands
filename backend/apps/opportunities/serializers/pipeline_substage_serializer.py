# backend/apps/opportunities/serializers/pipeline_substage_serializer.py

from rest_framework import serializers
from django.utils import timezone
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages
from apps.opportunities.models import PipelineSubStage, PipelineStage
from apps.opportunities.config.pipeline_stages import PipelineStagesConfig


class PipelineSubStageSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer pour les sous-étapes de pipeline avec validation d'unicité et de logique métier
    """
    
    # Champs calculés (read-only)
    is_overdue = serializers.BooleanField(read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)
    progress_percentage = serializers.DecimalField(read_only=True, max_digits=5, decimal_places=2)
    can_be_deleted = serializers.BooleanField(read_only=True)
    activities_count = serializers.IntegerField(read_only=True)
    chasing_active = serializers.BooleanField(read_only=True)
    
    # Champs pour les relations
    stage_name = serializers.CharField(source='stage.name', read_only=True)
    substage_type_display = serializers.CharField(source='get_substage_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Champs pour les durées calculées
    actual_duration = serializers.IntegerField(read_only=True)
    remaining_duration = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = PipelineSubStage
        fields = [
            'id',
            'stage',
            'stage_name',
            'name',
            'description',
            'order',
            'substage_type',
            'substage_type_display',
            'status',
            'status_display',
            'is_active',
            'estimated_duration',
            'actual_duration',
            'remaining_duration',
            'started_at',
            'completed_at',
            'expected_completion_date',
            'is_overdue',
            'days_overdue',
            'progress_percentage',
            'can_be_deleted',
            'activities_count',
            'chasing_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'stage_name',
            'substage_type_display',
            'status_display',
            'actual_duration',
            'remaining_duration',
            'is_overdue',
            'days_overdue',
            'progress_percentage',
            'can_be_deleted',
            'activities_count',
            'chasing_active',
            'created_at',
            'updated_at'
        ]
    
    def get_is_overdue(self, obj):
        """Vérifie si la sous-étape est en retard"""
        if obj.expected_completion_date and obj.status != PipelineStagesConfig.SubStageStatus.COMPLETED:
            return timezone.now().date() > obj.expected_completion_date
        return False
    
    def get_days_overdue(self, obj):
        """Calcule le nombre de jours de retard"""
        if self.get_is_overdue(obj):
            return (timezone.now().date() - obj.expected_completion_date).days
        return 0
    
    def get_progress_percentage(self, obj):
        """Calcule le pourcentage de progression"""
        if obj.status == PipelineStagesConfig.SubStageStatus.COMPLETED:
            return 100.0
        elif obj.status == PipelineStagesConfig.SubStageStatus.IN_PROGRESS:
            if obj.started_at and obj.estimated_duration:
                days_elapsed = (timezone.now().date() - obj.started_at.date()).days
                return min(round((days_elapsed / obj.estimated_duration) * 100, 2), 90.0)
            return 25.0
        elif obj.status == PipelineStagesConfig.SubStageStatus.BLOCKED:
            return 0.0
        return 0.0
    
    def get_can_be_deleted(self, obj):
        """Vérifie si la sous-étape peut être supprimée"""
        # Ne peut pas être supprimée si elle a des activités liées
        if hasattr(obj, 'activities') and obj.activities.exists():
            return False
        
        # Ne peut pas être supprimée si elle est en cours ou terminée
        if obj.status in [PipelineStagesConfig.SubStageStatus.IN_PROGRESS, 
                         PipelineStagesConfig.SubStageStatus.COMPLETED]:
            return False
        
        return True
    
    def get_activities_count(self, obj):
        """Nombre d'activités liées à cette sous-étape"""
        if hasattr(obj, 'activities'):
            return obj.activities.count()
        return 0
    
    def get_chasing_active(self, obj):
        """Vérifie si le chasing automatique est actif"""
        # À implémenter quand le système de chasing sera créé
        return False
    
    def get_actual_duration(self, obj):
        """Durée réelle en jours"""
        if obj.started_at and obj.completed_at:
            return (obj.completed_at.date() - obj.started_at.date()).days
        elif obj.started_at:
            return (timezone.now().date() - obj.started_at.date()).days
        return 0
    
    def get_remaining_duration(self, obj):
        """Durée restante estimée"""
        if obj.status == PipelineStagesConfig.SubStageStatus.COMPLETED:
            return 0
        
        if obj.estimated_duration and obj.started_at:
            days_elapsed = (timezone.now().date() - obj.started_at.date()).days
            return max(0, obj.estimated_duration - days_elapsed)
        
        return obj.estimated_duration or 0
    
    def validate_name(self, value):
        """Validation du nom de la sous-étape"""
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD,
                field_name="name"
            )
        
        # Nettoyer le nom
        value = value.strip()
        
        # Validation de la longueur
        if len(value) < 2:
            raise StandardizedValidationError(
                "SubStage name must be at least 2 characters long",
                field_name="name"
            )
        
        if len(value) > 200:
            raise StandardizedValidationError(
                "SubStage name cannot exceed 200 characters",
                field_name="name"
            )
        
        return value
    
    def validate_order(self, value):
        """Validation de l'ordre"""
        if value is not None and value < 0:
            raise StandardizedValidationError(
                "Order must be a positive number",
                field_name="order"
            )
        return value
    
    def validate_estimated_duration(self, value):
        """Validation de la durée estimée"""
        if value is not None and value <= 0:
            raise StandardizedValidationError(
                OpportunityErrorMessages.SUBSTAGE_DURATION_INVALID,
                field_name="estimated_duration"
            )
        
        # Validation des limites raisonnables
        if value is not None and value > 365:
            raise StandardizedValidationError(
                "Estimated duration cannot exceed 365 days",
                field_name="estimated_duration"
            )
        
        return value
    
    def validate_substage_type(self, value):
        """Validation du type de sous-étape"""
        if value not in [choice[0] for choice in PipelineStagesConfig.SubStageType.choices]:
            raise StandardizedValidationError(
                OpportunityErrorMessages.SUBSTAGE_TYPE_INVALID.format(substage_type=value),
                field_name="substage_type"
            )
        return value
    
    def validate_stage(self, value):
        """Validation de l'étape parent"""
        if value:
            client_id = self._get_client_id_from_context()
            if str(value.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED,
                    field_name="stage"
                )
        return value
    
    def validate_started_at(self, value):
        """Validation de la date de début"""
        if value and value > timezone.now():
            raise StandardizedValidationError(
                "Start date cannot be in the future",
                field_name="started_at"
            )
        return value
    
    def validate_completed_at(self, value):
        """Validation de la date de fin"""
        if value and value > timezone.now():
            raise StandardizedValidationError(
                "Completion date cannot be in the future",
                field_name="completed_at"
            )
        return value
    
    def validate_expected_completion_date(self, value):
        """Validation de la date de fin prévue"""
        if value and value < timezone.now().date():
            # Permettre les dates passées mais avertir
            pass
        return value
    
    def validate(self, data):
        """Validation générale des données"""
        data = super().validate(data)
        
        # Récupérer les valeurs actuelles et nouvelles
        stage = data.get('stage', getattr(self.instance, 'stage', None))
        name = data.get('name')
        order = data.get('order')
        substage_type = data.get('substage_type', getattr(self.instance, 'substage_type', None))
        estimated_duration = data.get('estimated_duration', getattr(self.instance, 'estimated_duration', None))
        started_at = data.get('started_at', getattr(self.instance, 'started_at', None))
        completed_at = data.get('completed_at', getattr(self.instance, 'completed_at', None))
        status = data.get('status', getattr(self.instance, 'status', None))
        
        # Validation de l'unicité du nom dans l'étape
        if name and stage:
            self.validate_client_scoped_uniqueness(
                data={'stage': stage.id, 'name': name},
                unique_fields=['stage', 'name'],
                model_class=PipelineSubStage,
                error_message=f"A substage with name '{name}' already exists in this stage"
            )
        
        # Validation de l'unicité de l'ordre dans l'étape
        if order is not None and stage:
            self.validate_client_scoped_uniqueness(
                data={'stage': stage.id, 'order': order},
                unique_fields=['stage', 'order'],
                model_class=PipelineSubStage,
                error_message=f"A substage with order {order} already exists in this stage"
            )
        
        # Validation des règles métier selon le type
        if substage_type == PipelineStagesConfig.SubStageType.PROCESS_INTERNE_CLIENT:
            # Les processus internes clients doivent avoir une durée estimée
            if not estimated_duration:
                raise StandardizedValidationError(
                    "Internal client processes must have an estimated duration",
                    field_name="estimated_duration"
                )
        
        # Validation des dates
        if started_at and completed_at:
            if started_at >= completed_at:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.SUBSTAGE_DATE_INVALID,
                    field_name="completed_at"
                )
        
        # Validation des transitions d'état
        if self.instance and status:
            current_status = self.instance.status
            if current_status != status:
                self._validate_status_transition(current_status, status)
        
        # Validation de la cohérence statut/dates
        if status == PipelineStagesConfig.SubStageStatus.COMPLETED and not completed_at:
            raise StandardizedValidationError(
                "Completed substages must have a completion date",
                field_name="completed_at"
            )
        
        if status == PipelineStagesConfig.SubStageStatus.IN_PROGRESS and not started_at:
            raise StandardizedValidationError(
                "In-progress substages must have a start date",
                field_name="started_at"
            )
        
        return data
    
    def _validate_status_transition(self, current_status, new_status):
        """Valide les transitions d'état autorisées"""
        allowed_transitions = {
            PipelineStagesConfig.SubStageStatus.NOT_STARTED: [
                PipelineStagesConfig.SubStageStatus.IN_PROGRESS,
                PipelineStagesConfig.SubStageStatus.BLOCKED
            ],
            PipelineStagesConfig.SubStageStatus.IN_PROGRESS: [
                PipelineStagesConfig.SubStageStatus.COMPLETED,
                PipelineStagesConfig.SubStageStatus.BLOCKED,
                PipelineStagesConfig.SubStageStatus.NOT_STARTED
            ],
            PipelineStagesConfig.SubStageStatus.COMPLETED: [
                PipelineStagesConfig.SubStageStatus.IN_PROGRESS  # Permettre la réouverture
            ],
            PipelineStagesConfig.SubStageStatus.BLOCKED: [
                PipelineStagesConfig.SubStageStatus.IN_PROGRESS,
                PipelineStagesConfig.SubStageStatus.NOT_STARTED
            ]
        }
        
        if new_status not in allowed_transitions.get(current_status, []):
            raise StandardizedValidationError(
                f"Cannot transition from {current_status} to {new_status}",
                field_name="status"
            )
    
    def create(self, validated_data):
        """Création d'une nouvelle sous-étape"""
        try:
            # Ajouter le client_id automatiquement
            validated_data['client_id'] = self._get_client_id_from_context()
            
            # Créer la sous-étape
            substage = PipelineSubStage.objects.create(**validated_data)
            
            return substage
            
        except Exception as e:
            raise StandardizedValidationError(
                f"SubStage creation failed: {str(e)}"
            )
    
    def update(self, instance, validated_data):
        """Mise à jour d'une sous-étape existante"""
        try:
            # Vérifier les permissions
            client_id = self._get_client_id_from_context()
            if str(instance.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED
                )
            
            # Vérifier si la sous-étape peut être modifiée
            if instance.status == PipelineStagesConfig.SubStageStatus.COMPLETED:
                # Certaines modifications sont interdites pour les sous-étapes terminées
                restricted_fields = ['stage', 'substage_type', 'estimated_duration']
                for field in restricted_fields:
                    if field in validated_data:
                        raise StandardizedValidationError(
                            OpportunityErrorMessages.SUBSTAGE_ALREADY_COMPLETED.format(substage_name=instance.name),
                            field_name=field
                        )
            
            # Mettre à jour l'instance
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            instance.save()
            return instance
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                f"SubStage update failed: {str(e)}"
            )
    
    def to_representation(self, instance):
        """Enrichir la représentation avec des données calculées"""
        representation = super().to_representation(instance)
        
        # Ajouter les champs calculés
        representation['is_overdue'] = self.get_is_overdue(instance)
        representation['days_overdue'] = self.get_days_overdue(instance)
        representation['progress_percentage'] = self.get_progress_percentage(instance)
        representation['can_be_deleted'] = self.get_can_be_deleted(instance)
        representation['activities_count'] = self.get_activities_count(instance)
        representation['chasing_active'] = self.get_chasing_active(instance)
        representation['actual_duration'] = self.get_actual_duration(instance)
        representation['remaining_duration'] = self.get_remaining_duration(instance)
        
        return representation