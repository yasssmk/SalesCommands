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

from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages, CampaignModuleErrorMessages
from core.exceptions import StandardizedValidationError

from end_users.models import User
from app_modules.territories.models import Territory

from ..models import (
    Campaign,
    CampaignType,
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
    owner_name = serializers.SerializerMethodField(read_only=True)
    primary_objective = serializers.SerializerMethodField(read_only=True)

    # Target progress — RAW counts (not a %), annotated on the list queryset via
    # separate subqueries. The card derives both modes from these: ACTIVE shows
    # "total - worked left to contact", the other statuses show worked/total as
    # a %. worked = targets in a final state (COMPLETED/STOPPED).
    targets_total = serializers.SerializerMethodField(read_only=True)
    targets_worked = serializers.SerializerMethodField(read_only=True)

    # "N activities to do today" — the count the TARGETED card renders, kept in
    # lock-step with the playlist's "To do today" chip. Reads the
    # _activities_today annotation set on the list queryset (campaign_views.py).
    activities_today = serializers.SerializerMethodField(read_only=True)

    # Attribution — owner + team and executor + team, for the card's
    # "Name — TEAM" attribution block. Mirrors TerritoryListSerializer's
    # get_owner / get_team ({id, full_name} for the person, {id, name} for the
    # team). Executor is nullable (defaults to owner), so both executor fields
    # return None when unset. The list queryset select_related's owner__team /
    # executor__team so these never fan out into an N+1.
    owner = serializers.SerializerMethodField(read_only=True)
    owner_team = serializers.SerializerMethodField(read_only=True)
    executor = serializers.SerializerMethodField(read_only=True)
    executor_team = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Campaign
        fields = [
            # Identity
            'id', 'name',

            # Type
            'campaign_type', 'campaign_type_display',
            'sequence_type', 'sequence_type_display', 'has_sequence',
            'channel_override',

            # Territory
            'territory_name',

            # Status
            'status', 'status_display',

            # Dates
            'planned_start_date', 'planned_end_date',
            'actual_start_date', 'actual_end_date',

            # Aggregates
            'accounts_count', 'owner_name', 'primary_objective',
            'targets_total', 'targets_worked', 'activities_today',

            # Attribution (owner + team, executor + team)
            'owner', 'owner_team', 'executor', 'executor_team',

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
        """Number of enrolled accounts holding at least one contact.

        Orphan accounts (0 CampaignContact — residue that maps to no real worked
        account) are excluded; terminal accounts with contacts still count.
        Relies on the _accounts_count annotation (ViewSet.get_queryset), with a
        contact-filtered fallback that mirrors it.
        """
        if hasattr(obj, '_accounts_count'):
            return obj._accounts_count
        return obj.campaign_accounts.filter(
            campaign_contacts__isnull=False
        ).distinct().count()

    def get_targets_total(self, obj):
        """Total enrolled targets (CampaignContact rows).

        Reads the _targets_total annotation set on the list queryset. Falls back
        to None — NEVER a property or a per-row count — so a view that does not
        annotate it (e.g. detail) can never reintroduce an N+1 across the page.
        Mirrors the annotation guard of get_accounts_count (annotation only).
        """
        return obj._targets_total if hasattr(obj, '_targets_total') else None

    def get_targets_worked(self, obj):
        """Targets in a final state (COMPLETED / STOPPED) = worked.

        Reads the _targets_worked annotation; None when unannotated (no N+1).
        """
        return obj._targets_worked if hasattr(obj, '_targets_worked') else None

    def get_activities_today(self, obj):
        """Activities the rep still has to do today for this campaign.

        Reads the _activities_today annotation set on the list queryset; None
        when unannotated (e.g. detail) — NEVER a property or a per-row count, so
        an un-annotated view can never reintroduce an N+1. Mirrors the annotation
        guard of get_targets_total.
        """
        return obj._activities_today if hasattr(obj, '_activities_today') else None

    def get_owner_name(self, obj):
        if not obj.owner:
            return None
        return f"{obj.owner.first_name or ''} {obj.owner.last_name or ''}".strip() or obj.owner.email

    @staticmethod
    def _user_summary(user):
        """Minimal user object for attribution. Mirrors TerritoryListSerializer.get_owner."""
        if not user:
            return None
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
        return {'id': str(user.id), 'full_name': full_name}

    @staticmethod
    def _team_summary(user):
        """The user's team as a minimal object. Mirrors TerritoryListSerializer.get_team."""
        team = getattr(user, 'team', None) if user else None
        if not team:
            return None
        return {'id': str(team.id), 'name': team.name}

    def get_owner(self, obj):
        return self._user_summary(obj.owner)

    def get_owner_team(self, obj):
        return self._team_summary(obj.owner)

    def get_executor(self, obj):
        return self._user_summary(obj.executor)

    def get_executor_team(self, obj):
        return self._team_summary(obj.executor)

    def get_primary_objective(self, obj):
        """Return the primary objective WITH its live advancement.

        current_value / progress_percentage come from the SAME calculation the
        detail serializer exposes. On the list/my-campaigns pages they are read
        from the batch map the view precomputes in one bounded pass
        (context['primary_objective_progress']); an unbatched caller falls back
        to the per-campaign service calculation.
        """
        if hasattr(obj, '_primary_objective_cache'):
            primary = obj._primary_objective_cache
        else:
            # Resolve from the prefetched ``objectives`` in Python (a ``.filter()``
            # would bypass the prefetch cache and re-query per row — an N+1).
            primary = next(
                (o for o in obj.objectives.all() if o.is_primary), None
            )

        if not primary:
            return None

        current_value, progress_pct = self._primary_progress(obj, primary)
        return {
            'id': str(primary.id),
            'name': primary.name,
            'objective_type': primary.objective_type,
            'target_value': float(primary.target_value),
            'current_value': current_value,
            'progress_percentage': progress_pct,
        }

    def _primary_progress(self, obj, primary):
        """(current_value, progress_percentage) for the campaign's primary objective.

        Prefers the batch map the list view precomputes (no per-row query); falls
        back to CampaignAnalyticsService — the detail serializer's calculation —
        so the field is always correct even for an unbatched caller.
        """
        progress_map = self.context.get('primary_objective_progress')
        if progress_map is not None and obj.id in progress_map:
            entry = progress_map[obj.id]
            return entry['current_value'], entry['progress_percentage']

        from app_modules.campaigns.services.campaign_analytics_service import (
            CampaignAnalyticsService,
        )
        from app_modules.campaigns.services.campaign_objective_progress import (
            progress_percentage,
        )
        service = CampaignAnalyticsService(client_id=obj.client_id)
        current = float(service._calculate_objective_value(obj, primary) or 0)
        return current, progress_percentage(current, primary.target_value)


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


    # Ownership
    owner = CampaignUserSerializer(read_only=True)
    executor = CampaignUserSerializer(read_only=True)

    # Objectives nested (inline to avoid circular import)
    objectives = serializers.SerializerMethodField(read_only=True)

    # Aggregates
    accounts_count = serializers.SerializerMethodField(read_only=True)
    expected_end_date = serializers.SerializerMethodField(read_only=True)
    is_inactive = serializers.SerializerMethodField(read_only=True)

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
            'planned_start_date', 'planned_end_date',
            'actual_start_date', 'actual_end_date',

            # Ownership
            'owner', 'executor',
            # Nested relations
            'objectives',

            # Aggregates
            'accounts_count', 'expected_end_date', 'is_inactive',

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
        # Accounts holding ≥1 contact (orphans excluded); mirrors the
        # _accounts_count annotation. See list serializer for rationale.
        if hasattr(obj, '_accounts_count'):
            return obj._accounts_count
        return obj.campaign_accounts.filter(
            campaign_contacts__isnull=False
        ).distinct().count()

    def get_objectives(self, obj):
        """Return objectives with computed progress (single value calculation per objective)."""
        from app_modules.campaigns.services.campaign_analytics_service import CampaignAnalyticsService
        service = CampaignAnalyticsService(client_id=obj.client_id)
        return service.get_objectives_progress(obj)
    
    def get_expected_end_date(self, obj):
        """Date of the last scheduled PLANNED activity linked to this campaign."""
        if hasattr(obj, '_expected_end_date'):
            val = obj._expected_end_date
            return val.isoformat() if val else None

        from app_modules.activities.models import Activity
        from app_modules.activities.constants import ActivityStatus
        last = (
            Activity.objects
            .filter(campaign=obj, status=ActivityStatus.PLANNED)
            .order_by('-scheduled_date')
            .values_list('scheduled_date', flat=True)
            .first()
        )
        return last.isoformat() if last else None

    def get_is_inactive(self, obj):
        from django.utils import timezone
        if obj.status != 'ACTIVE':
            return False
        # Not inactive if the campaign started less than inactivity_threshold_days ago
        start = obj.actual_start_date or obj.planned_start_date
        if start and (timezone.now().date() - start).days < CONFIG.limits.inactivity_threshold_days:
            return False
        if hasattr(obj, '_is_inactive'):
            return obj._is_inactive
        from app_modules.activities.models import Activity
        from app_modules.activities.constants import ActivityStatus
        threshold = timezone.now().date() - timezone.timedelta(
            days=CONFIG.limits.inactivity_threshold_days
        )
        has_recent = Activity.objects.filter(
            campaign=obj,
            status=ActivityStatus.COMPLETED,
            completed_at__date__gte=threshold,
        ).exists()
        return not has_recent

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


    start_date = serializers.DateField(
        source='planned_start_date',
        required=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Start Date'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Start Date (format: YYYY-MM-DD)'),
        },
    )
    end_date = serializers.DateField(
        source='planned_end_date',
        required=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='End Date'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='End Date (format: YYYY-MM-DD)'),
        },
    )

    # Executor assignment (write-only, optional)
    executor_id = serializers.UUIDField(
        required=False,
        write_only=True,
        allow_null=True,
    )

    channel_override = serializers.ChoiceField(
        choices=['AUTO', 'EMAIL_ONLY'],
        required=False,
        default='AUTO',
    )

    class Meta:
        model = Campaign
        fields = [
            'name', 'description',
            'campaign_type', 'sequence_type',
            'territory_ids',
            'start_date', 'end_date',
            'objective',
            'executor_id',
            'channel_override',
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

            # TARGETED is a singleton — only created via get_or_create_targeted()
            campaign_type = attrs.get('campaign_type')
            if campaign_type == CampaignType.TARGETED:
                raise StandardizedValidationError(
                    CampaignModuleErrorMessages.TARGETED_CAMPAIGN_MANUAL_CREATION_FORBIDDEN
                )

            # Date validation
            start_date = attrs.get('planned_start_date')
            end_date = attrs.get('planned_end_date')
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

            # Validate executor (if provided)
            executor_id = attrs.get('executor_id')
            if executor_id:
                self._validate_executor(executor_id, client_id)

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
    
    def _validate_executor(self, executor_id, client_id):
        """Validate executor exists and belongs to same client."""
        try:
            user = User.objects.get(id=executor_id, is_active=True)
            if str(user.client_account_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        except User.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

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
        """Create campaign with owner, optional executor and objective."""
        user = self.context.get('request').user if self.context.get('request') else None

        objective_data = validated_data.pop('objective', None)
        executor_id = validated_data.pop('executor_id', None)
        territory_ids = validated_data.pop('territory_ids', [])

        # Resolve executor
        executor = None
        if executor_id:
            executor = User.objects.get(id=executor_id)

        # Create campaign instance
        instance = Campaign(
            **validated_data,
            owner=user,
            executor=executor,
        )
        instance.save(user=user)
        

        # Set territories M2M
        if territory_ids:
            territories = Territory.objects.filter(id__in=territory_ids)
            instance.territories.set(territories)

        # Enroll accounts from territories (OUTBOUND)
        if territory_ids and instance.campaign_type == CampaignType.OUTBOUND:
            from ..services.campaign_creation_service import CampaignCreationService
            CampaignCreationService(
                user=user,
                client_id=instance.client_id,
            )._enroll_from_territories(instance)

        # Create objective (if provided)
        if objective_data:
            objective_type = objective_data['objective_type']
            obj = CampaignObjective(
                campaign=instance,
                name=objective_data.get('name') or f"{objective_type.replace('_', ' ').title()} Goal",
                objective_type=objective_type,
                target_value=objective_data['target_value'],
                is_primary=objective_data.get('is_primary', True),
            )
            obj.save(user=user, client_id=instance.client_id)

        return instance

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

    executor_id = serializers.UUIDField(
        required=False,
        write_only=True,
        allow_null=True,
    )

    channel_override = serializers.ChoiceField(
        choices=['AUTO', 'EMAIL_ONLY'],
        required=False,
        default='AUTO',
    )

    # Map frontend keys start_date/end_date → model fields planned_start_date/planned_end_date
    start_date = serializers.DateField(
        source='planned_start_date',
        required=False,
    )
    end_date = serializers.DateField(
        source='planned_end_date',
        required=False,
    )

    class Meta:
        model = Campaign
        fields = [
            'name', 'description',
            'sequence_type',
            'territory_ids',
            'start_date', 'end_date',
            'executor_id',
            'channel_override',
        ]
        extra_kwargs = {
            'name': {'required': False},
            'description': {'required': False},
            'sequence_type': {'required': False},
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

            # TARGETED campaign name is immutable
            if instance.is_targeted and 'name' in attrs:
                raise StandardizedValidationError(
                    CampaignModuleErrorMessages.TARGETED_CAMPAIGN_LIFECYCLE_FORBIDDEN
                )

            # Cannot modify campaigns in final state
            if instance.is_in_final_state:
                raise StandardizedValidationError(
                    CampaignModuleErrorMessages.CAMPAIGN_IN_FINAL_STATE.format(
                        state=instance.get_status_display()
                    )
                )

            # Date validation (merge with existing values)
            start_date = attrs.get('planned_start_date', instance.planned_start_date)
            end_date = attrs.get('planned_end_date', instance.planned_end_date)
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
        user = self.context.get('request').user if self.context.get('request') else None
        territory_ids = validated_data.pop('territory_ids', None)
        executor_id = validated_data.pop('executor_id', ...)  # sentinel to detect presence

        # Handle executor update (supports null to remove)
        if executor_id is not ...:
            if executor_id is None:
                instance.executor = None
            else:
                from end_users.models import User
                try:
                    instance.executor = User.objects.get(id=executor_id, is_active=True)
                except User.DoesNotExist:
                    from core.exceptions import StandardizedValidationError
                    from core.error_messages import CoreErrorMessages
                    raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save(user=user)

        # Set territories M2M (after save)
        if territory_ids is not None:
            territories = Territory.objects.filter(id__in=territory_ids)
            instance.territories.set(territories)

        return instance