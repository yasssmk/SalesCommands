# apps/campaign/serializers/campaign_target_serializer.py - Validation methods update

from rest_framework import serializers
from apps.campaign.models.campaign_target import CampaignTarget
from apps.campaign.models.campaign import Campaign
from apps.accounts.models import Account, Contact
from apps.leads.models import Lead
from apps.opportunities.models import Opportunity
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.client_scope import ClientScopeManager

# Import configuration variables
from apps.campaign.config.variables import (
    FIELD_NAMES,
    SERIALIZER_CONFIGS
)


class CampaignTargetSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Serializer for CampaignTarget model with standardized validation"""
    
    # Read-only fields for display
    target_type = serializers.SerializerMethodField(read_only=True)
    target_name = serializers.SerializerMethodField(read_only=True)
    target_details = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Write fields with improved error messages
    campaign_id = serializers.PrimaryKeyRelatedField(
        queryset=Campaign.objects.all(),
        source=FIELD_NAMES['CAMPAIGN'],
        write_only=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign'),
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Campaign ID')
        }
    )
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(),
        source=FIELD_NAMES['ACCOUNT'],
        write_only=True,
        required=False,
        allow_null=True,
        error_messages={
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Account ID')
        }
    )
    contact_id = serializers.PrimaryKeyRelatedField(
        queryset=Contact.objects.all(),
        source=FIELD_NAMES['CONTACT'],
        write_only=True,
        required=False,
        allow_null=True,
        error_messages={
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Contact ID')
        }
    )
    lead_id = serializers.PrimaryKeyRelatedField(
        queryset=Lead.objects.all(),
        source=FIELD_NAMES['LEAD'],
        write_only=True,
        required=False,
        allow_null=True,
        error_messages={
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Lead ID')
        }
    )

    target_opportunity_id = serializers.PrimaryKeyRelatedField(
        queryset=Opportunity.objects.all(),
        source=FIELD_NAMES['TARGET_OPPORTUNITY'],
        write_only=True,
        required=False,
        allow_null=True,
        error_messages={
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Opportunity ID')
        }
    )
    
    # Status field with validation
    status = serializers.ChoiceField(
        choices=CampaignTarget.Status.choices,
        required=False,
        error_messages={
            'invalid_choice': CoreErrorMessages.INVALID_FIELD.format(field='Status (invalid choice)')
        }
    )
    
    class Meta:
        model = CampaignTarget
        fields = SERIALIZER_CONFIGS['TARGET_FIELDS']
        read_only_fields = SERIALIZER_CONFIGS['TARGET_READ_ONLY_FIELDS']
    
    def get_target_type(self, obj):
        """Return the type of target"""
        try:
            return obj.get_target_type()
        except Exception:
            return None
    
    def get_target_name(self, obj):
        """Return a friendly name for the target"""
        try:
            if obj.contact:
                return f"{obj.contact.first_name} {obj.contact.last_name}".strip()
            elif obj.lead:
                return obj.lead.title
            elif obj.target_opportunity:
                return obj.target_opportunity.name
            elif obj.account:
                return obj.account.company_name
            return "Unknown"
        except Exception:
            return "Unknown"
    
    def get_target_details(self, obj):
        """Return detailed information about the target"""
        try:
            if obj.contact:
                return {
                    'type': 'contact',
                    'id': obj.contact.id,
                    'name': f"{obj.contact.first_name} {obj.contact.last_name}".strip(),
                    'email': getattr(obj.contact, 'email', None),
                    'phone': getattr(obj.contact, 'phone', None),
                    FIELD_NAMES['ACCOUNT']: {
                        'id': obj.contact.account.id,
                        'name': obj.contact.account.company_name
                    } if obj.contact.account else None
                }
            elif obj.lead:
                return {
                    'type': 'lead',
                    'id': obj.lead.id,
                    'title': obj.lead.title,
                    FIELD_NAMES['STATUS']: getattr(obj.lead, 'lead_status', None),
                    FIELD_NAMES['CONTACT']: {
                        'id': obj.lead.contact.id,
                        'name': f"{obj.lead.contact.first_name} {obj.lead.contact.last_name}".strip()
                    } if obj.lead.contact else None,
                    FIELD_NAMES['ACCOUNT']: {
                        'id': obj.lead.account.id,
                        'name': obj.lead.account.company_name
                    } if obj.lead.account else None
                }
            elif obj.target_opportunity:
                return {
                    'type': 'opportunity',
                    'id': obj.target_opportunity.id,
                    'name': obj.target_opportunity.name,
                    FIELD_NAMES['VALUE']: getattr(obj.target_opportunity, 'amount', None),
                    'stage': getattr(obj.target_opportunity, 'stage', None),
                    FIELD_NAMES['ACCOUNT']: {
                        'id': obj.target_opportunity.account.id,
                        'name': obj.target_opportunity.account.company_name
                    } if obj.target_opportunity.account else None
                }
            elif obj.account:
                return {
                    'type': 'account',
                    'id': obj.account.id,
                    'name': obj.account.company_name,
                    'industry': getattr(obj.account, 'industry', None),
                    'tier': getattr(obj.account, 'tier', None)
                }
            return None
        except Exception:
            return None
    
    def validate(self, data):
        """Validate that exactly one target type is specified and enforce uniqueness constraints"""
        try:
            # Count how many target types are specified
            target_count = sum([
                bool(data.get(FIELD_NAMES['ACCOUNT'])),
                bool(data.get(FIELD_NAMES['CONTACT'])),
                bool(data.get(FIELD_NAMES['LEAD'])),
                bool(data.get(FIELD_NAMES['TARGET_OPPORTUNITY']))
            ])
            
            if target_count == 0:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(
                        field="Target (one of: account, contact, lead, or opportunity)"
                    )
                )
            
            if target_count > 1:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field="Target selection (only one target type can be specified per campaign target)"
                    )
                )
            
            # Validate client scope and uniqueness for each target type
            campaign = data.get(FIELD_NAMES['CAMPAIGN'])
            if campaign:
                try:
                    client_id = campaign.client_id
                    instance_id = getattr(self.instance, 'id', None)
                    
                    # Validate client scope and uniqueness for each target type
                    self._validate_target_client_scope_and_uniqueness(
                        data, campaign, client_id, instance_id
                    )
                    
                except Exception as e:
                    raise StandardizedValidationError(
                        CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Campaign validation failed")
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
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Target validation failed")
            )
    
    def _validate_target_client_scope_and_uniqueness(self, data, campaign, client_id, instance_id):
        """Validate client scope and uniqueness for each target type"""
        try:
            # Validate client scope and uniqueness for account
            account = data.get(FIELD_NAMES['ACCOUNT'])
            if account:
                self._validate_account_target(account, campaign, client_id, instance_id)
            
            # Validate client scope and uniqueness for contact
            contact = data.get(FIELD_NAMES['CONTACT'])
            if contact:
                self._validate_contact_target(contact, campaign, client_id, instance_id)
            
            # Validate client scope and uniqueness for lead
            lead = data.get(FIELD_NAMES['LEAD'])
            if lead:
                self._validate_lead_target(lead, campaign, client_id, instance_id)
            
            # Validate client scope and uniqueness for opportunity
            target_opportunity = data.get(FIELD_NAMES['TARGET_OPPORTUNITY'])
            if target_opportunity:
                self._validate_opportunity_target(target_opportunity, campaign, client_id, instance_id)
                
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Target scope validation failed")
            )
    
    def _validate_account_target(self, account, campaign, client_id, instance_id):
        """Validate account target client scope and uniqueness"""
        try:
            # Check client scope
            if str(account.client_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
            
            # Check uniqueness - account can only be targeted once per campaign
            existing = CampaignTarget.objects.filter(
                **{
                    FIELD_NAMES['CAMPAIGN']: campaign,
                    FIELD_NAMES['ACCOUNT']: account,
                    f"{FIELD_NAMES['CONTACT']}__isnull": True,
                    f"{FIELD_NAMES['LEAD']}__isnull": True,
                    f"{FIELD_NAMES['TARGET_OPPORTUNITY']}__isnull": True
                }
            ).exclude(id=instance_id)
            
            if existing.exists():
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Account Target (account '{account.company_name}' is already targeted by this campaign)"
                    )
                )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Account validation failed")
            )
    
    def _validate_contact_target(self, contact, campaign, client_id, instance_id):
        """Validate contact target client scope and uniqueness"""
        try:
            # Check client scope
            if str(contact.account.client_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
            
            # Check uniqueness - contact can only be targeted once per campaign
            existing = CampaignTarget.objects.filter(
                **{
                    FIELD_NAMES['CAMPAIGN']: campaign,
                    FIELD_NAMES['CONTACT']: contact
                }
            ).exclude(id=instance_id)
            
            if existing.exists():
                contact_name = f"{contact.first_name} {contact.last_name}".strip()
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Contact Target (contact '{contact_name}' is already targeted by this campaign)"
                    )
                )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Contact validation failed")
            )
    
    def _validate_lead_target(self, lead, campaign, client_id, instance_id):
        """Validate lead target client scope and uniqueness"""
        try:
            # Check client scope
            if str(lead.client_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
            
            # Check uniqueness - lead can only be targeted once per campaign
            existing = CampaignTarget.objects.filter(
                **{
                    FIELD_NAMES['CAMPAIGN']: campaign,
                    FIELD_NAMES['LEAD']: lead
                }
            ).exclude(id=instance_id)
            
            if existing.exists():
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Lead Target (lead '{lead.title}' is already targeted by this campaign)"
                    )
                )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Lead validation failed")
            )
    
    def _validate_opportunity_target(self, target_opportunity, campaign, client_id, instance_id):
        """Validate opportunity target client scope and uniqueness"""
        try:
            # Check client scope
            if str(target_opportunity.client_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
            
            # Check uniqueness - opportunity can only be targeted once per campaign
            existing = CampaignTarget.objects.filter(
                **{
                    FIELD_NAMES['CAMPAIGN']: campaign,
                    FIELD_NAMES['TARGET_OPPORTUNITY']: target_opportunity
                }
            ).exclude(id=instance_id)
            
            if existing.exists():
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Opportunity Target (opportunity '{target_opportunity.name}' is already targeted by this campaign)"
                    )
                )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Opportunity validation failed")
            )
    
    def create(self, validated_data):
        """Create a new campaign target with standardized error handling"""
        try:
            # Set the user from context if available
            request = self.context.get('request')
            if request and hasattr(request, 'user'):
                validated_data['created_by'] = request.user
                validated_data['updated_by'] = request.user
            
            return CampaignTarget.objects.create(**validated_data)
            
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Target creation failed")
            )
    
    def update(self, instance, validated_data):
        """Update a campaign target with standardized error handling"""
        try:
            # Set the user from context if available
            request = self.context.get('request')
            if request and hasattr(request, 'user'):
                validated_data['updated_by'] = request.user
            
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
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Target update failed")
            )


class CampaignTargetListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing campaign targets"""
    
    target_type = serializers.SerializerMethodField(read_only=True)
    target_name = serializers.SerializerMethodField(read_only=True)
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = CampaignTarget
        fields = SERIALIZER_CONFIGS['TARGET_LIST_FIELDS']
    
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