# apps/leads/serializers/lead_serializer.py

from rest_framework import serializers
from apps.leads.models import Lead
from apps.accounts.models import Contact, Account
from apps.campaign.models import Campaign
from apps.activities.models import Activity
from core.exceptions import StandardizedValidationError
from apps.core_apps.serializers import AccountLinkedSerializerMixin


class LeadSerializer(AccountLinkedSerializerMixin, serializers.ModelSerializer):
    """Serializer for Lead model"""
    
    # Read-only fields for display
    account = serializers.SerializerMethodField(read_only=True)
    contact_name = serializers.SerializerMethodField(read_only=True)
    assigned_to_name = serializers.SerializerMethodField(read_only=True)
    campaign_name = serializers.CharField(source='campaign.name', read_only=True, allow_null=True)
    lead_status_display = serializers.CharField(source='get_lead_status_display', read_only=True)
    lead_source_display = serializers.CharField(source='get_lead_source_display', read_only=True)
    
    # Computed fields
    number_of_touches = serializers.SerializerMethodField(read_only=True)
    queued_activities_count = serializers.SerializerMethodField(read_only=True)
    
    # Write fields that accept IDs
    contact_id = serializers.PrimaryKeyRelatedField(
        queryset=Contact.objects.all(),
        source='contact',
        write_only=True
    )
    campaign_id = serializers.PrimaryKeyRelatedField(
        queryset=Campaign.objects.all(),
        source='campaign',
        write_only=True,
        required=False,
        allow_null=True
    )
    source_activity_id = serializers.PrimaryKeyRelatedField(
        queryset=Activity.objects.all(),
        source='source_activity',
        write_only=True,
        required=False,
        allow_null=True
    )
    activity_ids = serializers.PrimaryKeyRelatedField(
        queryset=Activity.objects.all(),
        source='activities',
        write_only=True,
        many=True,
        required=False
    )
    
    class Meta:
        model = Lead
        fields = [
            'id',
            'title',
            'description',
            
            # Source Information
            'lead_source',
            'lead_source_display',
            'lead_source_detail',
            
            # Status
            'lead_status',
            'lead_status_display',
            
            # Relationships - Read
            'account',
            'contact_name',
            'campaign_name',
            'assigned_to_name',
            
            # Relationships - Write
            'contact_id',
            'campaign_id',
            'source_activity_id',
            'activity_ids',
            'assigned_to',
            
            # Tracking
            'last_activity_date',
            'last_contacted_date',
            'number_of_touches',
            'queued_activities_count',
            
            # Qualification
            'is_qualified',
            'qualification_date',
            
            # Conversion
            'conversion_date',
            'converted_to_opportunity',
            
            # Metadata
            'notes',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by'
        ]
        read_only_fields = [
            'last_activity_date',
            'last_contacted_date', 
            'number_of_touches',
            'queued_activities_count',
            'qualification_date',
            'conversion_date',
            'converted_to_opportunity',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by'
        ]
    
    def get_contact_name(self, obj):
        """Get the full name of the contact"""
        if obj.contact:
            return f"{obj.contact.first_name} {obj.contact.last_name}"
        return None
    
    def get_assigned_to_name(self, obj):
        """Get the full name of assigned user"""
        if obj.assigned_to:
            return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}"
        return None
    
    def get_number_of_touches(self, obj):
        """Get count of activities linked to this lead"""
        return obj.activities.count()
    
    def get_queued_activities_count(self, obj):
        """Get count of planned activities for this lead"""
        return obj.activities.filter(status='PLANNED').count()
    
    def validate(self, data):
        """Validate lead data"""
        # Call parent validation first
        data = super().validate(data)
        
        # Check if contact belongs to account
        contact = data.get('contact')
        account = data.get('account', self.instance.account if self.instance else None)
        
        if contact and account:
            if contact.account != account:
                raise StandardizedValidationError(
                    "Contact must belong to the specified account",
                    field_name="contact_id"
                )
        
        # Validate campaign source
        lead_source = data.get('lead_source', self.instance.lead_source if self.instance else None)
        campaign = data.get('campaign')
        
        if lead_source == Lead.LeadSource.CAMPAIGN and not campaign:
            raise StandardizedValidationError(
                "Campaign is required when lead source is Campaign",
                field_name="campaign_id"
            )
        
        # Validate activity source
        source_activity = data.get('source_activity')
        
        if lead_source == Lead.LeadSource.ACTIVITY and not source_activity:
            raise StandardizedValidationError(
                "Source activity is required when lead source is Activity",
                field_name="source_activity_id"
            )
        
        return data
    
    def create(self, validated_data):
        """Create a new lead"""
        # Pop the user from context if available
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
            validated_data['updated_by'] = request.user
        
        # Pop activities to handle ManyToMany separately
        activities = validated_data.pop('activities', [])
        
        lead = Lead.objects.create(**validated_data)
        
        # Add activities if provided
        if activities:
            lead.activities.set(activities)
        
        # Update activity tracking
        lead.update_activity_tracking()
        
        return lead
    
    def update(self, instance, validated_data):
        """Update an existing lead"""
        # Pop the user from context if available
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['updated_by'] = request.user
        
        # Handle activities separately
        activities = validated_data.pop('activities', None)
        
        # Update the lead
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Update activities if provided
        if activities is not None:
            instance.activities.set(activities)
        
        # Update activity tracking
        instance.update_activity_tracking()
        
        return instance


