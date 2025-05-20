# apps/campaign/serializers/campaign_objective_serializer.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.campaign.models.campaign_objective import CampaignObjective
from apps.campaign.models.campaign import Campaign

class CampaignObjectiveSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Serializer for CampaignObjective model"""
    
    # Fields for write operations
    name = serializers.CharField(
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Objective Name'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Objective Name')
        }
    )
    
    campaign_id = serializers.PrimaryKeyRelatedField(
        queryset=Campaign.objects.all(),
        source='campaign',
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign'),
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND
        }
    )
    
    # Additional fields for read operations
    objective_type_display = serializers.SerializerMethodField(read_only=True)
    progress_percentage = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = CampaignObjective
        fields = [
            'id', 'campaign_id', 'name', 'description',
            'objective_type', 'objective_type_display', 'target_value',
            'current_value', 'unit', 'is_primary', 'progress_percentage',
            'last_updated', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_updated']
    
    def get_objective_type_display(self, obj):
        """Get the display name for objective type"""
        return obj.get_objective_type_display()
    
    def get_progress_percentage(self, obj):
        """Get the calculated progress percentage"""
        return obj.progress_percentage()
    
    def validate(self, data):
        """Complete validation of CampaignObjective data"""
        try:
            # Get client_id for validations
            client_id = self._get_client_id_from_context()
            
            # Validate client scope for campaign
            if 'campaign' in data:
                campaign = data['campaign']
                
                # Validate client ID first (basic security)
                self.validate_client_id(campaign)
                
                # Validate that the user owns the campaign or has permissions
                request = self.context.get('request')
                if request and hasattr(request, 'user'):
                    current_user = request.user
                    
                    # Check if user is the campaign owner
                    if campaign.owner.id != current_user.id:
                        # Check permissions logic here
                        raise StandardizedValidationError(
                            CoreErrorMessages.PERMISSION_DENIED
                        )
            
            # Validate target_value is positive
            if 'target_value' in data and data['target_value'] <= 0:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="Target Value")
                )
            
            # Validate current_value is not negative
            if 'current_value' in data and data['current_value'] < 0:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="Current Value")
                )
            
            # Validate objective_type
            if 'objective_type' in data:
                valid_types = [choice[0] for choice in CampaignObjective.ObjectiveType.choices]
                if data['objective_type'] not in valid_types:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(field="Objective Type")
                    )
            
            return super().validate(data)
            
        except serializers.ValidationError as e:
            raise StandardizedValidationError(e.detail)
    
    def create(self, validated_data):
        """Create a new CampaignObjective instance with client_id"""
        # Ensure client_id is included
        if 'client_id' not in validated_data and self.context.get('request'):
            validated_data['client_id'] = self.context['request'].auth.get('client_account')
        
        return super().create(validated_data)
