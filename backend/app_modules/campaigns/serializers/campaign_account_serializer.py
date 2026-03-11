# app_modules/campaigns/serializers/campaign_account_serializer.py
"""
Serializers for CampaignAccount pivot model.

3 serializers following CompanyAccount / DecisionStep patterns:
- CampaignAccountListSerializer: lightweight for table display
- CampaignAccountDetailSerializer: full retrieve with nested relations
- CampaignAccountSerializer: CRUD with M2M target_departments / target_contacts
"""

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages, CampaignModuleErrorMessages
from core.exceptions import StandardizedValidationError

from app_modules.accounts.models import CompanyAccount
from app_modules.contacts.models import Contact
from app_modules.core_modules.models import StandardDepartment
from app_modules.core_modules.serializers import StandardDepartmentSerializer

from ..models import (
    Campaign,
    CampaignAccount,
    CampaignAccountStatus,
)
from ..config.settings import CONFIG


# ============================================================================
# HELPER SERIALIZERS
# ============================================================================

class CampaignAccountAccountSerializer(serializers.ModelSerializer):
    """Minimal account serializer for campaign account responses."""

    class Meta:
        model = CompanyAccount
        fields = ['id', 'company_name', 'industry', 'city', 'country', 'type']
        read_only_fields = fields


class CampaignAccountContactSerializer(serializers.ModelSerializer):
    """Minimal contact serializer for campaign account responses."""

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
# LIST SERIALIZER (Performance optimized)
# ============================================================================

class CampaignAccountListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Lightweight serializer for campaign account lists (performance optimized).

    Principles:
        - Minimum fields for table display
        - SerializerMethodField for relations (avoid N+1)
        - No deep nested serializers
    """

    # Display fields
    account_name = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)

    # Computed aggregates
    contacts_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CampaignAccount
        fields = [
            # Identity
            'id',

            # Relations (simple)
            'campaign', 'account', 'account_name',

            # Status
            'status', 'status_display',

            # Aggregate
            'contacts_count',

            # Timestamps
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_account_name(self, obj):
        """Return account company name without extra query (select_related)."""
        if obj.account:
            return obj.account.company_name
        return None

    def get_status_display(self, obj):
        """Return human-readable status."""
        return obj.get_status_display() if obj.status else None

    def get_contacts_count(self, obj):
        """Return count of targeted contacts."""
        if hasattr(obj, '_contacts_count'):
            return obj._contacts_count
        return obj.target_contacts.count()


# ============================================================================
# DETAIL SERIALIZER (Full retrieve)
# ============================================================================

class CampaignAccountDetailSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Complete serializer for campaign account detail view.

    Includes nested account, targeting filters, and per-contact progress rows.
    """

    # Display fields
    campaign_name = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)

    # Nested relations (read-only)
    account = CampaignAccountAccountSerializer(read_only=True)
    target_departments = StandardDepartmentSerializer(many=True, read_only=True)
    target_contacts = CampaignAccountContactSerializer(many=True, read_only=True)

    # Per-contact progress rows (lazy import to avoid circular)
    campaign_contacts = serializers.SerializerMethodField(read_only=True)

    # Computed
    contacts_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CampaignAccount
        fields = [
            # Identity
            'id',

            # Relations
            'campaign', 'campaign_name',
            'account',

            # Status
            'status', 'status_display',

            # Targeting
            'target_departments', 'target_contacts',
            'contacts_count',

            # Per-contact progress
            'campaign_contacts',

            # Details
            'notes',

            # Audit
            'created_by', 'updated_by',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_campaign_name(self, obj):
        if obj.campaign:
            return obj.campaign.name
        return None

    def get_status_display(self, obj):
        return obj.get_status_display() if obj.status else None

    def get_contacts_count(self, obj):
        return obj.target_contacts.count()

    def get_campaign_contacts(self, obj):
        """Return per-contact progress rows (lazy import avoids circular)."""
        from .campaign_contact_serializer import CampaignContactListSerializer
        qs = obj.campaign_contacts.select_related('contact').all()
        return CampaignContactListSerializer(
            qs, many=True, context=self.context
        ).data


# ============================================================================
# MAIN SERIALIZER (CRUD)
# ============================================================================

class CampaignAccountSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for CampaignAccount CRUD operations.

    Supports:
        - M2M write for target_departments and target_contacts
        - Account uniqueness per campaign validation
        - Client scope validation for all FK references
    """

    # FK write fields
    campaign_id = serializers.UUIDField(
        source='campaign',
        write_only=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Campaign ID'),
        },
    )

    account_id = serializers.UUIDField(
        source='account',
        write_only=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Account'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Account ID'),
        },
    )

    # M2M write fields (ListField pattern — same as DecisionStep)
    department_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True,
    )

    contact_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True,
    )

    # Read-only display
    account_name = serializers.SerializerMethodField(read_only=True)
    campaign_name = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CampaignAccount
        fields = [
            # Write FK
            'campaign_id', 'account_id',

            # M2M write
            'department_ids', 'contact_ids',

            # Scalar write
            'notes',

            # Read-only display
            'id', 'account_name', 'campaign_name',
            'status', 'status_display',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'account_name', 'campaign_name',
            'status', 'status_display',
            'created_at', 'updated_at',
        ]

    # ------------------------------------------------------------------
    # Read-only helpers
    # ------------------------------------------------------------------

    def get_account_name(self, obj):
        if obj.account:
            return obj.account.company_name
        return None

    def get_campaign_name(self, obj):
        if obj.campaign:
            return obj.campaign.name
        return None

    def get_status_display(self, obj):
        return obj.get_status_display() if obj.status else None

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, attrs):
        """
        Global validation for CampaignAccount.

        Rules:
            - Campaign and Account belong to same client
            - Account unique per campaign (client-scoped)
            - Contacts belong to the same account
            - Departments are valid StandardDepartment entries
        """
        try:
            client_id = self._get_client_id_from_context()
            attrs['client_id'] = client_id

            campaign_id = attrs.get('campaign')
            account_id = attrs.get('account')

            # Validate campaign belongs to same client
            if campaign_id:
                self._validate_campaign(campaign_id, client_id)

            # Validate account belongs to same client
            if account_id:
                self._validate_account(account_id, client_id)

            # Validate uniqueness: (campaign, account) per client
            if campaign_id and account_id:
                self._validate_unique_enrollment(campaign_id, account_id, client_id)

            # Validate contacts belong to this account
            contact_ids = attrs.get('contact_ids', [])
            if contact_ids and account_id:
                self._validate_contacts(contact_ids, account_id, client_id)

            # Validate departments exist
            department_ids = attrs.get('department_ids', [])
            if department_ids:
                self._validate_departments(department_ids)

            return attrs

        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            )

    # ------------------------------------------------------------------
    # Private validation helpers
    # ------------------------------------------------------------------

    def _validate_campaign(self, campaign_id, client_id):
        """Validate campaign exists and belongs to same client."""
        try:
            campaign = Campaign.objects.get(id=campaign_id)
            if str(campaign.client_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        except Campaign.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

    def _validate_account(self, account_id, client_id):
        """Validate account exists and belongs to same client."""
        try:
            account = CompanyAccount.objects.get(id=account_id)
            if str(account.client_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        except CompanyAccount.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

    def _validate_unique_enrollment(self, campaign_id, account_id, client_id):
        """Validate account is not already enrolled in this campaign."""
        queryset = CampaignAccount.objects.filter(
            campaign_id=campaign_id,
            account_id=account_id,
            client_id=client_id,
        )
        # Exclude current instance on update
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.ACCOUNT_ALREADY_IN_CAMPAIGN
            )

    def _validate_contacts(self, contact_ids, account_id, client_id):
        """Validate all contacts exist and belong to the specified account."""
        contacts = Contact.objects.filter(
            id__in=contact_ids,
            client_id=client_id,
        )
        if contacts.count() != len(contact_ids):
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='Contact IDs (some not found)')
            )
        # All contacts must belong to the target account
        mismatched = contacts.exclude(account_id=account_id).count()
        if mismatched > 0:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field='Contact IDs (contacts must belong to the target account)'
                )
            )

    def _validate_departments(self, department_ids):
        """Validate all department IDs exist."""
        count = StandardDepartment.objects.filter(id__in=department_ids).count()
        if count != len(department_ids):
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='Department IDs (some not found)')
            )

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(self, validated_data):
        """
        Create CampaignAccount with M2M target_departments and target_contacts.

        Flow:
            1. Extract M2M IDs
            2. Resolve FK (campaign, account)
            3. Create instance
            4. Set M2M relations
        """
        user = self.context.get('request').user if self.context.get('request') else None

        # Extract M2M data before model creation
        department_ids = validated_data.pop('department_ids', [])
        contact_ids = validated_data.pop('contact_ids', [])
        client_id = validated_data.pop('client_id', None)

        # Resolve FK IDs to instances
        campaign_id = validated_data.pop('campaign')
        account_id = validated_data.pop('account')
        validated_data['campaign'] = Campaign.objects.get(id=campaign_id)
        validated_data['account'] = CompanyAccount.objects.get(id=account_id)

        # Create instance
        instance = CampaignAccount(**validated_data)
        instance.save(user=user, client_id=client_id)

        # Set M2M relations
        if department_ids:
            departments = StandardDepartment.objects.filter(id__in=department_ids)
            instance.target_departments.set(departments)

        if contact_ids:
            contacts = Contact.objects.filter(id__in=contact_ids)
            instance.target_contacts.set(contacts)

        return instance

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, instance, validated_data):
        """
        Update CampaignAccount with M2M handling.

        M2M fields are replaced entirely when provided (same as DecisionStep).
        """
        user = self.context.get('request').user if self.context.get('request') else None

        # Extract M2M data
        department_ids = validated_data.pop('department_ids', None)
        contact_ids = validated_data.pop('contact_ids', None)

        # Remove FK fields that should not change on update
        validated_data.pop('campaign', None)
        validated_data.pop('account', None)
        validated_data.pop('client_id', None)

        # Update scalar fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save(user=user)

        # Update M2M if provided (replace entirely)
        if department_ids is not None:
            departments = StandardDepartment.objects.filter(id__in=department_ids)
            instance.target_departments.set(departments)

        if contact_ids is not None:
            contacts = Contact.objects.filter(id__in=contact_ids)
            instance.target_contacts.set(contacts)

        return instance