# backend/apps/campaign/serializers/campaign_serializer.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from end_users.models import User
from apps.campaign.models.campaign import Campaign
from apps.sequence.sequences.sequence_dispatcher import SequenceDisptacher

class CampaignOwnerSerializer(serializers.ModelSerializer):
    """Serializer for the campaign owner summary"""
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role_name', 'team']
        read_only_fields = fields

class CampaignSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Serializer for Campaign model"""
    
    # Field for write operations
    name = serializers.CharField(
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign Name'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Campaign Name')
        }
    )

    sequence_type = serializers.ChoiceField(
        choices=SequenceDisptacher.SEQUENCE_CHOICES,
        default=SequenceDisptacher.CHASING,
        error_messages={
            'invalid_choice': CoreErrorMessages.INVALID_FIELD.format(field='Sequence Type')
        }
    )
    
    # Fields for read operations
    owner = CampaignOwnerSerializer(read_only=True)
    owner_id = serializers.SerializerMethodField(read_only=True)
    campaign_type_display = serializers.SerializerMethodField(read_only=True)
    progress_summary = serializers.SerializerMethodField(read_only=True)
    sequence_type_display = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Campaign
        fields = [
            'id', 'name', 'description', 'campaign_type', 'campaign_type_display',
            'sequence_type', 'sequence_type_display', 
            'owner', 'owner_id', 'start_date', 'end_date', 
            'progress_summary', 'client_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'client_id', 'created_at', 'updated_at', 'progress_summary', 'owner_id', 'sequence_type_display']

    def get_sequence_type_display(self, obj):
        """Get the display name for sequence type"""
        return dict(SequenceDisptacher.SEQUENCE_CHOICES).get(obj.sequence_type, '')
        
    def get_owner_id(self, obj):
        """Get the owner ID, defaulting to current user if needed"""
        # If owner exists, return its ID
        if obj.owner:
            return obj.owner.id
        
        # If in a request context, return current user's ID
        if self.context.get('request') and hasattr(self.context['request'], 'user'):
            return self.context['request'].user.id
        
        # No owner and no current user
        return None
    
    def get_campaign_type_display(self, obj):
        """Get the display name for campaign type"""
        return obj.get_campaign_type_display()
    
    def get_progress_summary(self, obj):
        """Get progress summary from campaign objectives"""
        # This will be implemented after CampaignObjective model is created
        # For now return a placeholder
        return {
            'total_objectives': 0,
            'completed_objectives': 0,
            'progress_percentage': 0
        }
    
    def validate(self, data):
        """Complete validation of Campaign data"""
        try:
            # Get client_id for validations
            client_id = self._get_client_id_from_context()
            
            # Validate date range
            if 'start_date' in data and 'end_date' in data:
                if data['end_date'] < data['start_date']:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_DATE_RANGE.format(
                            start_date=data['start_date'],
                            end_date=data['end_date']
                        )
                    )
            
            today = timezone.now().date()
            if data['end_date'] < today:
                raise StandardizedValidationError(
                    _("Campaign end date must be in the future. Current date: {today}, End date: {end_date}").format(
                        today=today,
                        end_date=data['end_date']
                    )
                )
            
            # Validate campaign type
            if 'campaign_type' in data:
                valid_types = [choice[0] for choice in Campaign.CampaignType.choices]
                if data['campaign_type'] not in valid_types:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(field="Campaign Type")
                    )
            
            return super().validate(data)
            
        except serializers.ValidationError as e:
            raise StandardizedValidationError(e.detail)
    
    def create(self, validated_data):
        """Create a new Campaign instance with client_id properly passed to save()"""
        client_id = self.context.get('client_id')
        if not client_id and self.context.get('request'):
            client_id = self.context['request'].auth.get('client_account')
        
        if not client_id:
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_ID_REQUIRED)
        
        # Pass client_id as keyword arg to save()
        instance = Campaign(**validated_data)
        instance.save(client_id=client_id, user=self.context.get('request').user if self.context.get('request') else None)
        
        return instance