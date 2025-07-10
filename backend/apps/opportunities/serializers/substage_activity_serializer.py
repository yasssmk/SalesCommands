# backend/apps/opportunities/serializers/substage_activity_serializer.py

from rest_framework import serializers
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages
from apps.opportunities.models import SubStageActivity, PipelineSubStage
from apps.activities.models import Activity
from apps.opportunities.config.pipeline_stages import PipelineStagesConfig


class SubStageActivitySerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer pour les liaisons entre sous-étapes et activités
    """
    
    # Champs calculés (read-only)
    is_trigger_activity = serializers.BooleanField(read_only=True)
    activity_completed = serializers.BooleanField(read_only=True)
    activity_overdue = serializers.BooleanField(read_only=True)
    pipeline_impact_display = serializers.CharField(read_only=True)
    
    # Champs pour les relations
    substage_name = serializers.CharField(source='substage.name', read_only=True)
    substage_status = serializers.CharField(source='substage.status', read_only=True)
    activity_title = serializers.CharField(source='activity.title', read_only=True)
    activity_type = serializers.CharField(source='activity.activity_type', read_only=True)
    activity_status = serializers.CharField(source='activity.status', read_only=True)
    activity_scheduled_start = serializers.DateTimeField(source='activity.scheduled_start', read_only=True)
    activity_scheduled_end = serializers.DateTimeField(source='activity.scheduled_end', read_only=True)
    link_type_display = serializers.CharField(source='get_link_type_display', read_only=True)
    
    # Champs pour les propriétaires
    activity_owner_name = serializers.CharField(source='activity.owner.get_full_name', read_only=True)
    
    class Meta:
        model = SubStageActivity
        fields = [
            'id',
            'substage',
            'substage_name',
            'substage_status',
            'activity',
            'activity_title',
            'activity_type',
            'activity_status',
            'activity_scheduled_start',
            'activity_scheduled_end',
            'activity_owner_name',
            'link_type',
            'link_type_display',
            'pipeline_impact',
            'pipeline_impact_display',
            'is_trigger_activity',
            'activity_completed',
            'activity_overdue',
            'notes',
            'created_automatically',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'substage_name',
            'substage_status',
            'activity_title',
            'activity_type',
            'activity_status',
            'activity_scheduled_start',
            'activity_scheduled_end',
            'activity_owner_name',
            'link_type_display',
            'pipeline_impact_display',
            'is_trigger_activity',
            'activity_completed',
            'activity_overdue',
            'created_at',
            'updated_at'
        ]
    
    def get_is_trigger_activity(self, obj):
        """Vérifie si l'activité est un déclencheur"""
        return obj.link_type == PipelineStagesConfig.ActivityLinkType.TRIGGER_ACTIVITY
    
    def get_activity_completed(self, obj):
        """Vérifie si l'activité est terminée"""
        return obj.activity.status == Activity.Status.COMPLETED
    
    def get_activity_overdue(self, obj):
        """Vérifie si l'activité est en retard"""
        if obj.activity.scheduled_start and obj.activity.status != Activity.Status.COMPLETED:
            from django.utils import timezone
            return timezone.now() > obj.activity.scheduled_start
        return False
    
    def get_pipeline_impact_display(self, obj):
        """Affichage du type d'impact sur le pipeline"""
        impact_mapping = {
            'advance': 'Advances Pipeline',
            'block': 'Blocks Pipeline',
            'neutral': 'Neutral Impact'
        }
        return impact_mapping.get(obj.pipeline_impact, 'Unknown')
    
    def validate_substage(self, value):
        """Validation de la sous-étape"""
        if value:
            client_id = self._get_client_id_from_context()
            if str(value.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED,
                    field_name="substage"
                )
        return value
    
    def validate_activity(self, value):
        """Validation de l'activité"""
        if value:
            client_id = self._get_client_id_from_context()
            if str(value.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED,
                    field_name="activity"
                )
            
            # Vérifier que l'activité n'est pas déjà liée à une autre sous-étape
            if not self.instance:
                existing_link = SubStageActivity.objects.filter(
                    activity=value,
                    client_id=client_id
                ).first()
                
                if existing_link:
                    raise StandardizedValidationError(
                        f"Activity '{value.title}' is already linked to substage '{existing_link.substage.name}'",
                        field_name="activity"
                    )
        
        return value
    
    def validate_link_type(self, value):
        """Validation du type de liaison"""
        if value not in [choice[0] for choice in PipelineStagesConfig.ActivityLinkType.choices]:
            raise StandardizedValidationError(
                f"Invalid link type: {value}",
                field_name="link_type"
            )
        return value
    
    def validate_pipeline_impact(self, value):
        """Validation de l'impact sur le pipeline"""
        if value and value not in ['advance', 'block', 'neutral']:
            raise StandardizedValidationError(
                f"Invalid pipeline impact: {value}",
                field_name="pipeline_impact"
            )
        return value
    
    def validate(self, data):
        """Validation générale des données"""
        data = super().validate(data)
        
        # Récupérer les valeurs
        substage = data.get('substage', getattr(self.instance, 'substage', None))
        activity = data.get('activity', getattr(self.instance, 'activity', None))
        link_type = data.get('link_type', getattr(self.instance, 'link_type', None))
        pipeline_impact = data.get('pipeline_impact', getattr(self.instance, 'pipeline_impact', None))
        
        # Vérifier la cohérence entre substage et activity
        if substage and activity:
            # Vérifier que l'activité appartient à la même opportunité
            if hasattr(substage.stage, 'opportunity_pipeline'):
                opportunity = substage.stage.opportunity_pipeline.opportunity
                
                # Vérifier que l'activité est liée à cette opportunité
                if hasattr(activity, 'opportunity') and activity.opportunity != opportunity:
                    raise StandardizedValidationError(
                        OpportunityErrorMessages.ACTIVITY_NOT_IN_PIPELINE,
                        field_name="activity"
                    )
                
                # Vérifier que l'activité est liée au contact principal de l'opportunité
                if hasattr(activity, 'contact') and activity.contact != opportunity.contact:
                    # Permettre si le contact appartient au même compte
                    if not (hasattr(activity.contact, 'account') and 
                           activity.contact.account == opportunity.contact.account):
                        raise StandardizedValidationError(
                            "Activity contact must belong to the same account as the opportunity",
                            field_name="activity"
                        )
        
        # Validation des règles métier selon le type de liaison
        if link_type == PipelineStagesConfig.ActivityLinkType.TRIGGER_ACTIVITY:
            # Les activités déclencheurs doivent avoir un impact sur le pipeline
            if not pipeline_impact or pipeline_impact == 'neutral':
                raise StandardizedValidationError(
                    "Trigger activities must have a non-neutral pipeline impact",
                    field_name="pipeline_impact"
                )
        
        if link_type == PipelineStagesConfig.ActivityLinkType.FUTURE_ACTIVITY:
            # Les activités futures doivent être planifiées
            if activity and not activity.scheduled_start:
                raise StandardizedValidationError(
                    "Future activities must have a scheduled start date",
                    field_name="activity"
                )
        
        # Validation de la cohérence temporelle
        if substage and activity:
            if link_type == PipelineStagesConfig.ActivityLinkType.PAST_ACTIVITY:
                # Les activités passées doivent être terminées
                if activity.status != Activity.Status.COMPLETED:
                    raise StandardizedValidationError(
                        "Past activities must be completed",
                        field_name="link_type"
                    )
            
            elif link_type == PipelineStagesConfig.ActivityLinkType.FUTURE_ACTIVITY:
                # Les activités futures ne doivent pas être terminées
                if activity.status == Activity.Status.COMPLETED:
                    raise StandardizedValidationError(
                        "Future activities cannot be completed",
                        field_name="link_type"
                    )
        
        return data
    
    def create(self, validated_data):
        """Création d'une nouvelle liaison"""
        try:
            # Ajouter le client_id automatiquement
            validated_data['client_id'] = self._get_client_id_from_context()
            
            # Créer la liaison
            link = SubStageActivity.objects.create(**validated_data)
            
            # Appliquer l'impact sur le pipeline si nécessaire
            if link.pipeline_impact == 'advance':
                self._advance_pipeline_if_needed(link)
            elif link.pipeline_impact == 'block':
                self._block_pipeline_if_needed(link)
            
            return link
            
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.ACTIVITY_LINK_FAILED.format(reason=str(e))
            )
    
    def update(self, instance, validated_data):
        """Mise à jour d'une liaison existante"""
        try:
            # Vérifier les permissions
            client_id = self._get_client_id_from_context()
            if str(instance.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED
                )
            
            # Sauvegarder l'ancien impact pour comparaison
            old_impact = instance.pipeline_impact
            
            # Mettre à jour l'instance
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            instance.save()
            
            # Appliquer les changements d'impact si nécessaire
            new_impact = instance.pipeline_impact
            if old_impact != new_impact:
                if new_impact == 'advance':
                    self._advance_pipeline_if_needed(instance)
                elif new_impact == 'block':
                    self._block_pipeline_if_needed(instance)
                elif old_impact in ['advance', 'block'] and new_impact == 'neutral':
                    self._neutralize_pipeline_impact(instance)
            
            return instance
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                f"SubStage activity link update failed: {str(e)}"
            )
    
    def _advance_pipeline_if_needed(self, link):
        """Faire avancer le pipeline si l'activité est terminée"""
        if link.activity.status == Activity.Status.COMPLETED:
            # Logique pour faire avancer la sous-étape
            substage = link.substage
            if substage.status == PipelineStagesConfig.SubStageStatus.NOT_STARTED:
                substage.status = PipelineStagesConfig.SubStageStatus.IN_PROGRESS
                substage.save()
    
    def _block_pipeline_if_needed(self, link):
        """Bloquer le pipeline si l'activité pose problème"""
        if link.activity.status == Activity.Status.CANCELLED:
            # Logique pour bloquer la sous-étape
            substage = link.substage
            if substage.status == PipelineStagesConfig.SubStageStatus.IN_PROGRESS:
                substage.status = PipelineStagesConfig.SubStageStatus.BLOCKED
                substage.save()
    
    def _neutralize_pipeline_impact(self, link):
        """Neutraliser l'impact sur le pipeline"""
        # Logique pour annuler l'impact précédent
        pass
    
    def to_representation(self, instance):
        """Enrichir la représentation avec des données calculées"""
        representation = super().to_representation(instance)
        
        # Ajouter les champs calculés
        representation['is_trigger_activity'] = self.get_is_trigger_activity(instance)
        representation['activity_completed'] = self.get_activity_completed(instance)
        representation['activity_overdue'] = self.get_activity_overdue(instance)
        representation['pipeline_impact_display'] = self.get_pipeline_impact_display(instance)
        
        return representation