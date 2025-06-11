# apps/campaign/serializers/campaign_serializer.py - Validation methods update

from rest_framework import serializers
from apps.campaign.models.campaign import Campaign
from apps.campaign.models.campaign_stakeholder import CampaignStakeholder
from apps.campaign.serializers.campaign_stakeholders_serializer import CampaignStakeholderSerializer
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from end_users.models import User

class CampaignSerializer(serializers.ModelSerializer):
    """Serializer for Campaign model with standardized validation"""
    
    # Read-only fields
    owner_name = serializers.SerializerMethodField(read_only=True)
    campaign_type_display = serializers.CharField(source='get_campaign_type_display', read_only=True)
    sequence_type_display = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    stakeholders = CampaignStakeholderSerializer(source='stakeholders.through.objects', many=True, read_only=True)
    
    # Computed fields
    has_sequence = serializers.SerializerMethodField(read_only=True)
    is_call_list = serializers.SerializerMethodField(read_only=True)
    target_summary = serializers.SerializerMethodField(read_only=True)
    has_mixed_targets = serializers.SerializerMethodField(read_only=True)

    # Stakeholder write fields
    owner_ids = serializers.PrimaryKeyRelatedField(
        many=True, 
        write_only=True, 
        queryset=User.objects.all(),
        required=False,
        error_messages={
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Owner IDs')
        }
    )
    
    executor_ids = serializers.PrimaryKeyRelatedField(
        many=True, 
        write_only=True, 
        queryset=User.objects.all(),
        required=False,
        error_messages={
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Executor IDs')
        }
    )
    
    receiver_ids = serializers.PrimaryKeyRelatedField(
        many=True, 
        write_only=True, 
        queryset=User.objects.all(),
        required=False,
        error_messages={
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Receiver IDs')
        }
    )
    
    # Campaign name with custom validation
    name = serializers.CharField(
        max_length=100,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign Name'),
            'blank': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign Name'),
            'max_length': CoreErrorMessages.INVALID_FIELD.format(field='Campaign Name (maximum 100 characters)')
        }
    )
    
    # Date fields with custom validation
    start_date = serializers.DateField(
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Start Date'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Start Date (format: YYYY-MM-DD)')
        }
    )
    
    end_date = serializers.DateField(
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='End Date'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='End Date (format: YYYY-MM-DD)')
        }
    )
    
    # Computed stakeholder summaries
    owner_count = serializers.SerializerMethodField(read_only=True)
    executor_count = serializers.SerializerMethodField(read_only=True)
    receiver_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Campaign
        fields = [
            'id',
            'name',
            'description',
            
            # Campaign configuration
            'campaign_type',
            'campaign_type_display',
            'sequence_type',
            'sequence_type_display',
            'has_sequence',
            'is_call_list',
            
            # Ownership
            'owner',
            'owner_name',
            
            # Stakeholders
            'stakeholders',
            'owner_ids',
            'executor_ids',
            'receiver_ids',
            'owner_count',
            'executor_count',
            'receiver_count',
            
            # Dates
            'start_date',
            'end_date',
            
            # Status
            'status',
            'status_display',
            
            # Target information
            'target_summary',
            'has_mixed_targets',
            
            # Metadata
            'created_at',
            'updated_at',
            'created_by',
            'updated_by'
        ]
        read_only_fields = [
            'owner_name',
            'campaign_type_display',
            'sequence_type_display',
            'status_display',
            'has_sequence',
            'is_call_list',
            'target_summary',
            'has_mixed_targets',
            'owner_count',
            'executor_count',
            'receiver_count',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by'
        ]
    
    def get_owner_name(self, obj):
        """Get the full name of the campaign owner"""
        try:
            if obj.owner:
                return f"{obj.owner.first_name} {obj.owner.last_name}".strip() or obj.owner.username
            return None
        except Exception:
            return None
    
    def get_sequence_type_display(self, obj):
        """Get display name for sequence type"""
        try:
            if obj.sequence_type:
                # Get the display value from choices
                from apps.sequence.sequences.sequence_dispatcher import SequenceDispatcher
                for choice in SequenceDispatcher.SEQUENCE_CHOICES:
                    if choice[0] == obj.sequence_type:
                        return choice[1]
                return obj.sequence_type
            return "No Sequence (Call List)"
        except Exception:
            return obj.sequence_type if obj.sequence_type else "No Sequence"
    
    def get_has_sequence(self, obj):
        """Check if campaign has automated sequences"""
        try:
            return obj.has_sequence()
        except Exception:
            return False
    
    def get_is_call_list(self, obj):
        """Check if campaign is a simple call list"""
        try:
            return obj.is_call_list()
        except Exception:
            return True
    
    def get_target_summary(self, obj):
        """Get summary of targets in the campaign"""
        try:
            return obj.get_target_summary()
        except Exception:
            return {'total': 0, 'accounts': 0, 'contacts': 0, 'leads': 0, 'opportunities': 0}
    
    def get_has_mixed_targets(self, obj):
        """Check if campaign has multiple target types"""
        try:
            return obj.has_mixed_targets()
        except Exception:
            return False
    
    def get_owner_count(self, obj):
        """Get count of owners"""
        try:
            return obj.get_owners().count()
        except Exception:
            return 0
    
    def get_executor_count(self, obj):
        """Get count of executors"""
        try:
            return obj.get_executors().count()
        except Exception:
            return 0
    
    def get_receiver_count(self, obj):
        """Get count of receivers"""
        try:
            return obj.get_receivers().count()
        except Exception:
            return 0
    
    def validate_start_date(self, value):
        """Validate start date"""
        try:
            from datetime import date
            if value < date.today():
                # Allow past start dates for existing campaigns, but warn for new ones
                pass  # Could add warnings in the future
            return value
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Start Date")
            )
    
    def validate_end_date(self, value):
        """Validate end date"""
        try:
            from datetime import date
            if value < date.today():
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="End Date (cannot be in the past)")
                )
            return value
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="End Date")
            )
    
    def validate(self, data):
        """Validate campaign data with standardized error handling"""
        try:
            # Validate dates
            start_date = data.get('start_date', self.instance.start_date if self.instance else None)
            end_date = data.get('end_date', self.instance.end_date if self.instance else None)
            
            if start_date and end_date and end_date < start_date:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Date range (end date {end_date} must be after start date {start_date})"
                    )
                )
            
            # Validate sequence_type with campaign_type
            campaign_type = data.get('campaign_type', self.instance.campaign_type if self.instance else None)
            sequence_type = data.get('sequence_type', self.instance.sequence_type if self.instance else None)
            
            # Call list campaigns should not have a sequence
            if campaign_type == Campaign.CampaignType.CALL_LIST and sequence_type is not None:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field="Sequence Type (Call List campaigns cannot have automated sequences)"
                    )
                )
            
            # Validate stakeholder lists don't contain duplicates
            stakeholder_fields = ['owner_ids', 'executor_ids', 'receiver_ids']
            for field_name in stakeholder_fields:
                stakeholder_list = data.get(field_name, [])
                if stakeholder_list and len(stakeholder_list) != len(set(user.id for user in stakeholder_list)):
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field=f"{field_name.replace('_', ' ').title()} (cannot contain duplicate users)"
                        )
                    )
            
            return data
            
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
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Campaign validation failed")
            )
    
    def create(self, validated_data):
        """Create a new campaign with stakeholders and standardized error handling"""
        try:
            # Extract stakeholder data
            owner_ids = validated_data.pop('owner_ids', [])
            executor_ids = validated_data.pop('executor_ids', [])
            receiver_ids = validated_data.pop('receiver_ids', [])
            
            # Get the current user
            request = self.context.get('request')
            user = request.user if request and hasattr(request, 'user') else None
            
            # Set created_by and updated_by
            if user:
                validated_data['created_by'] = user
                validated_data['updated_by'] = user
                if 'owner' not in validated_data:
                    validated_data['owner'] = user
            
            # Create the campaign
            campaign = Campaign.objects.create(**validated_data)
            
            # Add stakeholders with error handling
            self._add_stakeholders_safely(campaign, owner_ids, executor_ids, receiver_ids, user)
            
            return campaign
            
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Campaign creation failed")
            )
    
    def update(self, instance, validated_data):
        """Update a campaign with stakeholders and standardized error handling"""
        try:
            # Extract stakeholder data
            owner_ids = validated_data.pop('owner_ids', None)
            executor_ids = validated_data.pop('executor_ids', None)
            receiver_ids = validated_data.pop('receiver_ids', None)
            
            # Get the current user
            request = self.context.get('request')
            user = request.user if request and hasattr(request, 'user') else None
            
            # Set updated_by
            if user:
                validated_data['updated_by'] = user
            
            # Update the instance
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            instance.save()
            
            # Update stakeholders if provided
            self._update_stakeholders_safely(instance, owner_ids, executor_ids, receiver_ids, user)
            
            return instance
            
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Campaign update failed")
            )
    
    def _add_stakeholders_safely(self, campaign, owner_ids, executor_ids, receiver_ids, user):
        """Add stakeholders with error handling"""
        try:
            # The owner will already be added as a stakeholder via the save method
            
            # Add additional owners
            for owner in owner_ids:
                if owner != campaign.owner:  # Avoid duplicate if owner is already set
                    campaign.add_stakeholder(owner, CampaignStakeholder.StakeholderRole.OWNER, added_by=user)
            
            # Add executors
            for executor in executor_ids:
                campaign.add_stakeholder(executor, CampaignStakeholder.StakeholderRole.EXECUTOR, added_by=user)
            
            # Add receivers
            for receiver in receiver_ids:
                campaign.add_stakeholder(receiver, CampaignStakeholder.StakeholderRole.RECEIVER, added_by=user)
                
        except Exception as e:
            # If stakeholder addition fails, we should still have the campaign created
            # Log the error but don't fail the entire creation
            pass  # In production, this should be logged
    
    def _update_stakeholders_safely(self, instance, owner_ids, executor_ids, receiver_ids, user):
        """Update stakeholders with error handling"""
        try:
            # Update stakeholders if provided
            if owner_ids is not None:
                # Remove existing owners (except for the campaign.owner which is added automatically)
                instance.stakeholder_links.filter(
                    role=CampaignStakeholder.StakeholderRole.OWNER
                ).exclude(user=instance.owner).delete()
                
                # Add new owners
                for owner in owner_ids:
                    if owner != instance.owner:  # Avoid duplicate with campaign.owner
                        instance.add_stakeholder(owner, CampaignStakeholder.StakeholderRole.OWNER, added_by=user)
            
            if executor_ids is not None:
                # Remove existing executors
                instance.stakeholder_links.filter(
                    role=CampaignStakeholder.StakeholderRole.EXECUTOR
                ).delete()
                
                # Add new executors
                for executor in executor_ids:
                    instance.add_stakeholder(executor, CampaignStakeholder.StakeholderRole.EXECUTOR, added_by=user)
            
            if receiver_ids is not None:
                # Remove existing receivers
                instance.stakeholder_links.filter(
                    role=CampaignStakeholder.StakeholderRole.RECEIVER
                ).delete()
                
                # Add new receivers
                for receiver in receiver_ids:
                    instance.add_stakeholder(receiver, CampaignStakeholder.StakeholderRole.RECEIVER, added_by=user)
                    
        except Exception as e:
            # If stakeholder update fails, log but don't fail the entire update
            pass  # In production, this should be logged


class CampaignListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing campaigns"""
    
    owner_name = serializers.SerializerMethodField(read_only=True)
    campaign_type_display = serializers.CharField(source='get_campaign_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    has_sequence = serializers.SerializerMethodField(read_only=True)
    target_counts = serializers.SerializerMethodField(read_only=True)
    owner_count = serializers.SerializerMethodField(read_only=True)
    executor_count = serializers.SerializerMethodField(read_only=True)
    receiver_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Campaign
        fields = [
            'id',
            'name',
            'campaign_type',
            'campaign_type_display',
            'has_sequence',
            'owner',
            'owner_name',
            'owner_count',
            'executor_count',
            'receiver_count',
            'start_date',
            'end_date',
            'status',
            'status_display',
            'target_counts',
            'created_at'
        ]
    
    def get_owner_name(self, obj):
        """Get the full name of the campaign owner"""
        if obj.owner:
            return f"{obj.owner.first_name} {obj.owner.last_name}"
        return None
    
    def get_has_sequence(self, obj):
        """Check if campaign has automated sequences"""
        return obj.has_sequence()
    
    def get_target_counts(self, obj):
        """Get simplified target counts"""
        summary = obj.get_target_summary()
        return {
            'total': summary['total'],
            'accounts': summary['accounts'],
            'contacts': summary['contacts'],
            'leads': summary['leads']
        }
    
    def get_owner_count(self, obj):
        """Get count of owners"""
        return obj.get_owners().count()
    
    def get_executor_count(self, obj):
        """Get count of executors"""
        return obj.get_executors().count()
    
    def get_receiver_count(self, obj):
        """Get count of receivers"""
        return obj.get_receivers().count()


# Export serializers
__all__ = [
    'CampaignSerializer',
    'CampaignListSerializer'
]