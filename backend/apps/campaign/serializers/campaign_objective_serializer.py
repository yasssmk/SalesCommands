# apps/campaign/serializers/campaign_objective_serializer.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.campaign.models.campaign_objective import CampaignObjective
from apps.campaign.models.campaign import Campaign

class CampaignObjectiveSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Serializer for CampaignObjective model with standardized validation"""
    
    # Fields for write operations
    name = serializers.CharField(
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Objective Name'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Objective Name'),
            'blank': CoreErrorMessages.REQUIRED_FIELD.format(field='Objective Name'),
            'max_length': CoreErrorMessages.INVALID_FIELD.format(field='Objective Name (maximum 100 characters)')
        }
    )
    
    campaign_id = serializers.PrimaryKeyRelatedField(
        queryset=Campaign.objects.all(),
        source='campaign',
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign'),
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Campaign ID')
        }
    )
    
    target_value = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Target Value'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Target Value (must be a valid number)'),
            'max_digits': CoreErrorMessages.INVALID_FIELD.format(field='Target Value (maximum 12 digits)'),
            'max_decimal_places': CoreErrorMessages.INVALID_FIELD.format(field='Target Value (maximum 2 decimal places)')
        }
    )
    
    current_value = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        default=0.00,
        error_messages={
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Current Value (must be a valid number)'),
            'max_digits': CoreErrorMessages.INVALID_FIELD.format(field='Current Value (maximum 12 digits)'),
            'max_decimal_places': CoreErrorMessages.INVALID_FIELD.format(field='Current Value (maximum 2 decimal places)')
        }
    )
    
    objective_type = serializers.ChoiceField(
        choices=CampaignObjective.ObjectiveType.choices,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Objective Type'),
            'invalid_choice': CoreErrorMessages.INVALID_FIELD.format(field='Objective Type (invalid choice)')
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
        try:
            return obj.get_objective_type_display()
        except Exception:
            return obj.objective_type
    
    def get_progress_percentage(self, obj):
        """Get the calculated progress percentage"""
        try:
            return obj.progress_percentage()
        except Exception:
            return 0.0
    
    def validate_target_value(self, value):
        """Validate target value is positive"""
        try:
            if value <= 0:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="Target Value (must be greater than 0)")
                )
            return value
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Target Value")
            )
    
    def validate_current_value(self, value):
        """Validate current value is not negative"""
        try:
            if value < 0:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="Current Value (cannot be negative)")
                )
            return value
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Current Value")
            )
    
    def validate(self, data):
        """Complete validation of CampaignObjective data with standardized error handling"""
        try:
            # Get client_id for validations
            client_id = self._get_client_id_from_context()
            
            # Validate client scope for campaign
            campaign = data.get('campaign')
            if campaign:
                # Validate client ID first (basic security)
                try:
                    self.validate_client_id(campaign)
                except Exception as e:
                    raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
                
                # Validate that the user owns the campaign or has permissions
                request = self.context.get('request')
                if request and hasattr(request, 'user'):
                    current_user = request.user
                    
                    # Check if user is the campaign owner
                    if campaign.owner and campaign.owner.id != current_user.id:
                        # Check if user has permissions or is a stakeholder
                        if not current_user.has_perm('campaign.change_campaign'):
                            # Check if user is a stakeholder
                            from apps.campaign.models.campaign_stakeholder import CampaignStakeholder
                            is_stakeholder = CampaignStakeholder.objects.filter(
                                campaign=campaign,
                                user=current_user
                            ).exists()
                            
                            if not is_stakeholder:
                                raise StandardizedValidationError(
                                    CoreErrorMessages.PERMISSION_DENIED
                                )
            
            # Validate objective_type
            objective_type = data.get('objective_type')
            if objective_type:
                valid_types = [choice[0] for choice in CampaignObjective.ObjectiveType.choices]
                if objective_type not in valid_types:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field=f"Objective Type (must be one of: {', '.join(valid_types)})"
                        )
                    )
            
            # Cross-field validation: ensure target_value > current_value is reasonable
            target_value = data.get('target_value')
            current_value = data.get('current_value', 0)
            
            if target_value and current_value and current_value > target_value:
                # This is a warning, not an error - allow but could be flagged
                pass  # In the future, we could add warnings to the response
            
            return super().validate(data)
            
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except serializers.ValidationError as e:
            # Convert DRF validation errors to standardized format
            if isinstance(e.detail, dict):
                # Multiple field errors
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
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Objective validation failed")
            )
    
    def create(self, validated_data):
        """Create a new CampaignObjective instance with client_id and error handling"""
        try:
            # Ensure client_id is included
            if 'client_id' not in validated_data:
                client_id = self.context.get('request').auth.get('client_account') if self.context.get('request') and self.context.get('request').auth else None
                if not client_id and self.context.get('request'):
                    # Fallback to user's client_id if available
                    user = self.context.get('request').user
                    if hasattr(user, 'client_id'):
                        client_id = user.client_id
                        
                if client_id:
                    validated_data['client_id'] = client_id
            
            return super().create(validated_data)
            
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Objective creation failed")
            )
    
    def update(self, instance, validated_data):
        """Update a CampaignObjective instance with error handling"""
        try:
            # Validate client scope
            self.validate_client_id(instance)
            
            return super().update(instance, validated_data)
            
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Objective update failed")
            )