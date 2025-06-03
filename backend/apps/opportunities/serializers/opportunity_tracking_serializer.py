# apps/opportunities/serializers/opportunity_tracking_serializer.py

from rest_framework import serializers
from django.utils import timezone
from apps.opportunities.models import (
    Opportunity, OpportunitySource, OpportunityActivity, OpportunityHistory
)
from apps.leads.models import Lead
from apps.accounts.models import Account
from apps.activities.models import Activity
from apps.campaign.models import Campaign, CampaignTarget
from core.exceptions import StandardizedValidationError
from core.client_scope import ClientScopeManager


class OpportunitySourceSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Serializer for tracking the source of an opportunity"""
    
    # Read-only display fields
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)
    conversion_status_display = serializers.CharField(source='get_conversion_status_display', read_only=True)
    source_lead_title = serializers.CharField(source='source_lead.title', read_only=True)
    source_campaign_name = serializers.CharField(source='source_campaign.name', read_only=True)
    partner_name = serializers.CharField(source='partner.company_name', read_only=True)
    created_by_name = serializers.SerializerMethodField(read_only=True)
    assigned_to_name = serializers.SerializerMethodField(read_only=True)
    
    # Write fields for linked objects
    source_lead_id = serializers.PrimaryKeyRelatedField(
        queryset=Lead.objects.all(), source='source_lead', write_only=True, required=False
    )
    source_campaign_id = serializers.PrimaryKeyRelatedField(
        queryset=Campaign.objects.all(), source='source_campaign', write_only=True, required=False
    )
    source_campaign_target_id = serializers.PrimaryKeyRelatedField(
        queryset=CampaignTarget.objects.all(), source='source_campaign_target', write_only=True, required=False
    )
    partner_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(), source='partner', write_only=True, required=False
    )
    
    class Meta:
        model = OpportunitySource
        fields = [
            'id',
            'opportunity',
            'source_type',
            'source_type_display',
            'source_lead_id',
            'source_lead_title',
            'source_campaign_id',
            'source_campaign_name',
            'source_campaign_target_id',
            'partner_id',
            'partner_name',
            'created_by',
            'created_by_name',
            'conversion_status',
            'conversion_status_display',
            'conversion_date',
            'conversion_notes',
            'assigned_to',
            'assigned_to_name',
            'approval_date',
            'rejection_reason',
            'days_as_lead',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'conversion_date',
            'approval_date',
            'days_as_lead',
            'created_at',
            'updated_at'
        ]
    
    def get_created_by_name(self, obj):
        """Get the name of the user who created the opportunity"""
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}"
        return None
    
    def get_assigned_to_name(self, obj):
        """Get the name of the user to whom the opportunity is assigned"""
        if obj.assigned_to:
            return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}"
        return None
    
    def validate(self, data):
        """Validate source data"""
        data = super().validate(data)
        
        # Validate required fields based on source_type
        source_type = data.get('source_type', getattr(self.instance, 'source_type', None))
        
        if source_type == OpportunitySource.SourceType.LEAD and 'source_lead' not in data and not (self.instance and self.instance.source_lead):
            raise StandardizedValidationError(
                "Source lead is required when source type is Lead",
                field_name="source_lead_id"
            )
        
        if source_type == OpportunitySource.SourceType.CAMPAIGN:
            if 'source_campaign' not in data and not (self.instance and self.instance.source_campaign):
                raise StandardizedValidationError(
                    "Source campaign is required when source type is Campaign",
                    field_name="source_campaign_id"
                )
        
        if source_type == OpportunitySource.SourceType.PARTNER and 'partner' not in data and not (self.instance and self.instance.partner):
            raise StandardizedValidationError(
                "Partner is required when source type is Partner",
                field_name="partner_id"
            )
        
        return data
    
    def create(self, validated_data):
        """Create opportunity source with related data"""
        # Set conversion date if not provided
        if 'conversion_date' not in validated_data:
            validated_data['conversion_date'] = timezone.now()
        
        # Calculate days as lead if applicable
        if validated_data.get('source_type') == OpportunitySource.SourceType.LEAD and 'source_lead' in validated_data:
            lead = validated_data['source_lead']
            if lead.created_at:
                delta = validated_data.get('conversion_date', timezone.now()) - lead.created_at
                validated_data['days_as_lead'] = delta.days
        
        # Create the source
        source = super().create(validated_data)
        
        # Create history entry
        source.opportunity.create_history_entry(
            'CREATED', 
            f"Opportunity created from {source.get_source_type_display()}"
        )
        
        return source


class OpportunityActivitySerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Serializer for opportunity-activity links"""
    
    # Read-only display fields
    activity_title = serializers.CharField(source='activity.title', read_only=True)
    activity_type = serializers.CharField(source='activity.activity_type', read_only=True)
    activity_type_display = serializers.CharField(source='activity.get_activity_type_display', read_only=True)
    activity_status = serializers.CharField(source='activity.status', read_only=True)
    activity_status_display = serializers.CharField(source='activity.get_status_display', read_only=True)
    activity_date = serializers.DateTimeField(source='activity.scheduled_start', read_only=True)
    activity_owner = serializers.CharField(source='activity.owner.get_full_name', read_only=True)
    created_by_name = serializers.SerializerMethodField(read_only=True)
    
    # Write fields
    activity_id = serializers.PrimaryKeyRelatedField(
        queryset=Activity.objects.all(), source='activity', write_only=True
    )
    
    class Meta:
        model = OpportunityActivity
        fields = [
            'id',
            'opportunity',
            'activity_id',
            'activity_title',
            'activity_type',
            'activity_type_display',
            'activity_status',
            'activity_status_display',
            'activity_date',
            'activity_owner',
            'is_key_activity',
            'created_by',
            'created_by_name',
            'notes',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at'
        ]
    
    def get_created_by_name(self, obj):
        """Get the name of the user who created the link"""
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}"
        return None
    
    def validate(self, data):
        """Validate activity link data"""
        data = super().validate(data)
        
        # Ensure activity and opportunity belong to the same client
        client_id = self._get_client_id_from_context()
        
        if 'activity' in data and 'opportunity' in data:
            activity = data['activity']
            opportunity = data['opportunity']
            
            if str(activity.client_id) != str(client_id) or str(opportunity.client_id) != str(client_id):
                raise StandardizedValidationError(
                    "Activity and opportunity must belong to the same client"
                )
            
            # Ensure activity is associated with the same account
            if activity.account_id != opportunity.account_id:
                raise StandardizedValidationError(
                    "Activity must be associated with the same account as the opportunity",
                    field_name="activity_id"
                )
        
        return data
    
    def create(self, validated_data):
        """Create activity link with user context"""
        # Set created_by if not provided
        if 'created_by' not in validated_data and self.context.get('request'):
            validated_data['created_by'] = self.context['request'].user
        
        return super().create(validated_data)


