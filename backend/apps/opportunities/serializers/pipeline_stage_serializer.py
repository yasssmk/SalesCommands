# backend/apps/opportunities/serializers/pipeline_stage_serializer.py

from rest_framework import serializers
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages
from apps.opportunities.models import PipelineStage, PipelineTemplate, OpportunityPipeline


class PipelineStageSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer pour les étapes de pipeline avec validation d'unicité
    """
    
    # Champs calculés (read-only)
    substages_count = serializers.IntegerField(read_only=True)
    is_current = serializers.BooleanField(read_only=True)
    can_be_deleted = serializers.BooleanField(read_only=True)
    progress_percentage = serializers.DecimalField(read_only=True, max_digits=5, decimal_places=2)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Champs pour les relations
    template_name = serializers.CharField(source='template.name', read_only=True)
    opportunity_title = serializers.CharField(source='opportunity_pipeline.opportunity.title', read_only=True)
    
    class Meta:
        model = PipelineStage
        fields = [
            'id',
            'template',
            'opportunity_pipeline',
            'template_name',
            'opportunity_title',
            'name',
            'description',
            'order',
            'status',
            'status_display',
            'is_active',
            'started_at',
            'completed_at',
            'estimated_duration',
            'substages_count',
            'is_current',
            'can_be_deleted',
            'progress_percentage',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'template_name',
            'opportunity_title',
            'status_display',
            'substages_count',
            'is_current',
            'can_be_deleted',
            'progress_percentage',
            'created_at',
            'updated_at'
        ]
    
    def get_substages_count(self, obj):
        """Nombre de sous-étapes actives dans cette étape"""
        return obj.substages.filter(is_active=True).count()
    
    def get_is_current(self, obj):
        """Vérifie si cette étape est l'étape courante du pipeline"""
        if obj.opportunity_pipeline:
            return obj.opportunity_pipeline.current_stage_id == obj.id
        return False
    
    def get_can_be_deleted(self, obj):
        """Vérifie si l'étape peut être supprimée"""
        # Ne peut pas être supprimée si elle a des sous-étapes actives
        if obj.substages.filter(is_active=True).exists():
            return False
        
        # Ne peut pas être supprimée si c'est l'étape courante
        if self.get_is_current(obj):
            return False
        
        return True
    
    def get_progress_percentage(self, obj):
        """Calcule le pourcentage de progression de l'étape"""
        if obj.status == PipelineStage.StageStatus.COMPLETED:
            return 100.0
        elif obj.status == PipelineStage.StageStatus.ACTIVE:
            # Calculer basé sur les sous-étapes
            substages = obj.substages.filter(is_active=True)
            if substages.exists():
                completed_count = substages.filter(status='COMPLETED').count()
                return round((completed_count / substages.count()) * 100, 2)
            return 0.0
        else:
            return 0.0
    
    def validate_name(self, value):
        """Validation de l'unicité du nom dans le contexte"""
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
                "Stage name must be at least 2 characters long",
                field_name="name"
            )
        
        if len(value) > 200:
            raise StandardizedValidationError(
                "Stage name cannot exceed 200 characters",
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
        return value
    
    def validate_template(self, value):
        """Validation du template"""
        if value:
            client_id = self._get_client_id_from_context()
            if str(value.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED,
                    field_name="template"
                )
        return value
    
    def validate_opportunity_pipeline(self, value):
        """Validation du pipeline d'opportunité"""
        if value:
            client_id = self._get_client_id_from_context()
            if str(value.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED,
                    field_name="opportunity_pipeline"
                )
        return value
    
    def validate(self, data):
        """Validation générale des données"""
        data = super().validate(data)
        
        # Validation XOR : soit template, soit opportunity_pipeline
        template = data.get('template', getattr(self.instance, 'template', None))
        opportunity_pipeline = data.get('opportunity_pipeline', getattr(self.instance, 'opportunity_pipeline', None))
        
        if not template and not opportunity_pipeline:
            raise StandardizedValidationError(
                OpportunityErrorMessages.STAGE_NOT_FOUND,
                field_name="template"
            )
        
        if template and opportunity_pipeline:
            raise StandardizedValidationError(
                "A stage cannot belong to both a template and an opportunity pipeline",
                field_name="template"
            )
        
        # Validation de l'unicité du nom dans le contexte
        name = data.get('name')
        if name:
            if template:
                # Vérifier l'unicité dans le template
                self.validate_client_scoped_uniqueness(
                    data={'template': template.id, 'name': name},
                    unique_fields=['template', 'name'],
                    model_class=PipelineStage,
                    error_message=OpportunityErrorMessages.STAGE_NAME_DUPLICATE.format(stage_name=name)
                )
            elif opportunity_pipeline:
                # Vérifier l'unicité dans le pipeline d'opportunité
                self.validate_client_scoped_uniqueness(
                    data={'opportunity_pipeline': opportunity_pipeline.id, 'name': name},
                    unique_fields=['opportunity_pipeline', 'name'],
                    model_class=PipelineStage,
                    error_message=OpportunityErrorMessages.STAGE_NAME_DUPLICATE.format(stage_name=name)
                )
        
        
        # Validation des transitions d'état
        if self.instance:
            current_status = self.instance.status
            new_status = data.get('status', current_status)
            
            # Vérifier les transitions autorisées
            if current_status != new_status:
                self._validate_status_transition(current_status, new_status)
        
        return data
    
    def _validate_status_transition(self, current_status, new_status):
        """Valide les transitions d'état autorisées"""
        # Règles de transition
        allowed_transitions = {
            PipelineStage.StageStatus.ACTIVE: [
                PipelineStage.StageStatus.COMPLETED,
                PipelineStage.StageStatus.BLOCKED,
                PipelineStage.StageStatus.SKIPPED
            ],
            PipelineStage.StageStatus.BLOCKED: [
                PipelineStage.StageStatus.ACTIVE,
                PipelineStage.StageStatus.SKIPPED
            ],
            PipelineStage.StageStatus.COMPLETED: [
                PipelineStage.StageStatus.ACTIVE  # Permettre la réouverture
            ],
            PipelineStage.StageStatus.SKIPPED: [
                PipelineStage.StageStatus.ACTIVE
            ]
        }
        
        if new_status not in allowed_transitions.get(current_status, []):
            raise StandardizedValidationError(
                OpportunityErrorMessages.STAGE_INVALID_TRANSITION.format(
                    from_stage=current_status,
                    to_stage=new_status
                ),
                field_name="status"
            )
    
    def create(self, validated_data):
        """Création d'une nouvelle étape"""
        try:
            # Ajouter le client_id automatiquement
            validated_data['client_id'] = self._get_client_id_from_context()
            
            # Créer l'étape
            stage = PipelineStage.objects.create(**validated_data)
            
            return stage
            
        except Exception as e:
            raise StandardizedValidationError(
                f"Stage creation failed: {str(e)}"
            )
    
    def update(self, instance, validated_data):
        """Mise à jour d'une étape existante"""
        try:
            # Vérifier les permissions
            client_id = self._get_client_id_from_context()
            if str(instance.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED
                )
            
            # Vérifier si l'étape peut être modifiée
            if instance.substages.filter(is_active=True).exists():
                # Certaines modifications sont interdites si l'étape a des sous-étapes
                restricted_fields = ['template', 'opportunity_pipeline']
                for field in restricted_fields:
                    if field in validated_data:
                        raise StandardizedValidationError(
                            OpportunityErrorMessages.STAGE_HAS_DEPENDENCIES.format(stage_name=instance.name),
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
                f"Stage update failed: {str(e)}"
            )
    
    def to_representation(self, instance):
        """Enrichir la représentation avec des données calculées"""
        representation = super().to_representation(instance)
        
        # Ajouter les champs calculés
        representation['substages_count'] = self.get_substages_count(instance)
        representation['is_current'] = self.get_is_current(instance)
        representation['can_be_deleted'] = self.get_can_be_deleted(instance)
        representation['progress_percentage'] = self.get_progress_percentage(instance)
        
        return representation