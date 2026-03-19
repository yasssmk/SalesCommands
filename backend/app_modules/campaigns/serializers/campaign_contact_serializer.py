# app_modules/campaigns/serializers/campaign_contact_serializer.py
"""
Serializers for CampaignContact pivot model.

3 serializers:
- CampaignContactListSerializer: lightweight for nested display in CampaignAccount
- CampaignContactDetailSerializer: full retrieve with contact details
- CampaignContactSerializer: CRUD (campaign_account_id + contact_id)
"""

from rest_framework import serializers

from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages, CampaignModuleErrorMessages
from core.exceptions import StandardizedValidationError

from app_modules.contacts.models import Contact

from ..models import (
    CampaignAccount,
    CampaignContact,
)


# ============================================================================
# HELPER
# ============================================================================

class CampaignContactMinimalContactSerializer(serializers.ModelSerializer):
    """Minimal contact fields for campaign contact responses."""

    full_name = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Contact
        fields = [
            'id', 'first_name', 'last_name', 'full_name',
            'email', 'phone_number', 'job_title', 'department_name',
        ]
        read_only_fields = fields

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()

    def get_department_name(self, obj):
        if obj.standard_department:
            return obj.standard_department.get_name_display()
        return None


# ============================================================================
# LIST SERIALIZER
# ============================================================================

class CampaignContactListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Lightweight serializer for nested display inside CampaignAccountDetailSerializer.
    """

    status_display = serializers.SerializerMethodField(read_only=True)
    contact_name = serializers.SerializerMethodField(read_only=True)
    activities_count = serializers.SerializerMethodField(read_only=True)
    account_name = serializers.SerializerMethodField(read_only=True)
    has_on_hold = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CampaignContact
        fields = [
            'id',
            'contact', 'contact_name',
            'account_name',
            'status', 'status_display',
            'callback_date',
            'activities_generated',
            'activities_count',
            'has_on_hold',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_status_display(self, obj):
        return obj.get_status_display() if obj.status else None

    def get_contact_name(self, obj):
        if obj.contact:
            return f"{obj.contact.first_name or ''} {obj.contact.last_name or ''}".strip()
        return None

    def get_activities_count(self, obj):
        if hasattr(obj, '_activities_count'):
            return obj._activities_count
        return obj.activities.count()
    
    def get_account_name(self, obj):
        try:
            return obj.campaign_account.account.company_name
        except Exception:
            return None
    
    def get_has_on_hold(self, obj):
        from app_modules.activities.constants import ActivityStatus
        if hasattr(obj, '_prefetched_objects_cache') and 'activities' in obj._prefetched_objects_cache:
            return len(obj._prefetched_objects_cache['activities']) > 0
        return obj.activities.filter(status=ActivityStatus.ON_HOLD).exists()


# ============================================================================
# DETAIL SERIALIZER
# ============================================================================

class CampaignContactDetailSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Full detail serializer — used in retrieve and action responses.
    """

    status_display = serializers.SerializerMethodField(read_only=True)
    contact = CampaignContactMinimalContactSerializer(read_only=True)
    campaign_account_id = serializers.UUIDField(source='campaign_account.id', read_only=True)
    account_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CampaignContact
        fields = [
            'id',
            'campaign_account_id',
            'account_name',
            'contact',
            'status', 'status_display',
            'callback_date',
            'activities_generated',
            'notes',
            'created_by', 'updated_by',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_status_display(self, obj):
        return obj.get_status_display() if obj.status else None

    def get_account_name(self, obj):
        try:
            return obj.campaign_account.account.company_name
        except Exception:
            return None


# ============================================================================
# CRUD SERIALIZER
# ============================================================================

class CampaignContactSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for CampaignContact create operations.

    Validates:
        - campaign_account belongs to same client
        - contact belongs to same client and to the account
        - unique (campaign_account, contact) per client
    """

    campaign_account_id = serializers.UUIDField(
        source='campaign_account',
        write_only=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign Account'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Campaign Account ID'),
        },
    )

    contact_id = serializers.UUIDField(
        source='contact',
        write_only=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Contact'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Contact ID'),
        },
    )

    # Read-only display
    status_display = serializers.SerializerMethodField(read_only=True)
    contact_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CampaignContact
        fields = [
            # Write
            'campaign_account_id', 'contact_id',
            'notes',
            # Read-only
            'id', 'status', 'status_display',
            'contact_name',
            'callback_date', 'activities_generated',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'status', 'status_display',
            'contact_name',
            'callback_date', 'activities_generated',
            'created_at', 'updated_at',
        ]

    def get_status_display(self, obj):
        return obj.get_status_display() if obj.status else None

    def get_contact_name(self, obj):
        if obj.contact:
            return f"{obj.contact.first_name or ''} {obj.contact.last_name or ''}".strip()
        return None

    def validate(self, attrs):
        try:
            client_id = self._get_client_id_from_context()
            attrs['client_id'] = client_id

            ca_id = attrs.get('campaign_account')
            contact_id = attrs.get('contact')

            # Validate campaign_account belongs to client
            try:
                campaign_account = CampaignAccount.objects.get(
                    id=ca_id, client_id=client_id
                )
                attrs['campaign_account'] = campaign_account
            except CampaignAccount.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

            # Validate contact belongs to client and to the account
            try:
                contact = Contact.objects.get(id=contact_id, client_id=client_id)
                if contact.account_id != campaign_account.account_id:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field='Contact (must belong to the campaign account)'
                        )
                    )
                attrs['contact'] = contact
            except Contact.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

            # Uniqueness check
            qs = CampaignContact.objects.filter(
                campaign_account=campaign_account,
                contact=contact,
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise StandardizedValidationError(
                    CampaignModuleErrorMessages.ACCOUNT_ALREADY_IN_CAMPAIGN
                )

            return attrs

        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            )

    def create(self, validated_data):
        user = self.context['request'].user if self.context.get('request') else None
        instance = CampaignContact(**validated_data)
        instance.save(user=user)
        return instance