# apps/campaign/serializers/campaign_stakeholders_serializer.py

from rest_framework import serializers
from apps.campaign.models import CampaignStakeholder
from apps.campaign.models.campaign import Campaign
from end_users.models import User
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.client_scope import ClientScopeManager

# Import configuration variables
from apps.campaign.config.settings import CONFIG


class CampaignStakeholderSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for campaign stakeholders with standardized validation
    """
    user_name = serializers.SerializerMethodField(read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    added_by_name = serializers.SerializerMethodField(read_only=True)
    campaign_name = serializers.SerializerMethodField(read_only=True)
    
    # Write fields with improved error messages
    campaign = serializers.PrimaryKeyRelatedField(
        queryset=Campaign.objects.all(),
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign'),
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Campaign ID')
        }
    )
    
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='User'),
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='User ID')
        }
    )
    
    role = serializers.ChoiceField(
        choices=CampaignStakeholder.StakeholderRole.choices,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Role'),
            'invalid_choice': CoreErrorMessages.INVALID_FIELD.format(field='Role (invalid choice)')
        }
    )
    
    class Meta:
        model = CampaignStakeholder
        fields = CONFIG.serializers.stakeholder_fields
        read_only_fields = CONFIG.serializers.stakeholder_read_only_fields
    
    def get_user_name(self, obj):
        """Get the name of the stakeholder"""
        try:
            if obj.user:
                full_name = f"{obj.user.first_name} {obj.user.last_name}".strip()
                return full_name or obj.user.username
            return None
        except Exception:
            return None
    
    def get_added_by_name(self, obj):
        """Get the name of the user who added this stakeholder"""
        try:
            if obj.added_by:
                full_name = f"{obj.added_by.first_name} {obj.added_by.last_name}".strip()
                return full_name or obj.added_by.username
            return None
        except Exception:
            return None
    
    def get_campaign_name(self, obj):
        """Get the name of the campaign"""
        try:
            return obj.campaign.name if obj.campaign else None
        except Exception:
            return None
    
    def validate(self, data):
        """Validate stakeholder data with standardized error handling"""
        try:
            # Validate client scope for campaign
            campaign = data.get(CONFIG.fields.campaign)
            if campaign:
                try:
                    self.validate_client_id(campaign)
                except Exception:
                    raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
            
            # Validate that user and campaign are provided
            user = data.get(CONFIG.fields.user)
            role = data.get(CONFIG.fields.role)
            
            if not user:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='User')
                )
            
            if not role:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='Role')
                )
            
            # Validate role choice
            valid_roles = [choice[0] for choice in CampaignStakeholder.StakeholderRole.choices]
            if role not in valid_roles:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Role (must be one of: {', '.join(valid_roles)})"
                    )
                )
            
            # Check for existing stakeholder with same campaign, user, and role
            instance_id = getattr(self.instance, 'id', None)
            existing = CampaignStakeholder.objects.filter(
                **{
                    CONFIG.fields.campaign: campaign,
                    CONFIG.fields.user: user,
                    CONFIG.fields.role: role
                }
            ).exclude(id=instance_id)
            
            if existing.exists():
                user_name = self.get_user_name(existing.first()) or f"User {user.id}"
                role_display = existing.first().get_role_display() if existing.first() else role
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Stakeholder (user '{user_name}' already has role '{role_display}' in this campaign)"
                    )
                )
            
            return data
            
        except StandardizedValidationError:
            # Re-raise standardized validation errors
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
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Stakeholder validation failed")
            )
    
    def create(self, validated_data):
        """Create a new campaign stakeholder with standardized error handling"""
        try:
            # Set added_by from context if available
            request = self.context.get('request')
            if request and hasattr(request, 'user'):
                validated_data['added_by'] = request.user
            
            # Ensure client_id is set
            campaign = validated_data.get(CONFIG.fields.campaign)
            if campaign and hasattr(campaign, 'client_id'):
                validated_data['client_id'] = campaign.client_id
            
            return CampaignStakeholder.objects.create(**validated_data)
            
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Stakeholder creation failed")
            )
    
    def update(self, instance, validated_data):
        """Update a campaign stakeholder with standardized error handling"""
        try:
            # Validate client scope for existing instance
            self.validate_client_id(instance)
            
            # Update the instance
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            instance.save()
            return instance
            
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Stakeholder update failed")
            )