# backend/apps/opportunities/serializers/substage_activity_serializer.py

from rest_framework import serializers
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages, ActivityErrorMessages
from apps.opportunities.models import SubStageActivity, PipelineSubStage
from apps.activities.models import Activity


class SubStageActivitySerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer simplifié pour les liaisons entre sous-étapes et activités
    """
    
    # Champs pour l'affichage des relations (read-only)
    substage_name = serializers.CharField(source='substage.name', read_only=True)
    substage_status = serializers.CharField(source='substage.status', read_only=True)
    
    activity_title = serializers.CharField(source='activity.title', read_only=True)
    activity_type = serializers.CharField(source='activity.activity_type', read_only=True)
    activity_status = serializers.CharField(source='activity.status', read_only=True)
    activity_scheduled_start = serializers.DateTimeField(source='activity.scheduled_start', read_only=True)
    activity_scheduled_end = serializers.DateTimeField(source='activity.scheduled_end', read_only=True)
    activity_owner_name = serializers.CharField(source='activity.owner.get_full_name', read_only=True)
    
    # Propriété calculée pour la timeline
    timeline_position = serializers.CharField(read_only=True)
    
    # Informations sur l'opportunity pour validation
    opportunity_id = serializers.IntegerField(source='opportunity.id', read_only=True)
    
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
            'timeline_position',
            'opportunity_id',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        """
        Validation globale : vérifier la cohérence opportunity uniquement
        La contrainte d'unicité (1 activité = 1 substage) est gérée automatiquement 
        par ClientScopeManager via la contrainte DB unique_substage_activity_per_client
        """
        substage = attrs.get('substage')
        activity = attrs.get('activity')
        
        if substage and activity:
            # Récupérer l'opportunity du substage
            substage_opportunity = substage.stage.opportunity_pipeline.opportunity
            
            # Vérifier que l'activité appartient à la même opportunity
            if activity.opportunity != substage_opportunity:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.ACTIVITY_OPPORTUNITY_MISMATCH
                )
        
        return attrs

    def create(self, validated_data):
        """
        Création avec gestion d'erreurs
        """
        try:
            validated_data['client_id'] = self.get_client_id()
            return super().create(validated_data)
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to create substage-activity link: {str(e)}"
                )
            )

    def update(self, instance, validated_data):
        """
        Mise à jour avec gestion d'erreurs
        """
        try:
            return super().update(instance, validated_data)
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to update substage-activity link: {str(e)}"
                )
            )


class SubStageActivityCreateSerializer(serializers.Serializer):
    """
    Serializer dédié pour créer une liaison avec une activité existante
    """
    activity_id = serializers.IntegerField()
    
    def validate_activity_id(self, value):
        """Valider que l'activité existe et appartient au bon client"""
        try:
            activity = Activity.objects.get(
                id=value, 
                client_id=self.context.get('client_id')
            )
            return activity
        except Activity.DoesNotExist:
            raise StandardizedValidationError(
                ActivityErrorMessages.ACTIVITY_NOT_FOUND
            )


class SubStageActivityWithNewActivitySerializer(serializers.Serializer):
    """
    Serializer pour créer une activité ET la lier au substage en une seule opération
    """
    # Champs pour créer l'activité
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    activity_type = serializers.CharField(max_length=50)
    scheduled_start = serializers.DateTimeField(required=False)
    scheduled_end = serializers.DateTimeField(required=False)
    owner_id = serializers.IntegerField(required=False)
    
    def validate(self, attrs):
        """Validation des dates si fournies"""
        scheduled_start = attrs.get('scheduled_start')
        scheduled_end = attrs.get('scheduled_end')
        
        if scheduled_start and scheduled_end and scheduled_start >= scheduled_end:
            raise StandardizedValidationError(
                OpportunityErrorMessages.SUBSTAGE_DATE_INVALID
            )
        
        return attrs