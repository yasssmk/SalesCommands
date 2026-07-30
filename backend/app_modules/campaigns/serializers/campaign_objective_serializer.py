# app_modules/campaigns/serializers/campaign_objective_serializer.py
"""
Serializers for CampaignObjective model.

2 serializers following CompanyAccount / CampaignMember patterns:
- CampaignObjectiveListSerializer: lightweight for table display
- CampaignObjectiveSerializer: create/update with validation

Constraints enforced:
- unique_together: (campaign, objective_type, client_id)
- UniqueConstraint: only one is_primary=True per campaign
- target_value > 0
- Valid objective_type
"""

from rest_framework import serializers

from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages, CampaignModuleErrorMessages
from core.exceptions import StandardizedValidationError

from ..models import (
    Campaign,
    CampaignObjective,
    ObjectiveType,
)


# ============================================================================
# LIST SERIALIZER (Performance optimized)
# ============================================================================

class CampaignObjectiveListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Lightweight serializer for campaign objective lists (performance optimized).

    Principles:
        - Minimum fields for table/card display
        - SerializerMethodField for computed values
        - No deep nested serializers
    """

    # Display fields
    campaign_name = serializers.SerializerMethodField(read_only=True)
    objective_type_display = serializers.SerializerMethodField(read_only=True)

    # Computed fields
    current_value = serializers.SerializerMethodField(read_only=True)
    progress_percentage = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CampaignObjective
        fields = [
            # Identity
            'id',

            # Relations (display)
            'campaign', 'campaign_name',

            # Core
            'name', 'objective_type', 'objective_type_display',
            'target_value', 'current_value', 'progress_percentage',
            'is_primary',

            # Timestamps
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_campaign_name(self, obj):
        """Return campaign name (relies on select_related)."""
        return obj.campaign.name if obj.campaign else None

    def get_objective_type_display(self, obj):
        """Return human-readable objective type."""
        return obj.get_objective_type_display() if obj.objective_type else None

    def get_current_value(self, obj):
        """Return current tracked value."""
        try:
            return obj.get_current_value()
        except Exception:
            return 0

    def get_progress_percentage(self, obj):
        """Return progress as percentage (0-100)."""
        try:
            return obj.get_progress_percentage()
        except Exception:
            return 0.0


# ============================================================================
# CREATE / UPDATE SERIALIZER
# ============================================================================

class CampaignObjectiveSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for CampaignObjective create and update operations.

    Supports:
        - FK write via campaign_id
        - Validation: target_value > 0, valid type, unique type per campaign
        - Only one is_primary per campaign
        - Campaign belongs to same client and not in final state
    """

    # FK write field
    campaign_id = serializers.UUIDField(
        source='campaign',
        write_only=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Campaign ID'),
        }
    )

    # Read-only display
    campaign_name = serializers.SerializerMethodField(read_only=True)
    objective_type_display = serializers.SerializerMethodField(read_only=True)
    current_value = serializers.SerializerMethodField(read_only=True)
    progress_percentage = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CampaignObjective
        fields = [
            # Write FK
            'campaign_id',

            # Writable fields
            'name', 'objective_type', 'target_value', 'is_primary',

            # Read-only display
            'id', 'campaign_name',
            'objective_type_display',
            'current_value', 'progress_percentage',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'campaign_name',
            'objective_type_display',
            'current_value', 'progress_percentage',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'name': {
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Objective Name'),
                    'blank': CoreErrorMessages.REQUIRED_FIELD.format(field='Objective Name'),
                }
            },
            'objective_type': {
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Objective Type'),
                    'invalid_choice': CoreErrorMessages.INVALID_FIELD.format(field='Objective Type'),
                }
            },
            'target_value': {
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Target Value'),
                    'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Target Value'),
                }
            },
        }

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def get_campaign_name(self, obj):
        return obj.campaign.name if obj.campaign else None

    def get_objective_type_display(self, obj):
        return obj.get_objective_type_display() if obj.objective_type else None

    def get_current_value(self, obj):
        try:
            return obj.get_current_value()
        except Exception:
            return 0

    def get_progress_percentage(self, obj):
        try:
            return obj.get_progress_percentage()
        except Exception:
            return 0.0

    # ------------------------------------------------------------------
    # Field-level validation
    # ------------------------------------------------------------------

    def validate_name(self, value):
        """Validate and normalize objective name."""
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Objective Name')
            )
        return value.strip()

    def validate_target_value(self, value):
        """Validate target_value is strictly positive."""
        if value is None or value <= 0:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.OBJECTIVE_TARGET_VALUE_INVALID
            )
        return value

    def validate_objective_type(self, value):
        """Validate objective_type is a valid choice."""
        valid = [c[0] for c in ObjectiveType.choices]
        if value not in valid:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.OBJECTIVE_INVALID_TYPE.format(
                    objective_type=value
                )
            )
        return value

    # ------------------------------------------------------------------
    # Global validation
    # ------------------------------------------------------------------

    def validate(self, attrs):
        """
        Global validation for CampaignObjective.

        Rules:
            - Campaign exists and belongs to same client
            - Campaign is not in final state
            - Unique (campaign, objective_type) per client (create only)
            - Only one is_primary=True per campaign
        """
        try:
            client_id = self._get_client_id_from_context()

            campaign_id = attrs.get('campaign')
            objective_type = attrs.get('objective_type')
            is_primary = attrs.get('is_primary', False)

            # Resolve and validate campaign
            if campaign_id:
                campaign = self._validate_campaign(campaign_id, client_id)
                attrs['campaign'] = campaign

            # Unique (campaign, objective_type) on create
            if not self.instance and campaign_id and objective_type:
                if CampaignObjective.objects.filter(
                    campaign=attrs['campaign'],
                    objective_type=objective_type,
                    client_id=client_id,
                ).exists():
                    raise StandardizedValidationError(
                        CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                            fields='objective type per campaign'
                        )
                    )

            # is_primary validation
            if is_primary:
                self._validate_primary(attrs)

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

    def _validate_primary(self, attrs):
        """Validate only one is_primary per campaign."""
        campaign = attrs.get('campaign')
        if not campaign:
            return

        existing_primary = CampaignObjective.objects.filter(
            campaign=campaign,
            is_primary=True,
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
        """Create CampaignObjective with audit fields."""
        user = self.context.get('request').user if self.context.get('request') else None
        client_id = validated_data.pop('client_id', None) or self._get_client_id_from_context()

        instance = CampaignObjective(**validated_data)
        instance.save(user=user, client_id=client_id)

        return instance

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, instance, validated_data):
        """
        Update CampaignObjective.

        Rules:
            - Cannot change campaign after creation
            - Cannot change objective_type after creation
            - Can update name, target_value, is_primary
        """
        user = self.context.get('request').user if self.context.get('request') else None

        # Remove immutable fields
        validated_data.pop('campaign', None)
        validated_data.pop('objective_type', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save(user=user)
        return instance


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'CampaignObjectiveListSerializer',
    'CampaignObjectiveSerializer',
]