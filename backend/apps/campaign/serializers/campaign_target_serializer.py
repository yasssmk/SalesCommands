# apps/campaign/serializers/campaign_target_serializer.py

from rest_framework import serializers
from apps.campaign.models.campaign_target import CampaignTarget
from apps.campaign.models.campaign import Campaign
from apps.accounts.models import Account, Contact
from apps.leads.models import Lead
from apps.opportunities.models import Opportunity
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.client_scope import ClientScopeManager


class CampaignTargetSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Serializer for CampaignTarget model"""
    
    # Read-only fields for display
    target_type = serializers.SerializerMethodField(read_only=True)
    target_name = serializers.SerializerMethodField(read_only=True)
    target_details = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Write fields
    campaign_id = serializers.PrimaryKeyRelatedField(
        queryset=Campaign.objects.all(),
        source='campaign',
        write_only=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign'),
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND
        }
    )
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(),
        source='account',
        write_only=True,
        required=False,
        allow_null=True,
        error_messages={
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND
        }
    )
    contact_id = serializers.PrimaryKeyRelatedField(
        queryset=Contact.objects.all(),
        source='contact',
        write_only=True,
        required=False,
        allow_null=True,
        error_messages={
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND
        }
    )
    lead_id = serializers.PrimaryKeyRelatedField(
        queryset=Lead.objects.all(),
        source='lead',
        write_only=True,
        required=False,
        allow_null=True,
        error_messages={
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND
        }
    )

    target_opportunity_id = serializers.PrimaryKeyRelatedField(
        queryset=Opportunity.objects.all(),
        source='target_opportunity',
        write_only=True,
        required=False,
        allow_null=True,
        error_messages={
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND
        }
    )
    
    class Meta:
        model = CampaignTarget
        fields = [
            'id',
            'campaign',
            'campaign_id',
            
            # Target fields
            'account',
            'contact',
            'lead',
            'target_opportunity',
            'account_id',
            'contact_id',
            'lead_id',
            'target_opportunity_id',
            
            # Display fields
            'target_type',
            'target_name',
            'target_details',
            
            # Status and tracking
            'status',
            'status_display',
            'sequence_created',
            'notes',
            'linked_opportunity',  
            
            # Metadata
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'target_type',
            'target_name',
            'target_details',
            'status_display',
            'created_at',
            'updated_at'
        ]
    
    def get_target_type(self, obj):
        """Return the type of target"""
        return obj.get_target_type()
    
    def get_target_name(self, obj):
        """Return a friendly name for the target"""
        if obj.contact:
            return f"{obj.contact.first_name} {obj.contact.last_name}"
        elif obj.lead:
            return obj.lead.title
        elif obj.target_opportunity:
            return obj.target_opportunity.name
        elif obj.account:
            return obj.account.company_name
        return "Unknown"
    
    def get_target_details(self, obj):
        """Return detailed information about the target"""
        if obj.contact:
            return {
                'type': 'contact',
                'id': obj.contact.id,
                'name': f"{obj.contact.first_name} {obj.contact.last_name}",
                'email': obj.contact.email,
                'phone': obj.contact.phone,
                'account': {
                    'id': obj.contact.account.id,
                    'name': obj.contact.account.company_name
                }
            }
        elif obj.lead:
            return {
                'type': 'lead',
                'id': obj.lead.id,
                'title': obj.lead.title,
                'status': obj.lead.lead_status,
                'contact': {
                    'id': obj.lead.contact.id,
                    'name': f"{obj.lead.contact.first_name} {obj.lead.contact.last_name}"
                },
                'account': {
                    'id': obj.lead.account.id,
                    'name': obj.lead.account.company_name
                }
            }
        elif obj.target_opportunity:
            return {
                'type': 'opportunity',
                'id': obj.target_opportunity.id,
                'name': obj.target_opportunity.name,
                'value': obj.target_opportunity.amount,
                'stage': obj.target_opportunity.stage,
                'account': {
                    'id': obj.target_opportunity.account.id,
                    'name': obj.target_opportunity.account.company_name
                }
            }
        elif obj.account:
            return {
                'type': 'account',
                'id': obj.account.id,
                'name': obj.account.company_name,
                'industry': obj.account.industry,
                'tier': obj.account.tier
            }
        return None
    
    def validate(self, data):
        """Validate that exactly one target type is specified and enforce uniqueness constraints"""
        # Count how many target types are specified
        target_count = sum([
            bool(data.get('account')),
            bool(data.get('contact')),
            bool(data.get('lead')),
            bool(data.get('target_opportunity'))
        ])
        
        if target_count == 0:
            raise StandardizedValidationError(
                "One target (account, contact, lead, or opportunity) must be specified"
            )
        
        if target_count > 1:
            raise StandardizedValidationError(
                "Only one target type can be specified per campaign target"
            )
        
        # Validate client scope and uniqueness for each target type
        campaign = data.get('campaign')
        if campaign:
            client_id = campaign.client_id
            instance_id = getattr(self.instance, 'id', None)
            
            # Validate client scope and uniqueness for account
            account = data.get('account')
            if account:
                # Check client scope
                if str(account.client_id) != str(client_id):
                    raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
                
                # Check uniqueness - account can only be targeted once per campaign
                if CampaignTarget.objects.filter(
                    campaign=campaign,
                    account=account,
                    contact__isnull=True,
                    lead__isnull=True,
                    target_opportunity__isnull=True
                ).exclude(id=instance_id).exists():
                    raise StandardizedValidationError(
                        CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                            fields='Campaign and Account'
                        )
                    )
            
            # Validate client scope and uniqueness for contact
            contact = data.get('contact')
            if contact:
                # Check client scope
                if str(contact.account.client_id) != str(client_id):
                    raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
                
                # Check uniqueness - contact can only be targeted once per campaign
                if CampaignTarget.objects.filter(
                    campaign=campaign,
                    contact=contact
                ).exclude(id=instance_id).exists():
                    raise StandardizedValidationError(
                        CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                            fields='Campaign and Contact'
                        )
                    )
            
            # Validate client scope and uniqueness for lead
            lead = data.get('lead')
            if lead:
                # Check client scope
                if str(lead.client_id) != str(client_id):
                    raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
                
                # Check uniqueness - lead can only be targeted once per campaign
                if CampaignTarget.objects.filter(
                    campaign=campaign,
                    lead=lead
                ).exclude(id=instance_id).exists():
                    raise StandardizedValidationError(
                        CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                            fields='Campaign and Lead'
                        )
                    )
            
            # Validate client scope and uniqueness for opportunity
            target_opportunity = data.get('target_opportunity')
            if target_opportunity:
                # Check client scope
                if str(target_opportunity.client_id) != str(client_id):
                    raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
                
                # Check uniqueness - opportunity can only be targeted once per campaign
                if CampaignTarget.objects.filter(
                    campaign=campaign,
                    target_opportunity=target_opportunity
                ).exclude(id=instance_id).exists():
                    raise StandardizedValidationError(
                        CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                            fields='Campaign and Opportunity'
                        )
                    )
        
        return data
    
    def create(self, validated_data):
        """Create a new campaign target"""
        # Pop the user from context if available
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
            validated_data['updated_by'] = request.user
        
        return CampaignTarget.objects.create(**validated_data)
    
    def update(self, instance, validated_data):
        """Update a campaign target"""
        # Pop the user from context if available
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['updated_by'] = request.user
        
        # Update the instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class CampaignTargetListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing campaign targets"""
    
    target_type = serializers.SerializerMethodField(read_only=True)
    target_name = serializers.SerializerMethodField(read_only=True)
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = CampaignTarget
        fields = [
            'id',
            'campaign',
            'campaign_name',
            'target_type',
            'target_name',
            'status',
            'status_display',
            'activities_generated',
            'created_at'
        ]
    
    def get_target_type(self, obj):
        """Return the type of target"""
        return obj.get_target_type()
    
    def get_target_name(self, obj):
        """Return a friendly name for the target"""
        if obj.contact:
            return f"{obj.contact.first_name} {obj.contact.last_name}"
        elif obj.lead:
            return obj.lead.title
        elif obj.target_opportunity:
            return obj.target_opportunity.name
        elif obj.account:
            return obj.account.company_name
        return "Unknown"


# Export serializers
__all__ = [
    'CampaignTargetSerializer',
    'CampaignTargetListSerializer'
]