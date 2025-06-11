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
        source='campaign',
        write_only=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign'),
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Campaign ID')
        }
    )
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(),
        source='account',
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
        source='contact',
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
        source='lead',
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
        source='target_opportunity',
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
            'activities_generated',
            'callback_date',
            'no_answer_count',
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
                    'account': {
                        'id': obj.contact.account.id,
                        'name': obj.contact.account.company_name
                    } if obj.contact.account else None
                }
            elif obj.lead:
                return {
                    'type': 'lead',
                    'id': obj.lead.id,
                    'title': obj.lead.title,
                    'status': getattr(obj.lead, 'lead_status', None),
                    'contact': {
                        'id': obj.lead.contact.id,
                        'name': f"{obj.lead.contact.first_name} {obj.lead.contact.last_name}".strip()
                    } if obj.lead.contact else None,
                    'account': {
                        'id': obj.lead.account.id,
                        'name': obj.lead.account.company_name
                    } if obj.lead.account else None
                }
            elif obj.target_opportunity:
                return {
                    'type': 'opportunity',
                    'id': obj.target_opportunity.id,
                    'name': obj.target_opportunity.name,
                    'value': getattr(obj.target_opportunity, 'amount', None),
                    'stage': getattr(obj.target_opportunity, 'stage', None),
                    'account': {
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
                bool(data.get('account')),
                bool(data.get('contact')),
                bool(data.get('lead')),
                bool(data.get('target_opportunity'))
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
            campaign = data.get('campaign')
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
            account = data.get('account')
            if account:
                self._validate_account_target(account, campaign, client_id, instance_id)
            
            # Validate client scope and uniqueness for contact
            contact = data.get('contact')
            if contact:
                self._validate_contact_target(contact, campaign, client_id, instance_id)
            
            # Validate client scope and uniqueness for lead
            lead = data.get('lead')
            if lead:
                self._validate_lead_target(lead, campaign, client_id, instance_id)
            
            # Validate client scope and uniqueness for opportunity
            target_opportunity = data.get('target_opportunity')
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
                campaign=campaign,
                account=account,
                contact__isnull=True,
                lead__isnull=True,
                target_opportunity__isnull=True
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
                campaign=campaign,
                contact=contact
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
                campaign=campaign,
                lead=lead
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
                campaign=campaign,
                target_opportunity=target_opportunity
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