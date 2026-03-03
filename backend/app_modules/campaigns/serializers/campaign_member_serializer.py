# app_modules/campaigns/serializers/campaign_member_serializer.py
"""
Serializers for CampaignMember model.

2 serializers following CompanyAccount / CampaignAccount patterns:
- CampaignMemberListSerializer: lightweight for table display
- CampaignMemberSerializer: create/update with validation

Constraints enforced:
- unique_together: (campaign, user, role, client_id)
- UniqueConstraint: only one is_primary_owner=True per campaign
- User must belong to same client
- Campaign must not be in final state
"""

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages, CampaignModuleErrorMessages
from core.exceptions import StandardizedValidationError

from end_users.models import User

from ..models import (
    Campaign,
    CampaignMember,
)
from ..config.settings import CONFIG


# ============================================================================
# HELPER SERIALIZERS
# ============================================================================

class MemberUserSerializer(serializers.ModelSerializer):
    """Minimal user serializer for member responses."""

    full_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name']
        read_only_fields = fields

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip() or obj.email


# ============================================================================
# LIST SERIALIZER (Performance optimized)
# ============================================================================

class CampaignMemberListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Lightweight serializer for campaign member lists (performance optimized).

    Principles:
        - Minimum fields for table display
        - SerializerMethodField for relations (avoid N+1 with select_related)
        - No deep nested serializers
    """

    # Display fields
    campaign_name = serializers.SerializerMethodField(read_only=True)
    user_name = serializers.SerializerMethodField(read_only=True)
    user_email = serializers.SerializerMethodField(read_only=True)
    role_display = serializers.SerializerMethodField(read_only=True)
    added_by_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CampaignMember
        fields = [
            # Identity
            'id',

            # Relations (display)
            'campaign', 'campaign_name',
            'user', 'user_name', 'user_email',

            # Role
            'role', 'role_display',
            'is_primary_owner',

            # Audit
            'added_at', 'added_by_name',
        ]
        read_only_fields = fields

    def get_campaign_name(self, obj):
        """Return campaign name (relies on select_related)."""
        return obj.campaign.name if obj.campaign else None

    def get_user_name(self, obj):
        """Return user full name (relies on select_related)."""
        if not obj.user:
            return None
        return f"{obj.user.first_name or ''} {obj.user.last_name or ''}".strip() or obj.user.email

    def get_user_email(self, obj):
        """Return user email."""
        return obj.user.email if obj.user else None

    def get_role_display(self, obj):
        """Return human-readable role."""
        return obj.get_role_display() if obj.role else None

    def get_added_by_name(self, obj):
        """Return added_by full name (relies on select_related)."""
        if not obj.added_by:
            return None
        return f"{obj.added_by.first_name or ''} {obj.added_by.last_name or ''}".strip() or obj.added_by.email


# ============================================================================
# CREATE / UPDATE SERIALIZER
# ============================================================================

class CampaignMemberSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for CampaignMember create and update operations.

    Supports:
        - FK write via campaign_id / user_id
        - Validation: unique (campaign, user, role), one primary_owner per campaign
        - User and campaign belong to same client
        - Campaign not in final state
    """

    # FK write fields
    campaign_id = serializers.UUIDField(
        source='campaign',
        write_only=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Campaign ID'),
        }
    )
    user_id = serializers.UUIDField(
        source='user',
        write_only=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='User'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='User ID'),
        }
    )

    # Read-only display
    campaign_name = serializers.SerializerMethodField(read_only=True)
    user_name = serializers.SerializerMethodField(read_only=True)
    role_display = serializers.SerializerMethodField(read_only=True)
    added_by_name = serializers.SerializerMethodField(read_only=True)

    # Nested user (read-only, for detail responses)
    user_detail = MemberUserSerializer(source='user', read_only=True)

    class Meta:
        model = CampaignMember
        fields = [
            # Write FK
            'campaign_id', 'user_id',

            # Writable fields
            'role', 'is_primary_owner',

            # Read-only display
            'id', 'campaign_name',
            'user_name', 'user_detail',
            'role_display',
            'is_primary_owner',
            'added_at', 'added_by', 'added_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'campaign_name',
            'user_name', 'user_detail',
            'role_display',
            'added_at', 'added_by', 'added_by_name',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'role': {
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Role'),
                    'invalid_choice': CoreErrorMessages.INVALID_FIELD.format(field='Role'),
                }
            },
        }

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def get_campaign_name(self, obj):
        return obj.campaign.name if obj.campaign else None

    def get_user_name(self, obj):
        if not obj.user:
            return None
        return f"{obj.user.first_name or ''} {obj.user.last_name or ''}".strip() or obj.user.email

    def get_role_display(self, obj):
        return obj.get_role_display() if obj.role else None

    def get_added_by_name(self, obj):
        if not obj.added_by:
            return None
        return f"{obj.added_by.first_name or ''} {obj.added_by.last_name or ''}".strip() or obj.added_by.email

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, attrs):
        """
        Global validation for CampaignMember.

        Rules:
            - Campaign exists and belongs to same client
            - User exists, is active, and belongs to same client
            - Campaign is not in final state
            - Unique (campaign, user, role) per client (create only)
            - Only one is_primary_owner=True per campaign
            - is_primary_owner only valid for OWNER role
        """
        try:
            client_id = self._get_client_id_from_context()

            campaign_id = attrs.get('campaign')
            user_id = attrs.get('user')
            role = attrs.get('role')
            is_primary_owner = attrs.get('is_primary_owner', False)

            # Resolve and validate campaign
            if campaign_id:
                campaign = self._validate_campaign(campaign_id, client_id)
                attrs['campaign'] = campaign

            # Resolve and validate user
            if user_id:
                user = self._validate_user(user_id, client_id)
                attrs['user'] = user

            # Unique check on create (campaign + user + role)
            if not self.instance and campaign_id and user_id and role:
                if CampaignMember.objects.filter(
                    campaign=attrs['campaign'],
                    user=attrs['user'],
                    role=role,
                    client_id=client_id,
                ).exists():
                    raise StandardizedValidationError(
                        CampaignModuleErrorMessages.MEMBER_ALREADY_EXISTS.format(role=role)
                    )

            # is_primary_owner validation
            if is_primary_owner:
                self._validate_primary_owner(attrs, client_id)

            return attrs

        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            )

    def _validate_campaign(self, campaign_id, client_id):
        """Validate campaign exists, belongs to same client, not in final state."""
        try:
            campaign = Campaign.objects.get(id=campaign_id)
        except Campaign.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

        if str(campaign.client_id) != str(client_id):
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)

        if campaign.is_in_final_state:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.CAMPAIGN_IN_FINAL_STATE.format(
                    state=campaign.get_status_display()
                )
            )

        return campaign

    def _validate_user(self, user_id, client_id):
        """Validate user exists, is active, and belongs to same client."""
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

        if not user.is_active:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='User (inactive)')
            )

        if str(user.client_account_id) != str(client_id):
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)

        return user

    def _validate_primary_owner(self, attrs, client_id):
        """Validate is_primary_owner constraints."""
        role = attrs.get('role')

        # is_primary_owner only valid for OWNER role
        if role and role != CampaignMember.MemberRole.OWNER:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field='is_primary_owner (only valid for OWNER role)'
                )
            )

        # Check no other primary owner exists for this campaign
        campaign = attrs.get('campaign')
        if campaign:
            existing_primary = CampaignMember.objects.filter(
                campaign=campaign,
                is_primary_owner=True,
            )
            # Exclude current instance on update
            if self.instance:
                existing_primary = existing_primary.exclude(id=self.instance.id)

            if existing_primary.exists():
                raise StandardizedValidationError(
                    CampaignModuleErrorMessages.OBJECTIVE_PRIMARY_EXISTS
                )

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(self, validated_data):
        """
        Create CampaignMember with audit fields.

        Sets added_by to current request user.
        """
        request = self.context.get('request')
        user = request.user if request else None
        client_id = validated_data.pop('client_id', None) or self._get_client_id_from_context()

        instance = CampaignMember(
            **validated_data,
            added_by=user,
        )
        instance.save(user=user, client_id=client_id)

        return instance

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, instance, validated_data):
        """
        Update CampaignMember.

        Rules:
            - Cannot change campaign or user after creation
            - Can change role and is_primary_owner
        """
        user = self.context.get('request').user if self.context.get('request') else None

        # Remove FK fields (immutable after creation)
        validated_data.pop('campaign', None)
        validated_data.pop('user', None)

        # Update allowed fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save(user=user)
        return instance


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'CampaignMemberListSerializer',
    'CampaignMemberSerializer',
]