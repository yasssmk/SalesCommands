# backend/apps/opportunities/serializers/opportunity_pipeline_serializer.py

from rest_framework import serializers
from django.utils import timezone
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages
from apps.opportunities.models import OpportunityPipeline, Opportunity, PipelineTemplate, PipelineStage
from apps.opportunities.config.pipeline_stages import PipelineStagesConfig


class OpportunityPipelineSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer pour les pipelines d'opportunité avec validation d'unicité et de cohérence
    """
    
    # Champs calculés (read-only)
    progress_percentage = serializers.DecimalField(read_only=True, max_digits=5, decimal_places=2)
    estimated_completion_date = serializers.DateField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)
    active_substages_count = serializers.IntegerField(read_only=True)
    completed_substages_count = serializers.IntegerField(read_only=True)
    total_substages_count = serializers.IntegerField(read_only=True)
    can_be_deleted = serializers.BooleanField(read_only=True)
    
    # Champs pour les relations
    opportunity_title = serializers.CharField(source='opportunity.title', read_only=True)
    opportunity_status = serializers.CharField(source='opportunity.status', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    current_stage_name = serializers.CharField(source='current_stage.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Champs pour les contacts
    deal_owner_name = serializers.CharField(source='opportunity.deal_owner.get_full_name', read_only=True)
    primary_contact_name = serializers.CharField(source='opportunity.contact.get_full_name', read_only=True)
    
    class Meta:
        model = OpportunityPipeline
        fields = [
            'id',
            'opportunity',
            'opportunity_title',
            'opportunity_status',
            'template',
            'template_name',
            'current_stage',
            'current_stage_name',
            'status',
            'status_display',
            'started_at',
            'last_updated',
            'completed_at',
            'total_stages',
            'completed_stages',
            'progress_percentage',
            'estimated_completion_date',
            'is_overdue',
            'days_overdue',
            'active_substages_count',
            'completed_substages_count',
            'total_substages_count',
            'can_be_deleted',
            'deal_owner_name',
            'primary_contact_name',
            'is_customized',
            'customization_notes',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'opportunity_title',
            'opportunity_status',
            'template_name',
            'current_stage_name',
            'status_display',
            'last_updated',
            'completed_at',
            'total_stages',
            'completed_stages',
            'progress_percentage',
            'estimated_completion_date',
            'is_overdue',
            'days_overdue',
            'active_substages_count',
            'completed_substages_count',
            'total_substages_count',
            'can_be_deleted',
            'deal_owner_name',
            'primary_contact_name',
            'created_at',
            'updated_at'
        ]
    
    def get_progress_percentage(self, obj):
        """Calcule le pourcentage de progression du pipeline"""
        if obj.status == PipelineStagesConfig.PipelineStatus.COMPLETED:
            return 100.0
        elif obj.status == PipelineStagesConfig.PipelineStatus.ACTIVE:
            if obj.total_stages > 0:
                return round((obj.completed_stages / obj.total_stages) * 100, 2)
            return 0.0
        else:
            return 0.0
    
    def get_estimated_completion_date(self, obj):
        """Calcule la date de fin estimée basée sur les sous-étapes"""
        if obj.status == PipelineStagesConfig.PipelineStatus.COMPLETED:
            return obj.completed_at.date() if obj.completed_at else None
        
        # Calculer basé sur les sous-étapes restantes
        active_substages = obj.get_active_substages()
        if active_substages:
            max_expected_date = None
            for substage in active_substages:
                if substage.expected_completion_date:
                    if not max_expected_date or substage.expected_completion_date > max_expected_date:
                        max_expected_date = substage.expected_completion_date
            return max_expected_date
        
        return None
    
    def get_is_overdue(self, obj):
        """Vérifie si le pipeline est en retard"""
        estimated_date = self.get_estimated_completion_date(obj)
        if estimated_date and obj.status == PipelineStagesConfig.PipelineStatus.ACTIVE:
            return timezone.now().date() > estimated_date
        return False
    
    def get_days_overdue(self, obj):
        """Calcule le nombre de jours de retard"""
        if self.get_is_overdue(obj):
            estimated_date = self.get_estimated_completion_date(obj)
            if estimated_date:
                return (timezone.now().date() - estimated_date).days
        return 0
    
    def get_active_substages_count(self, obj):
        """Nombre de sous-étapes actives"""
        return sum(stage.substages.filter(
            is_active=True,
            status__in=[
                PipelineStagesConfig.SubStageStatus.NOT_STARTED,
                PipelineStagesConfig.SubStageStatus.IN_PROGRESS
            ]
        ).count() for stage in obj.stages.filter(is_active=True))
    
    def get_completed_substages_count(self, obj):
        """Nombre de sous-étapes terminées"""
        return sum(stage.substages.filter(
            is_active=True,
            status=PipelineStagesConfig.SubStageStatus.COMPLETED
        ).count() for stage in obj.stages.filter(is_active=True))
    
    def get_total_substages_count(self, obj):
        """Nombre total de sous-étapes"""
        return sum(stage.substages.filter(is_active=True).count() 
                  for stage in obj.stages.filter(is_active=True))
    
    def get_can_be_deleted(self, obj):
        """Vérifie si le pipeline peut être supprimé"""
        # Ne peut pas être supprimé s'il a des activités liées
        if obj.stages.filter(substages__activities__isnull=False).exists():
            return False
        
        # Ne peut pas être supprimé s'il est en cours depuis plus de 7 jours
        if obj.status == PipelineStagesConfig.PipelineStatus.ACTIVE:
            days_active = (timezone.now() - obj.started_at).days
            if days_active > 7:
                return False
        
        return True
    
    def validate_opportunity(self, value):
        """Validation de l'opportunité"""
        if value:
            client_id = self._get_client_id_from_context()
            if str(value.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED,
                    field_name="opportunity"
                )
            
            # Vérifier que l'opportunité n'a pas déjà un pipeline
            if not self.instance and hasattr(value, 'pipeline'):
                raise StandardizedValidationError(
                    OpportunityErrorMessages.PIPELINE_ALREADY_EXISTS,
                    field_name="opportunity"
                )
            
            # Vérifier que l'opportunité n'est pas fermée
            if value.status in [Opportunity.OpportunityStatus.WON, Opportunity.OpportunityStatus.LOST]:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.OPPORTUNITY_CLOSED,
                    field_name="opportunity"
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
            
            # Vérifier que le template est actif
            if not value.is_active:
                raise StandardizedValidationError(
                    "Cannot use inactive template",
                    field_name="template"
                )
        
        return value
    
    def validate_current_stage(self, value):
        """Validation de l'étape courante"""
        if value:
            client_id = self._get_client_id_from_context()
            if str(value.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED,
                    field_name="current_stage"
                )
            
            # Vérifier que l'étape appartient à ce pipeline
            if self.instance and value.opportunity_pipeline != self.instance:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.PIPELINE_INVALID_CURRENT_STAGE,
                    field_name="current_stage"
                )
        
        return value
    
    def validate(self, data):
        """Validation générale des données"""
        data = super().validate(data)
        
        # Vérifier la cohérence opportunity-template
        opportunity = data.get('opportunity', getattr(self.instance, 'opportunity', None))
        template = data.get('template', getattr(self.instance, 'template', None))
        
        if opportunity and template:
            # Vérifier que l'opportunité et le template appartiennent au même client
            if opportunity.client_id != template.client_id:
                raise StandardizedValidationError(
                    "Opportunity and template must belong to the same client",
                    field_name="template"
                )
        
        # Validation des transitions d'état
        if self.instance:
            current_status = self.instance.status
            new_status = data.get('status', current_status)
            
            if current_status != new_status:
                self._validate_status_transition(current_status, new_status)
        
        # Validation de l'unicité : une opportunité = un pipeline
        if opportunity and not self.instance:
            existing_pipeline = OpportunityPipeline.objects.filter(
                opportunity=opportunity,
                client_id=self._get_client_id_from_context()
            ).first()
            
            if existing_pipeline:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.PIPELINE_ALREADY_EXISTS,
                    field_name="opportunity"
                )
        
        return data
    
    def _validate_status_transition(self, current_status, new_status):
        """Valide les transitions d'état autorisées"""
        allowed_transitions = {
            PipelineStagesConfig.PipelineStatus.ACTIVE: [
                PipelineStagesConfig.PipelineStatus.COMPLETED,
                PipelineStagesConfig.PipelineStatus.PAUSED,
                PipelineStagesConfig.PipelineStatus.CANCELLED,
                PipelineStagesConfig.PipelineStatus.FAILED
            ],
            PipelineStagesConfig.PipelineStatus.PAUSED: [
                PipelineStagesConfig.PipelineStatus.ACTIVE,
                PipelineStagesConfig.PipelineStatus.CANCELLED,
                PipelineStagesConfig.PipelineStatus.FAILED
            ],
            PipelineStagesConfig.PipelineStatus.COMPLETED: [
                PipelineStagesConfig.PipelineStatus.ACTIVE  # Permettre la réouverture
            ],
            PipelineStagesConfig.PipelineStatus.CANCELLED: [
                PipelineStagesConfig.PipelineStatus.ACTIVE  # Permettre la réactivation
            ],
            PipelineStagesConfig.PipelineStatus.FAILED: [
                PipelineStagesConfig.PipelineStatus.ACTIVE  # Permettre la réactivation
            ]
        }
        
        if new_status not in allowed_transitions.get(current_status, []):
            raise StandardizedValidationError(
                OpportunityErrorMessages.PIPELINE_INVALID_STATE.format(current_state=current_status),
                field_name="status"
            )
    
    def create(self, validated_data):
        """Création d'un nouveau pipeline"""
        try:
            # Ajouter le client_id automatiquement
            validated_data['client_id'] = self._get_client_id_from_context()
            
            # Utiliser la méthode de classe pour créer à partir du template
            opportunity = validated_data['opportunity']
            template = validated_data['template']
            
            # Créer le pipeline via la méthode du modèle
            pipeline = OpportunityPipeline.create_from_template(
                opportunity=opportunity,
                template=template,
                user=self.context.get('request').user if 'request' in self.context else None
            )
            
            # Appliquer les autres champs si fournis
            for attr, value in validated_data.items():
                if attr not in ['opportunity', 'template', 'client_id']:
                    setattr(pipeline, attr, value)
            
            pipeline.save()
            return pipeline
            
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.PIPELINE_CREATION_FAILED.format(reason=str(e))
            )
    
    def update(self, instance, validated_data):
        """Mise à jour d'un pipeline existant"""
        try:
            # Vérifier les permissions
            client_id = self._get_client_id_from_context()
            if str(instance.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED
                )
            
            # Vérifier si le pipeline peut être modifié
            if instance.status == PipelineStagesConfig.PipelineStatus.COMPLETED:
                # Certaines modifications sont interdites pour les pipelines terminés
                restricted_fields = ['opportunity', 'template']
                for field in restricted_fields:
                    if field in validated_data:
                        raise StandardizedValidationError(
                            f"Cannot modify {field} on completed pipeline",
                            field_name=field
                        )
            
            # Marquer comme personnalisé si modification des étapes
            if any(field in validated_data for field in ['current_stage', 'customization_notes']):
                instance.mark_as_customized()
            
            # Mettre à jour l'instance
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            instance.save()
            return instance
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.PIPELINE_CUSTOMIZATION_FAILED.format(reason=str(e))
            )
    
    def to_representation(self, instance):
        """Enrichir la représentation avec des données calculées"""
        representation = super().to_representation(instance)
        
        # Ajouter les champs calculés
        representation['progress_percentage'] = self.get_progress_percentage(instance)
        representation['estimated_completion_date'] = self.get_estimated_completion_date(instance)
        representation['is_overdue'] = self.get_is_overdue(instance)
        representation['days_overdue'] = self.get_days_overdue(instance)
        representation['active_substages_count'] = self.get_active_substages_count(instance)
        representation['completed_substages_count'] = self.get_completed_substages_count(instance)
        representation['total_substages_count'] = self.get_total_substages_count(instance)
        representation['can_be_deleted'] = self.get_can_be_deleted(instance)
        
        return representation