class OpportunityHistorySerializer(serializers.ModelSerializer):
    """Serializer for opportunity history records"""
    
    change_type_display = serializers.CharField(source='get_change_type_display', read_only=True)
    changed_by_name = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = OpportunityHistory
        fields = [
            'id',
            'opportunity',
            'change_type',
            'change_type_display',
            'description',
            'details',
            'change_date',
            'changed_by',
            'changed_by_name'
        ]
        read_only_fields = fields  # All fields are read-only
    
    def get_changed_by_name(self, obj):
        """Get the name of the user who made the change"""
        if obj.changed_by:
            return f"{obj.changed_by.first_name} {obj.changed_by.last_name}"
        return None


class LeadConversionSerializer(serializers.Serializer):
    """Serializer for converting leads to opportunities"""
    
    # Basic opportunity data
    title = serializers.CharField(required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    opportunity_type = serializers.ChoiceField(
        choices=Opportunity.OpportunityType.choices,
        default=Opportunity.OpportunityType.NEW_BUSINESS
    )
    expected_close_date = serializers.DateField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    # Conversion workflow
    assign_to = serializers.PrimaryKeyRelatedField(
        queryset=None,  # Will be set dynamically
        required=False,
        allow_null=True
    )
    conversion_notes = serializers.CharField(required=False, allow_blank=True)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Dynamically set the queryset for assign_to
        from end_users.models import User
        
        if 'context' in kwargs and 'client_id' in kwargs['context']:
            client_id = kwargs['context']['client_id']
            self.fields['assign_to'].queryset = User.objects.filter(client_id=client_id)
        else:
            self.fields['assign_to'].queryset = User.objects.all()
    
    def validate_expected_close_date(self, value):
        """Validate expected close date is in the future"""
        if value < timezone.now().date():
            raise serializers.ValidationError("Expected close date must be in the future")
        return value