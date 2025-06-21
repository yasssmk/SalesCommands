# apps/campaign/serializers/campaign_objective_serializer.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.campaign.models.campaign_objective import CampaignObjective
from apps.campaign.models.campaign import Campaign
from apps.campaign.config.settings import CONFIG


class CampaignObjectiveSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Simplified serializer for CampaignObjective (MVP version)"""
    
    # Write fields
    campaign_id = serializers.PrimaryKeyRelatedField(
        queryset=Campaign.objects.all(),
        source='campaign',
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign'),
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Campaign ID')
        }
    )
    
    # Read-only calculated fields
    current_value = serializers.SerializerMethodField(read_only=True)
    progress_percentage = serializers.SerializerMethodField(read_only=True)
    objective_type_display = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = CampaignObjective
        fields = CONFIG.serializers.objective_fields
        read_only_fields = CONFIG.serializers.objective_read_only_fields
    
    def get_current_value(self, obj):
        """Get current value from campaign tracking"""
        try:
            return obj.get_current_value()
        except Exception:
            return 0
    
    def get_progress_percentage(self, obj):
        """Get progress percentage"""
        try:
            return round(obj.get_progress_percentage(), 1)
        except Exception:
            return 0.0
    
    def get_objective_type_display(self, obj):
        """Get display name for objective type"""
        try:
            return obj.get_objective_type_display()
        except Exception:
            return obj.objective_type
    
    def validate_target_value(self, value):
        """Simple validation: target value must be positive"""
        if value <= 0:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Target Value (must be greater than 0)")
            )
        return value
    
    def validate(self, data):
        """Basic validation for MVP"""
        try:
            # Validate campaign access
            campaign = data.get('campaign')
            if campaign:
                self.validate_client_id(campaign)
            
            return super().validate(data)
            
        except StandardizedValidationError:
            raise
        except serializers.ValidationError as e:
            # Convert DRF validation errors to standardized format
            if isinstance(e.detail, dict):
                error_messages = []
                for field, errors in e.detail.items():
                    if isinstance(errors, list):
                        error_messages.extend([str(error) for error in errors])
                    else:
                        error_messages.append(str(errors))
                raise StandardizedValidationError('; '.join(error_messages))
            else:
                raise StandardizedValidationError(str(e.detail))
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Objective validation failed")
            )