class LeadListSerializer(serializers.ModelSerializer):
    """Simplified serializer for lead lists"""
    
    account = serializers.SerializerMethodField(read_only=True)
    contact_name = serializers.SerializerMethodField(read_only=True)
    assigned_to_name = serializers.SerializerMethodField(read_only=True)
    lead_status_display = serializers.CharField(source='get_lead_status_display', read_only=True)
    lead_source_display = serializers.CharField(source='get_lead_source_display', read_only=True)
    number_of_touches = serializers.SerializerMethodField(read_only=True)
    queued_activities_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Lead
        fields = [
            'id',
            'title',
            'lead_source',
            'lead_source_display',
            'lead_status',
            'lead_status_display',
            'account',
            'contact_name',
            'assigned_to_name',
            'number_of_touches',
            'queued_activities_count',
            'is_qualified',
            'created_at',
            'last_activity_date'
        ]
    
    def get_account(self, obj):
        """Return minimal account information"""
        return {
            'id': obj.account.id,
            'company_name': obj.account.company_name
        } if obj.account else None
    
    def get_contact_name(self, obj):
        """Get the full name of the contact"""
        if obj.contact:
            return f"{obj.contact.first_name} {obj.contact.last_name}"
        return None
    
    def get_assigned_to_name(self, obj):
        """Get the full name of assigned user"""
        if obj.assigned_to:
            return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}"
        return None
    
    def get_number_of_touches(self, obj):
        """Get count of activities linked to this lead"""
        return obj.activities.count()
    
    def get_queued_activities_count(self, obj):
        """Get count of planned activities for this lead"""
        return obj.activities.filter(status='PLANNED').count()


class LeadConversionSerializer(serializers.Serializer):
    """Serializer for lead conversion to opportunity"""
    
    opportunity_name = serializers.CharField(required=True)
    opportunity_type = serializers.CharField(required=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    close_date = serializers.DateField(required=True)
    stage = serializers.CharField(required=False, default='QUALIFICATION')
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_opportunity_type(self, value):
        """Validate opportunity type"""
        # This will be validated against Opportunity model choices once created
        valid_types = ['NEW_BUSINESS', 'RENEWAL', 'UPSELL', 'CROSS_SELL']
        if value not in valid_types:
            raise serializers.ValidationError("Invalid opportunity type")
        return value


class LeadActivitySerializer(serializers.ModelSerializer):
    """Serializer for activities related to a lead"""
    
    activity_type_display = serializers.CharField(source='get_activity_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    account_name = serializers.CharField(source='account.company_name', read_only=True)
    owner_name = serializers.SerializerMethodField(read_only=True)
    contacts = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Activity
        fields = [
            'id',
            'title',
            'activity_type',
            'activity_type_display',
            'status',
            'status_display',
            'scheduled_start',
            'completed_at',
            'account_name',
            'owner_name',
            'contacts',
            'outcome_notes'
        ]
    
    def get_owner_name(self, obj):
        """Get the full name of activity owner"""
        if obj.owner:
            return f"{obj.owner.first_name} {obj.owner.last_name}"
        return None
    
    def get_contacts(self, obj):
        """Get contact names for the activity"""
        return [f"{c.first_name} {c.last_name}" for c in obj.contacts.all()]


# Export serializers
__all__ = [
    'LeadSerializer',
    'LeadListSerializer',
    'LeadConversionSerializer',
    'LeadActivitySerializer'
]