# backend/apps/opportunities/serializers/substage_activity_serializer.py

from rest_framework import serializers
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages
from apps.opportunities.models import SubStageActivity, PipelineSubStage
from apps.activities.models import Activity


class SubStageActivitySerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer MVP avec validation centralisée pour les liaisons Activity ↔ SubStage.
    
    RESPONSABILITÉ UNIQUE :
    - validate() : SEUL endroit pour valider Activity.opportunity = SubStage.opportunity
    - Utilise ActivitySubStageService.get_substage_opportunity()
    - Gestion d'erreurs standardisée
    - Liaison automatique Activity.pipeline_substage
    """
    
    # ===== CHAMPS DISPLAY (READ-ONLY) =====

    substage = serializers.PrimaryKeyRelatedField(
        queryset=PipelineSubStage.objects.all(),
        write_only=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Substage'),
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Substage ID must be a valid integer')
         }
    )

    activity = serializers.PrimaryKeyRelatedField(
        queryset=Activity.objects.all(),
        write_only=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Activity'),
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Activity ID must be a valid integer')
        }
    )
    
    substage_name = serializers.CharField(source='substage.name', read_only=True)
    substage_status = serializers.CharField(source='substage.status', read_only=True)
    substage_type = serializers.CharField(source='substage.get_substage_type_display', read_only=True)
    
    activity_title = serializers.CharField(source='activity.title', read_only=True)
    activity_type = serializers.CharField(source='activity.activity_type', read_only=True)
    activity_type_display = serializers.CharField(source='activity.get_activity_type_display', read_only=True)
    activity_status = serializers.CharField(source='activity.status', read_only=True)
    activity_status_display = serializers.CharField(source='activity.get_status_display', read_only=True)
    activity_scheduled_start = serializers.DateTimeField(source='activity.scheduled_start', read_only=True)
    activity_scheduled_end = serializers.DateTimeField(source='activity.scheduled_end', read_only=True)
    activity_completed_at = serializers.DateTimeField(source='activity.completed_at', read_only=True)
    activity_owner_name = serializers.CharField(source='activity.owner.get_full_name', read_only=True)
    activity_outcome_notes = serializers.CharField(source='activity.outcome_notes', read_only=True)
    
    # Informations stage et opportunity
    stage_name = serializers.CharField(source='substage.stage.name', read_only=True)
    opportunity_id = serializers.SerializerMethodField(read_only=True)
    opportunity_title = serializers.SerializerMethodField(read_only=True)
    
    # Informations contextuelles
    has_context = serializers.SerializerMethodField(read_only=True)
    context_summary = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = SubStageActivity
        fields = [
            'id',
            'substage',
            'substage_name', 
            'substage_status',
            'substage_type',
            'activity',
            'activity_title',
            'activity_type',
            'activity_type_display',
            'activity_status',
            'activity_status_display',
            'activity_scheduled_start',
            'activity_scheduled_end',
            'activity_completed_at',
            'activity_owner_name',
            'activity_outcome_notes',
            'stage_name',
            'opportunity_id',
            'opportunity_title',
            'has_context',
            'context_summary',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    # ===== VALIDATION CENTRALISÉE - SEUL ENDROIT =====

    def validate(self, attrs):

        substage = attrs.get('substage')
        activity = attrs.get('activity')

        client_id = self._get_client_id_from_context()
            
        if str(substage.client_id) != str(client_id):
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        
        if str(activity.client_id) != str(client_id):
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        
        self.validate_client_scoped_uniqueness(
            data=attrs,
            unique_fields=['substage'],
            error_message=OpportunityErrorMessages.UNIQUE_CONSTRAINT_ACTIVITY_SUBSTAGE,
        )
    
        if substage and activity:
            # Import du service pour utiliser le helper centralisé
            from ..services.activity_substage_service import ActivitySubStageService
            
            # Récupérer l'opportunity du substage via le service
            substage_opportunity = ActivitySubStageService.get_substage_opportunity(substage)
            
            # Validation 1 : SubStage doit avoir une opportunity
            if not substage_opportunity:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.SUBSTAGE_OPPORTUNITY_NOT_FOUND
                )
            
            # Validation 2 : Activity.opportunity = SubStage.opportunity
            if activity.opportunity and activity.opportunity != substage_opportunity:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.ACTIVITY_OPPORTUNITY_MISMATCH
                )
            
            # Validation 3 : Une activité ne peut être liée qu'à un seul substage
            if activity.pipeline_substage and activity.pipeline_substage != substage:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.ACTIVITY_ALREADY_LINKED
                )
        
        return attrs

        
    def validate_substage(self, value):
        """Validation du substage avec client scope"""
        client_id = self._get_client_id_from_context()
        
        # ✅ NOUVEAU: Gérer le cas où value est un ID (pour compatibilité) ou une instance
        if isinstance(value, int):
            # Si c'est un ID, récupérer l'instance avec validation d'existence
            try:
                substage = PipelineSubStage.objects.get(id=value, client_id=client_id)
            except PipelineSubStage.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
        else:
            # Si c'est déjà une instance, valider juste le client_id
            substage = value
            if str(substage.client_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        
        return substage

    def validate_activity(self, value):
        """Validation de l'activity avec client scope"""
        client_id = self._get_client_id_from_context()
        
        # ✅ NOUVEAU: Gérer le cas où value est un ID (pour compatibilité) ou une instance
        if isinstance(value, int):
            # Si c'est un ID, récupérer l'instance avec validation d'existence
            try:
                activity = Activity.objects.get(id=value, client_id=client_id)
            except Activity.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
        else:
            # Si c'est déjà une instance, valider juste le client_id
            activity = value
            if str(activity.client_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        
        return activity

    # ===== CRÉATION AVEC LIAISON AUTOMATIQUE =====

    def create(self, validated_data):
        """
        Création avec liaison automatique Activity.pipeline_substage
        et auto-set opportunity si nécessaire
        """
        try:
            # Ajouter client_id
            validated_data['client_id'] = self._get_client_id_from_context()
            validated_data = self._enrich_validated_data(validated_data, is_update=False)
            
            # Récupérer les objets
            activity = validated_data['activity']
            substage = validated_data['substage']
            
            # Auto-set opportunity si elle n'existe pas (cohérent avec le modèle)
            if not activity.opportunity:
                from ..services.activity_substage_service import ActivitySubStageService
                substage_opportunity = ActivitySubStageService.get_substage_opportunity(substage)
                if substage_opportunity:
                    activity.opportunity = substage_opportunity
                    activity.save(update_fields=['opportunity'])
            
            # Créer la liaison SubStageActivity
            substage_activity = super().create(validated_data)
            
            # ✅ LIAISON AUTOMATIQUE : Mettre à jour Activity.pipeline_substage
            activity.pipeline_substage = substage
            activity.set_substage_context(substage)
            activity.save(update_fields=['pipeline_substage', 'substage_name', 'objectives', 'context_info', 'call_to_action'])
            
            return substage_activity
            
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.ACTIVITY_LINK_FAILED.format(reason=str(e))
            )

    def update(self, instance, validated_data):
        """
        Mise à jour avec gestion des liaisons
        """
        try:
            # ✅ NOUVEAU: Enrichir avec updated_by, updated_at
            validated_data = self._enrich_validated_data(validated_data, is_update=True)
            
            # Si on change le substage, mettre à jour la liaison directe et le contexte
            if 'substage' in validated_data:
                new_substage = validated_data['substage']
                activity = instance.activity
                
                # Mettre à jour la liaison directe
                activity.pipeline_substage = new_substage
                
                # ✅ NOUVEAU: Mettre à jour le contexte avec le nouveau substage
                activity.set_substage_context(new_substage) 
                
                # Sauvegarder les changements sur l'activité
                activity.save(update_fields=['pipeline_substage', 'substage_name', 'objectives', 'context_info', 'call_to_action'])
            
            return super().update(instance, validated_data)
            
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.ACTIVITY_LINK_FAILED.format(reason=str(e))
            )
        
    # ===== MÉTHODES HELPER POUR ENRICHISSEMENT =====

    def get_opportunity_id(self, obj):
        """Récupère l'ID de l'opportunity via le service centralisé"""
        try:
            from ..services.activity_substage_service import ActivitySubStageService
            opportunity = ActivitySubStageService.get_substage_opportunity(obj.substage)
            return opportunity.id if opportunity else None
        except:
            return None

    def get_opportunity_title(self, obj):
        """Récupère le titre de l'opportunity via le service centralisé"""
        try:
            from ..services.activity_substage_service import ActivitySubStageService
            opportunity = ActivitySubStageService.get_substage_opportunity(obj.substage)
            return opportunity.title if opportunity else None
        except:
            return None

    def get_has_context(self, obj):
        """Vérifie si l'activité a du contexte enrichi"""
        try:
            activity = obj.activity
            return bool(activity.context_info and activity.substage_name)
        except:
            return False

    def get_context_summary(self, obj):
        """Récupère le résumé de contexte via la méthode du modèle Activity"""
        try:
            return obj.activity.get_context_summary()
        except:
            return {
                'has_substage': False,
                'substage_name': "",
                'objectives': "",
                'call_to_action': "",
                'stakeholder_count': 0
            }

    def to_representation(self, instance):
        """Enrichir la représentation avec des infos du service"""
        data = super().to_representation(instance)
        
        # Ajouter des informations supplémentaires si nécessaire
        try:
            from ..services.activity_substage_service import ActivitySubStageService
            substage_info = ActivitySubStageService.get_activity_substage_info(
                activity_id=instance.activity.id,
                client_id=instance.client_id
            )
            if substage_info:
                # Enrichir avec des infos détaillées du service si nécessaire
                data['substage_details'] = {
                    'stage_id': substage_info.get('stage_id'),
                    'stage_name': substage_info.get('stage_name'),
                    'opportunity_id': substage_info.get('opportunity_id')
                }
        except:
            pass  # Fail silently pour l'affichage
        
        return data


# ===== SERIALIZER SIMPLIFIÉ POUR CRÉATION =====

class SubStageActivityCreateSerializer(serializers.Serializer):
    """
    Serializer simplifié pour créer une liaison Activity ↔ SubStage
    via ActivitySubStageService.link_existing_activity()
    
    Utilisé par les endpoints qui veulent juste lier une activité existante.
    """
    activity_id = serializers.IntegerField(required=True)
    
    def validate_activity_id(self, value):
        """Valider que l'activité existe et appartient au client"""
        client_id = self.context.get('client_id')
        
        if not client_id:
            raise StandardizedValidationError(
                CoreErrorMessages.CLIENT_ID_REQUIRED
            )
        
        try:
            Activity.objects.get(id=value, client_id=client_id)
            return value
        except Activity.DoesNotExist:
            raise StandardizedValidationError(
                CoreErrorMessages.OBJECT_NOT_FOUND
            )


