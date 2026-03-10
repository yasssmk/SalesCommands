# app_modules/campaigns/serializers/campaign_serializer.py
"""
Serializers for Campaign model.

4 serializers following CompanyAccount / Territory patterns:
- CampaignListSerializer: lightweight for table display
- CampaignDetailSerializer: full retrieve with nested relations
- CampaignCreateSerializer: create with nested objective + member IDs
- CampaignUpdateSerializer: partial update (PATCH)
"""

from rest_framework import serializers
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages, CampaignModuleErrorMessages
from core.exceptions import StandardizedValidationError

from end_users.models import User
from app_modules.territories.models import Territory

from ..models import (
    Campaign,
    CampaignType,
    CampaignStatus,
    CampaignMember,
    CampaignObjective,
    ObjectiveType,
)
from ..config.settings import CONFIG


# ============================================================================
# HELPER SERIALIZERS
# ============================================================================

class CampaignTerritorySerializer(serializers.ModelSerializer):
    """Minimal territory serializer for campaign responses."""

    class Meta:
        model = Territory
        fields = ['id', 'name', 'type']
        read_only_fields = fields


class CampaignUserSerializer(serializers.ModelSerializer):
    """Minimal user serializer for campaign responses."""

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

class CampaignListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Lightweight serializer for campaign lists (performance optimized).

    Principles:
        - Minimum fields for table display
        - SerializerMethodField for relations (avoid N+1)
        - No deep nested serializers
    """

    # Display fields
    campaign_type_display = serializers.SerializerMethodField(read_only=True)
    sequence_type_display = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)
    has_sequence = serializers.SerializerMethodField(read_only=True)

    # Relations as simple objects
    territory_name = serializers.SerializerMethodField(read_only=True)

    # Computed aggregates
    accounts_count = serializers.SerializerMethodField(read_only=True)
    members_summary = serializers.SerializerMethodField(read_only=True)
    primary_objective = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Campaign
        fields = [
            # Identity
            'id', 'name',

            # Type
            'campaign_type', 'campaign_type_display',
            'sequence_type', 'sequence_type_display', 'has_sequence',

            # Territory
            'territory_name',

            # Status
            'status', 'status_display',

            # Dates
            'start_date', 'end_date',

            # Aggregates
            'accounts_count', 'members_summary', 'primary_objective',

            # Timestamps
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_campaign_type_display(self, obj):
        """Return human-readable campaign type."""
        return obj.get_campaign_type_display() if obj.campaign_type else None

    def get_sequence_type_display(self, obj):
        """Return sequence type display with safe fallback."""
        return obj.get_sequence_type_display_safe()

    def get_status_display(self, obj):
        """Return human-readable status."""
        return obj.get_status_display() if obj.status else None

    def get_has_sequence(self, obj):
        """Check if campaign uses automated sequences."""
        return obj.has_sequence

    def get_territory_name(self, obj):
        """Return territory names (M2M)."""
        territories = obj.territories.all()
        if not territories:
            return None
        return ', '.join(t.name for t in territories)


    def get_accounts_count(self, obj):
        """Return number of accounts enrolled in campaign."""
        # Relies on annotation from ViewSet.get_queryset() or fallback
        if hasattr(obj, '_accounts_count'):
            return obj._accounts_count
        return obj.campaign_accounts.count()

    def get_members_summary(self, obj):
        """Return summary of members by role."""
        if hasattr(obj, '_members_count'):
            return {'total': obj._members_count}
        return {'total': obj.members.count()}

    def get_primary_objective(self, obj):
        """Return primary objective as minimal object."""
        if hasattr(obj, '_primary_objective_cache'):
            primary = obj._primary_objective_cache
        else:
            primary = obj.objectives.filter(is_primary=True).first()

        if not primary:
            return None
        return {
            'id': str(primary.id),
            'name': primary.name,
            'objective_type': primary.objective_type,
            'target_value': float(primary.target_value),
        }


# ============================================================================
# DETAIL SERIALIZER (Full retrieve)
# ============================================================================

class CampaignDetailSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Complete serializer for campaign detail view.

    Includes all fields + nested relations (members, objectives, territory).
    """

    # Display fields
    campaign_type_display = serializers.SerializerMethodField(read_only=True)
    sequence_type_display = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)
    has_sequence = serializers.SerializerMethodField(read_only=True)

    # Nested relations (read-only)
    territories = CampaignTerritorySerializer(many=True, read_only=True)


    # Members nested (inline to avoid circular import)
    members = serializers.SerializerMethodField(read_only=True)

    # Objectives nested (inline to avoid circular import)
    objectives = serializers.SerializerMethodField(read_only=True)

    # Aggregates
    accounts_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Campaign
        fields = [
            # Identity
            'id', 'name', 'description',

            # Type
            'campaign_type', 'campaign_type_display',
            'sequence_type', 'sequence_type_display', 'has_sequence',

            # Territory
            'territories',

            # Status
            'status', 'status_display',

            # Dates
            'start_date', 'end_date',

            # Nested relations
            'members', 'objectives',

            # Aggregates
            'accounts_count',

            # Audit
            'created_by', 'updated_by',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_campaign_type_display(self, obj):
        return obj.get_campaign_type_display() if obj.campaign_type else None

    def get_sequence_type_display(self, obj):
        return obj.get_sequence_type_display_safe()

    def get_status_display(self, obj):
        return obj.get_status_display() if obj.status else None

    def get_has_sequence(self, obj):
        return obj.has_sequence

    def get_accounts_count(self, obj):
        if hasattr(obj, '_accounts_count'):
            return obj._accounts_count
        return obj.campaign_accounts.count()

    def get_members(self, obj):
        """Return members grouped with user info."""
        members = obj.members.select_related('user', 'added_by').all()
        return [
            {
                'id': str(m.id),
                'user': {
                    'id': str(m.user_id),
                    'email': m.user.email,
                    'first_name': m.user.first_name,
                    'last_name': m.user.last_name,
                    'full_name': f"{m.user.first_name or ''} {m.user.last_name or ''}".strip() or m.user.email,
                },
                'role': m.role,
                'role_display': m.get_role_display(),
                'is_primary_owner': m.is_primary_owner,
                'added_at': m.added_at.isoformat() if m.added_at else None,
                'added_by_name': (
                    f"{m.added_by.first_name or ''} {m.added_by.last_name or ''}".strip()
                    if m.added_by else None
                ),
            }
            for m in members
        ]

    def get_objectives(self, obj):
        """Return objectives with computed progress."""
        objectives = obj.objectives.all()
        return [
            {
                'id': str(o.id),
                'name': o.name,
                'objective_type': o.objective_type,
                'objective_type_display': o.get_objective_type_display(),
                'target_value': float(o.target_value),
                'current_value': o.get_current_value(),
                'progress_percentage': o.get_progress_percentage(),
                'is_primary': o.is_primary,
            }
            for o in objectives
        ]


# ============================================================================
# CREATE SERIALIZER
# ============================================================================

class CampaignCreateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for campaign creation.

    Supports:
        - Nested objective creation (optional DictField)
        - Member assignment via owner_ids / executor_ids / receiver_ids
        - Territory validation for OUTBOUND campaigns
        - Client-scoped name uniqueness
    """

    territory_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True,
    )

    # Nested objective (optional, created in create())
    objective = serializers.DictField(
        write_only=True,
        required=False,
        help_text='Objective data: {name, objective_type, target_value, is_primary}',
    )

    # Member assignment (write-only)
    owner_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True,
    )
    executor_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True,
    )
    receiver_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True,
    )

    class Meta:
        model = Campaign
        fields = [
            'name', 'description',
            'campaign_type', 'sequence_type',
            'territory_ids',
            'start_date', 'end_date',
            'objective',
            'owner_ids', 'executor_ids', 'receiver_ids',
        ]
        extra_kwargs = {
            'name': {
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign Name'),
                    'blank': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign Name'),
                }
            },
            'campaign_type': {
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign Type'),
                }
            },
            'start_date': {
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Start Date'),
                    'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Start Date (format: YYYY-MM-DD)'),
                }
            },
            'end_date': {
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(field='End Date'),
                    'invalid': CoreErrorMessages.INVALID_FIELD.format(field='End Date (format: YYYY-MM-DD)'),
                }
            },
        }

    # ------------------------------------------------------------------
    # Field-level validation
    # ------------------------------------------------------------------

    def validate_name(self, value):
        """Validate and normalize campaign name."""
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign Name')
            )
        return value.strip()

    def validate_campaign_type(self, value):
        """Validate campaign type is a valid choice."""
        valid = [c[0] for c in CampaignType.choices]
        if value not in valid:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='Campaign Type')
            )
        return value

    # ------------------------------------------------------------------
    # Global validation
    # ------------------------------------------------------------------

    def validate(self, attrs):
        """
        Global validation for campaign creation.

        Rules:
            - end_date > start_date
            - OUTBOUND requires territory
            - Name unique within client scope
            - Territory belongs to same client (if provided)
            - Member user IDs belong to same client
        """
        try:
            client_id = self._get_client_id_from_context()
            attrs['client_id'] = client_id

            # Date validation
            start_date = attrs.get('start_date')
            end_date = attrs.get('end_date')
            if start_date and end_date and end_date < start_date:
                raise StandardizedValidationError(
                    CampaignModuleErrorMessages.CAMPAIGN_DATE_INVALID
                )

            # OUTBOUND → at least one territory required
            campaign_type = attrs.get('campaign_type')
            territory_ids = attrs.get('territory_ids', [])
            if campaign_type == CampaignType.OUTBOUND and not territory_ids:
                raise StandardizedValidationError(
                    CampaignModuleErrorMessages.CAMPAIGN_TERRITORY_REQUIRED
                )

            # Validate all territories belong to same client
            for tid in territory_ids:
                self._validate_territory(tid, client_id)


            # Name uniqueness within client
            self.validate_client_scoped_uniqueness(
                data=attrs,
                unique_fields=['name'],
                model_class=Campaign,
                error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields='campaign name'
                ),
            )

            # Validate member IDs (if provided)
            for field_name in ('owner_ids', 'executor_ids', 'receiver_ids'):
                user_ids = attrs.get(field_name, [])
                if user_ids:
                    self._validate_user_ids(user_ids, client_id, field_name)

            # Validate objective structure (if provided)
            objective_data = attrs.get('objective')
            if objective_data:
                self._validate_objective_data(objective_data)

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

    def _validate_territory(self, territory_id, client_id):
        """Validate territory exists and belongs to same client."""
        try:
            territory = Territory.objects.get(id=territory_id)
            if str(territory.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.CLIENT_MISMATCH
                )
        except Territory.DoesNotExist:
            raise StandardizedValidationError(
                CoreErrorMessages.OBJECT_NOT_FOUND
            )

    def _validate_user_ids(self, user_ids, client_id, field_name):
        """Validate all user IDs exist and belong to same client."""
        users = User.objects.filter(id__in=user_ids, is_active=True)
        if users.count() != len(user_ids):
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field=field_name)
            )
        for user in users:
            if str(user.client_account_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.CLIENT_MISMATCH
                )

    def _validate_objective_data(self, objective_data):
        """Validate objective dict structure. 'name' is optional — auto-generated if absent."""
        required_keys = {'objective_type', 'target_value'}
        missing = required_keys - set(objective_data.keys())
        if missing:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field=f"Objective ({', '.join(missing)})")
            )

        valid_types = [c[0] for c in ObjectiveType.choices]
        if objective_data.get('objective_type') not in valid_types:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.OBJECTIVE_INVALID_TYPE.format(
                    objective_type=objective_data.get('objective_type')
                )
            )

        try:
            tv = float(objective_data['target_value'])
            if tv <= 0:
                raise ValueError
        except (TypeError, ValueError):
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.OBJECTIVE_TARGET_VALUE_INVALID
            )

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(self, validated_data):
        """
        Create campaign with optional nested objective and members.

        Flow:
            1. Extract nested data (objective, member IDs)
            2. Resolve territory FK
            3. Create Campaign instance
            4. Create CampaignObjective (if provided)
            5. Create CampaignMember entries
        """
        user = self.context.get('request').user if self.context.get('request') else None

        # Extract nested data before model creation
        objective_data = validated_data.pop('objective', None)
        owner_ids = validated_data.pop('owner_ids', [])
        executor_ids = validated_data.pop('executor_ids', [])
        receiver_ids = validated_data.pop('receiver_ids', [])
        client_id = validated_data.get('client_id', None)

        #  Extract territory IDs (M2M — set after instance creation)
        territory_ids = validated_data.pop('territory_ids', [])

        # Create campaign instance
        instance = Campaign.objects.create(**validated_data)

        # Set territories M2M
        if territory_ids:
            territories = Territory.objects.filter(id__in=territory_ids)
            instance.territories.set(territories)

        # Enroll accounts from territories immediately (OUTBOUND campaigns only)
        # This ensures the Accounts tab is populated in DRAFT state.
        # The fallback in CampaignLifecycleService.start() remains as a safety net.
        if territory_ids and instance.campaign_type == 'OUTBOUND':
            from ..services.campaign_creation_service import CampaignCreationService
            creation_service = CampaignCreationService(
                user=user,
                client_id=instance.client_id,
            )
            creation_service._enroll_from_territories(instance)

        # Create objective (if provided)
        if objective_data:
            objective_type = objective_data['objective_type']
            # Auto-generate name if frontend does not send one
            objective_name = objective_data.get('name') or f"{objective_type.replace('_', ' ').title()} Goal"
            CampaignObjective.objects.create(
                campaign=instance,
                name=objective_name,
                objective_type=objective_type,
                target_value=objective_data['target_value'],
                is_primary=objective_data.get('is_primary', True),
                client_id=instance.client_id,
            )

        # Create members
        self._create_members(instance, owner_ids, CampaignMember.MemberRole.OWNER, user)
        self._create_members(instance, executor_ids, CampaignMember.MemberRole.EXECUTOR, user)
        self._create_members(instance, receiver_ids, CampaignMember.MemberRole.RECEIVER, user)

        # If no owner provided, set current user as primary owner
        if not owner_ids and user:
            instance.add_member(
                user=user,
                role=CampaignMember.MemberRole.OWNER,
                added_by=user,
                is_primary_owner=True,
            )

        return instance

    def _create_members(self, campaign, user_ids, role, added_by):
        """Create CampaignMember entries for a given role."""
        for i, uid in enumerate(user_ids):
            campaign.add_member(
                user=User.objects.get(id=uid),
                role=role,
                added_by=added_by,
                is_primary_owner=(role == CampaignMember.MemberRole.OWNER and i == 0),
            )


# ============================================================================
# UPDATE SERIALIZER
# ============================================================================

class CampaignUpdateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for campaign updates (PATCH).

    Business Rules:
        - campaign_type is immutable after creation
        - Status changes go through dedicated lifecycle endpoints
        - All fields optional (partial update)
        - Date validation if dates provided
        - Name uniqueness check (exclude current instance)
    """

    territory_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True,
    )

    class Meta:
        model = Campaign
        fields = [
            'name', 'description',
            'sequence_type',
            'territory_ids',
            'start_date', 'end_date',
        ]
        extra_kwargs = {
            'name': {'required': False},
            'description': {'required': False},
            'sequence_type': {'required': False},
            'start_date': {'required': False},
            'end_date': {'required': False},
        }

    def validate_name(self, value):
        """Normalize campaign name."""
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign Name')
            )
        return value.strip()

    def validate(self, attrs):
        """
        Global validation for campaign update.

        Rules:
            - Campaign must be modifiable (not in final state)
            - end_date > start_date (merge with instance values)
            - Name uniqueness (exclude self)
            - Territory belongs to same client
        """
        try:
            instance = self.instance
            client_id = self._get_client_id_from_context()

            # Cannot modify campaigns in final state
            if instance.is_in_final_state:
                raise StandardizedValidationError(
                    CampaignModuleErrorMessages.CAMPAIGN_IN_FINAL_STATE.format(
                        state=instance.get_status_display()
                    )
                )

            # Date validation (merge with existing values)
            start_date = attrs.get('start_date', instance.start_date)
            end_date = attrs.get('end_date', instance.end_date)
            if start_date and end_date and end_date < start_date:
                raise StandardizedValidationError(
                    CampaignModuleErrorMessages.CAMPAIGN_DATE_INVALID
                )

            # Name uniqueness (exclude current instance)
            if 'name' in attrs:
                self.validate_client_scoped_uniqueness(
                    data=attrs,
                    unique_fields=['name'],
                    model_class=Campaign,
                    error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                        fields='campaign name'
                    ),
                )

                # Validate territories if provided
                territory_ids = attrs.get('territory_ids', [])
                for tid in territory_ids:
                    try:
                        territory = Territory.objects.get(id=tid)
                        if str(territory.client_id) != str(client_id):
                            raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
                    except Territory.DoesNotExist:
                        raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)


            return attrs

        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            )

    def update(self, instance, validated_data):
        """Update campaign with proper audit fields."""
        user = self.context.get('request').user if self.context.get('request') else None

                # Resolve territories M2M
        territory_ids = validated_data.pop('territory_ids', None)

        # Update fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save(user=user)

        # Set territories M2M (after save)
        if territory_ids is not None:
            territories = Territory.objects.filter(id__in=territory_ids)
            instance.territories.set(territories)

        return instance