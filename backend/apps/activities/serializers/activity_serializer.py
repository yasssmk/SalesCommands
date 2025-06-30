# apps/activities/serializers/activity_serializer.py
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.activities.models import Activity, ActivityCampaign, ActivitySequence
from apps.accounts.models import Account, Contact
from apps.campaign.models import Campaign, CampaignTarget


class ActivitySequenceSerializer(serializers.ModelSerializer):
    """Serializer for ActivitySequence model"""
    sequence_outcome_display = serializers.SerializerMethodField(read_only=True)
    source_type_display = serializers.SerializerMethodField(read_only=True)
    can_attempt_call = serializers.SerializerMethodField(read_only=True)

    sequence_type_display = serializers.SerializerMethodField(read_only=True)
    sequence_variant_display = serializers.SerializerMethodField(read_only=True)
    is_from_sequence = serializers.SerializerMethodField(read_only=True)
    full_sequence_info = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = ActivitySequence
        fields = [
            'id', 'source_type', 'source_type_display', 'sequence_position',
            'sequence_outcome', 'sequence_outcome_display', 'call_attempts',
            'can_attempt_call', 'callback_requested_date', 'sequence_paused_until',
            'days_since_last_sequence_activity', 'next_sequence_activity',
            'sequence_type', 'sequence_type_display',
            'sequence_variant', 'sequence_variant_display',
            'is_from_sequence', 'full_sequence_info'
        ]
        read_only_fields = ['id', 'days_since_last_sequence_activity']
    
    def get_sequence_outcome_display(self, obj):
        """Get the display name for sequence outcome"""
        if obj.sequence_outcome:
            return obj.get_sequence_outcome_display()
        return None
    
    def get_source_type_display(self, obj):
        """Get the display name for source type"""
        return obj.get_source_type_display()
    
    def get_can_attempt_call(self, obj):
        """Check if another call attempt is allowed"""
        return obj.call_attempts < 3
    
    def get_sequence_type_display(self, obj):
        """Get human-readable display for sequence type"""
        return obj.get_sequence_type_display()
    
    def get_sequence_variant_display(self, obj):
        """Get human-readable display for sequence variant"""
        return obj.get_sequence_variant_display()
    
    def get_is_from_sequence(self, obj):
        """Check if this activity is from a sequence"""
        return obj.is_from_sequence()
    
    def get_full_sequence_info(self, obj):
        """Get complete sequence information for API responses"""
        return obj.get_full_sequence_info()


class ActivityCampaignSerializer(serializers.ModelSerializer):
    """Serializer for ActivityCampaign model"""
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    
    class Meta:
        model = ActivityCampaign
        fields = [
            'id', 'campaign', 'campaign_name', 'campaign_target',
            'meeting_scheduled', 'opportunity_created'
        ]
        read_only_fields = ['id']


class ActivitySerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Main serializer for Activity model with optional nested campaign and sequence info
    """
    # Nested serializers for related models
    campaign_info = ActivityCampaignSerializer(read_only=True)
    sequence_info = ActivitySequenceSerializer(read_only=True)

    # Display fields
    activity_type_display = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)
    
    # Related object displays
    account_name = serializers.CharField(source='account.company_name', read_only=True)
    owner_name = serializers.StringRelatedField(source='owner', read_only=True)
    contact_names = serializers.SerializerMethodField(read_only=True)
    
    # Write fields for creating activities
    contact_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of contact IDs to associate with this activity"
    )

    contact_validation_info = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Activity
        fields = [
            'id', 'title', 'activity_type', 'activity_type_display',
            'description', 'account', 'account_name', 'contacts', 'contact_ids',
            'contact_names', 'owner', 'owner_name', 'scheduled_start',
            'scheduled_end', 'status', 'status_display', 'completed_at',
            'outcome_notes', 'opportunity', 'campaign_info', 'sequence_info',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'completed_at']
    
    def get_activity_type_display(self, obj):
        """Get the display name for activity type"""
        return obj.get_activity_type_display()
    
    def get_status_display(self, obj):
        """Get the display name for status"""
        return obj.get_status_display()
    
    def get_contact_names(self, obj):
        """Get names of associated contacts"""
        return [f"{c.first_name} {c.last_name}" for c in obj.contacts.all()]
    
    def get_contact_validation_info(self, obj):
        """Get validation info for contacts in this activity"""
        if not obj.contacts.exists():
            return None
        
        contact = obj.contacts.first()
        return {
            'email_is_valid': contact.email_is_valid,
            'phone_is_valid': contact.phone_is_valid,
            'opted_out': contact.opted_out,
            'has_email': bool(contact.email),
            'has_phone': bool(contact.phone_number),
            'has_linkedin': bool(contact.linkedin),
        }
    
    def validate(self, data):
        """Validate the activity data"""
        try:
            # Get client_id for validations
            client_id = self._get_client_id_from_context()
            
            # Validate account belongs to client
            if 'account' in data:
                account = data['account']
                self.validate_client_id(account)
            
            # Validate scheduled dates
            if 'scheduled_end' in data and 'scheduled_start' in data:
                if data['scheduled_end'] < data['scheduled_start']:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_DATE_RANGE.format(
                            start_date=data['scheduled_start'],
                            end_date=data['scheduled_end']
                        )
                    )
            
            return super().validate(data)
            
        except serializers.ValidationError as e:
            raise StandardizedValidationError(e.detail)
    
    def create(self, validated_data):
        """Create activity with optional contacts"""
        contact_ids = validated_data.pop('contact_ids', [])
        
        # Set owner to current user if not provided
        if 'owner' not in validated_data and self.context.get('request'):
            validated_data['owner'] = self.context['request'].user
        
        activity = super().create(validated_data)
        
        # Add contacts if provided
        if contact_ids:
            contacts = Contact.objects.filter(
                id__in=contact_ids,
                account=activity.account,
                client_id=self.get_client_id()
            )
            activity.contacts.set(contacts)
        
        return activity


class ActivityWithCampaignSerializer(ActivitySerializer):
    """
    Serializer for creating activities with campaign information
    """
    # Campaign-specific fields
    campaign_id = serializers.IntegerField(write_only=True)
    campaign_target_id = serializers.IntegerField(write_only=True)
    
    # Sequence-specific fields
    sequence_position = serializers.IntegerField(write_only=True, required=False)
    source_type = serializers.CharField(
        write_only=True,
        default=ActivitySequence.SourceType.CAMPAIGN
    )
    
    class Meta(ActivitySerializer.Meta):
        fields = ActivitySerializer.Meta.fields + [
            'campaign_id', 'campaign_target_id', 'sequence_position', 'source_type'
        ]
    
    def validate(self, data):
        """Validate campaign-specific data"""
        data = super().validate(data)
        
        # Validate campaign exists and belongs to user
        if 'campaign_id' in data:
            try:
                campaign = Campaign.objects.get(
                    id=data['campaign_id'],
                    client_id=self.get_client_id()
                )
                
                # Check if user owns the campaign
                if self.context.get('request') and hasattr(self.context['request'], 'user'):
                    if campaign.owner != self.context['request'].user:
                        raise StandardizedValidationError(
                            "You can only create activities for your own campaigns"
                        )
                
            except Campaign.DoesNotExist:
                raise StandardizedValidationError("Campaign not found")
        
        # Validate campaign target
        if 'campaign_target_id' in data:
            try:
                campaign_target = CampaignTarget.objects.get(
                    id=data['campaign_target_id'],
                    campaign_id=data.get('campaign_id'),
                    client_id=self.get_client_id()
                )
                
                # Ensure activity account matches campaign target account
                if 'account' in data and data['account'] != campaign_target.account:
                    raise StandardizedValidationError(
                        "Activity account must match campaign target account"
                    )
                
            except CampaignTarget.DoesNotExist:
                raise StandardizedValidationError("Campaign target not found")
        
        return data
    
    def create(self, validated_data):
        """Create activity with campaign and sequence information"""
        # Extract campaign-specific data
        campaign_id = validated_data.pop('campaign_id')
        campaign_target_id = validated_data.pop('campaign_target_id')
        sequence_position = validated_data.pop('sequence_position', None)
        source_type = validated_data.pop('source_type', ActivitySequence.SourceType.CAMPAIGN)
        
        # Create the activity
        activity = super().create(validated_data)
        
        # Create campaign information
        campaign = Campaign.objects.get(id=campaign_id)
        campaign_target = CampaignTarget.objects.get(id=campaign_target_id)
        
        ActivityCampaign.objects.create(
            activity=activity,
            campaign=campaign,
            campaign_target=campaign_target
        )
        
        # Create sequence information if provided
        if sequence_position is not None:
            ActivitySequence.objects.create(
                activity=activity,
                source_type=source_type,
                sequence_position=sequence_position
            )
        
        return activity


class ActivityCompletionSerializer(serializers.Serializer):
    """
    Serializer for completing activities with outcomes
    """
    outcome_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Notes about the outcome of the activity"
    )
    
    # Campaign-specific outcomes
    meeting_scheduled = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Whether a meeting was scheduled as a result"
    )
    
    opportunity_created = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Whether an opportunity was created as a result"
    )
    
    # Sequence-specific outcomes
    sequence_outcome = serializers.ChoiceField(
        choices=ActivitySequence.SequenceOutcome.choices,
        required=False,
        help_text="Outcome of the sequence activity"
    )
    
    callback_requested_date = serializers.DateField(
        required=False,
        help_text="Date when contact requested to be called back"
    )

    
    
    def validate(self, data):
        """Validate completion data"""
        # If sequence outcome is callback requested, require callback date
        if (data.get('sequence_outcome') == ActivitySequence.SequenceOutcome.CALLBACK_REQUESTED and
            not data.get('callback_requested_date')):
            raise serializers.ValidationError(
                "Callback date is required when outcome is 'callback requested'"
            )
        
        return data