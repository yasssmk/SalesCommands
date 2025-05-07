# apps/campaign/serializers/campaign_target_serializer.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.campaign.models.campaign_target import CampaignTarget
from apps.campaign.models.campaign import Campaign
from apps.accounts.models import Account

class AccountSummarySerializer(serializers.ModelSerializer):
    """Serializer for the account summary in campaign targets"""
    class Meta:
        model = Account
        fields = ['id', 'company_name', 'industry', 'company_size']
        read_only_fields = fields

class CampaignTargetSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Serializer for CampaignTarget model"""
    
    # Fields for write operations
    campaign_id = serializers.PrimaryKeyRelatedField(
        queryset=Campaign.objects.all(),
        source='campaign',
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign'),
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND
        }
    )
    
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(),
        source='account',
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Account'),
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND
        }
    )
    
    # Fields for read operations
    account_details = AccountSummarySerializer(source='account', read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = CampaignTarget
        fields = [
            'id', 'campaign', 'campaign_id', 'account', 'account_id', 
            'account_details', 'status', 'status_display', 'sequence_created',
            'expected_value', 'notes', 'opportunity', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'status_display']
    
    def get_status_display(self, obj):
        """Get the display name for status"""
        return obj.get_status_display()
    
    def validate(self, data):
        """Complete validation of CampaignTarget data"""
        try:
            # Get client_id for validations
            client_id = self._get_client_id_from_context()
            
            # Validate client scope for campaign and account
            if 'campaign' in data:
                campaign = data['campaign']
                self.validate_client_id(campaign)
                
                # Validate that the user owns the campaign or has permissions
                request = self.context.get('request')
                if request and hasattr(request, 'user'):
                    current_user = request.user
                    
                    # Check if user is the campaign owner
                    if campaign.owner.id != current_user.id:
                        raise StandardizedValidationError(
                            CoreErrorMessages.PERMISSION_DENIED
                        )
            
            if 'account' in data:
                account = data['account']
                self.validate_client_id(account)
            
            # Validate uniqueness of account within campaign
            if 'campaign' in data and 'account' in data:
                campaign = data['campaign']
                account = data['account']
                
                # Skip check if this is an update and campaign/account didn't change
                instance = getattr(self, 'instance', None)
                if instance:
                    if instance.campaign_id == campaign.id and instance.account_id == account.id:
                        return super().validate(data)
                
                # Check if this account is already a target for this campaign
                if CampaignTarget.objects.filter(
                    campaign=campaign, 
                    account=account
                ).exists():
                    raise StandardizedValidationError(
                        _("This account is already a target for this campaign")
                    )
            
            return super().validate(data)
            
        except serializers.ValidationError as e:
            raise StandardizedValidationError(e.detail)
    
    def create(self, validated_data):
        """Create a new CampaignTarget instance"""
        # Set initial status to PENDING
        validated_data['status'] = CampaignTarget.Status.PENDING
        
        return super().create(validated_data)