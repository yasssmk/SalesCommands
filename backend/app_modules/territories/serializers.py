# backend/app_modules/territories/serializers.py
"""
Serializers for Territory module.

Follows the same patterns as CompanyAccount serializers for consistency.
"""

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from end_users.models import User
from .models import Territory, TerritoryType

# ============================================================================
# CONSTANTS
# ============================================================================

ALLOWED_FILTER_KEYS = {
    # Account filters
    'type',
    'classification', 
    'industry',
    'country',
    'company_size',
    'account_owner',
    'account_scope',
    'has_buying_decision',
    # Contact filters
    'influence_level',
    'standard_department',
    'has_buying_authority',
    'opted_out',
    'contact_scope',
}

# ============================================================================
# BASE MIXIN FOR VALIDATION
# ============================================================================

class TerritoryValidationMixin:
    """
    Shared validation methods for Territory serializers.
    
    Provides common validation logic for:
    - Owner validation (cross-tenant check)
    - Filter definition account_owner validation
    """
    
    def _validate_owner(self, owner_id, client_id):
        """Validate owner exists and belongs to same client."""
        try:
            owner = User.objects.get(id=owner_id)
            if not owner.is_active:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field='Owner (inactive user)')
                )
            if str(owner.client_account_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field='Owner (different client)')
                )
        except User.DoesNotExist:
            raise StandardizedValidationError(
                CoreErrorMessages.OBJECT_NOT_FOUND
            )
    
    def _validate_filter_account_owner(self, owner_id):
        """Validate account_owner in filter_definition belongs to same client."""
        try:
            client_id = self._get_client_id_from_context()
            owner = User.objects.get(id=owner_id)
            if str(owner.client_account_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field='Filter Definition account_owner (different client)'
                    )
                )
        except User.DoesNotExist:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field='Filter Definition account_owner (user not found)'
                )
            )
    
    def validate_filter_definition(self, value):
        """
        Validate filter_definition structure and content.
        
        - Must be a dict
        - Only allowed keys accepted
        - account_owner validated for cross-tenant
        """
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='Filter Definition')
            )
        
        # Whitelist validation
        unknown_keys = set(value.keys()) - ALLOWED_FILTER_KEYS
        if unknown_keys:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field=f"Filter Definition (unknown keys: {', '.join(sorted(unknown_keys))})"
                )
            )
        
        # Validate account_owner if present
        if value.get('account_owner'):
            self._validate_filter_account_owner(value['account_owner'])
        
        return value


# ============================================================================
# HELPER SERIALIZERS
# ============================================================================

class TerritoryOwnerSerializer(serializers.ModelSerializer):
    """Serializer for territory owner summary."""
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name']
        read_only_fields = fields


# ============================================================================
# LIST SERIALIZER (Performance optimized)
# ============================================================================

class TerritoryListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Lightweight serializer for territory lists (performance optimized).
    
    Principles:
        - Minimum fields for table/card display
        - SerializerMethodField for relations (avoid N+1)
        - No deep nested serializers
    """
    
    owner = serializers.SerializerMethodField(read_only=True)
    team = serializers.SerializerMethodField(read_only=True)
    type_display = serializers.SerializerMethodField(read_only=True)
    filter_count = serializers.SerializerMethodField(read_only=True)
    is_in_active_campaign = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Territory
        fields = [
            # Identity
            'id', 'name', 'description',

            # Type
            'type', 'type_display',

            # Flags
            'is_system', 'is_default',

            # Filters
            'filter_definition', 'filter_count',

            # Owner / team
            'owner', 'team',

            # Campaign linkage
            'is_in_active_campaign',

            # Coverage snapshot (materialised on the row; not live — see model)
            'coverage_numerator', 'coverage_denominator',
            'coverage_period_key', 'coverage_computed_at',

            # Timestamps
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_owner(self, obj):
        """Return owner as minimal object."""
        if not obj.owner:
            return None
        return {
            'id': str(obj.owner.id),
            'email': obj.owner.email,
            'first_name': obj.owner.first_name,
            'last_name': obj.owner.last_name,
            'full_name': f"{obj.owner.first_name or ''} {obj.owner.last_name or ''}".strip() or obj.owner.email
        }
    
    def get_team(self, obj):
        """Return the owner's team as a minimal object, or None."""
        team = getattr(obj.owner, 'team', None) if obj.owner else None
        if not team:
            return None
        return {'id': str(team.id), 'name': team.name}

    def get_is_in_active_campaign(self, obj):
        """
        Whether the territory is targeted by an ACTIVE campaign.

        Reads the ``_is_in_active_campaign`` annotation set by the list
        queryset (a single Exists subquery for the whole page). Falls back to a
        per-object Exists only when the annotation is absent, so a caller that
        forgets the annotation stays correct at the cost of one extra query.
        """
        annotated = getattr(obj, '_is_in_active_campaign', None)
        if annotated is not None:
            return bool(annotated)
        return obj.campaigns.filter(status='ACTIVE').exists()

    def get_type_display(self, obj):
        """Return human-readable type."""
        return obj.get_type_display() if obj.type else None

    def get_filter_count(self, obj):
        """Return count of active filters."""
        if not obj.filter_definition:
            return 0
        return len([v for v in obj.filter_definition.values() if v])


# ============================================================================
# DETAIL SERIALIZER
# ============================================================================

class TerritorySerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Complete serializer for territory detail view.
    
    Includes all fields and nested owner object.
    """
    
    owner = TerritoryOwnerSerializer(read_only=True)
    type_display = serializers.SerializerMethodField(read_only=True)
    filter_count = serializers.SerializerMethodField(read_only=True)
    has_filters = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Territory
        fields = [
            # Identity
            'id', 'name', 'description',
            
            # Type
            'type', 'type_display',
            
            # Flags
            'is_system', 'is_default',
            
            # Filters
            'filter_definition', 'filter_count', 'has_filters',
            
            # Owner
            'owner',
            
            # Audit
            'created_by', 'updated_by',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'is_system', 'filter_count', 'has_filters',
            'type_display', 'created_by', 'updated_by',
            'created_at', 'updated_at'
        ]
    
    def get_type_display(self, obj):
        """Return human-readable type."""
        return obj.get_type_display() if obj.type else None
    
    def get_filter_count(self, obj):
        """Return count of active filters."""
        if not obj.filter_definition:
            return 0
        return len([v for v in obj.filter_definition.values() if v])
    
    def get_has_filters(self, obj):
        """Return whether territory has filters."""
        return bool(obj.filter_definition)


# ============================================================================
# CREATE SERIALIZER
# ============================================================================

class TerritoryCreateSerializer( TerritoryValidationMixin, ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for territory creation.
    
    Business Rules:
        - name is required
        - Auto-inject client_id
        - is_system defaults to False
    """
    
    owner_id = serializers.UUIDField(
        required=False,
        allow_null=False,
        write_only=True
    )
    
    class Meta:
        model = Territory
        fields = [
            'name', 'description', 'type',
            'is_default', 'filter_definition',
            'owner_id'
        ]
        extra_kwargs = {
            'name': {
                'required': True,
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Name'),
                }
            },
            'type': {
                'required': False,
                'default': TerritoryType.ACCOUNT
            }
        }
    
    def validate_name(self, value):
        """Validate and normalize territory name."""
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Name')
            )
        return value.strip()
    
    def validate_type(self, value):
        """Validate type field."""
        if value is None or value == '':
            return TerritoryType.ACCOUNT
        
        valid_types = [choice[0] for choice in TerritoryType.choices]
        if value not in valid_types:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='Type')
            )
        return value
    
    def validate(self, attrs):
        """Global validation for territory creation."""
        try:
            client_id = self._get_client_id_from_context()
            attrs['client_id'] = client_id
            
            # Validate uniqueness of name within client
            self.validate_client_scoped_uniqueness(
                data=attrs,
                unique_fields=['name'],
                model_class=Territory,
                error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields='name'
                )
            )
            
            # Validate owner if provided
            if attrs.get('owner_id'):
                self._validate_owner(attrs['owner_id'], client_id)
            
            return attrs
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            )
    
    def create(self, validated_data):
        """Create territory with proper audit fields."""
        user = self.context.get('request').user if self.context.get('request') else None
        
        # Extract owner_id and set owner
        owner_id = validated_data.pop('owner_id', None)
        if owner_id:
            validated_data['owner_id'] = owner_id
        elif user:
            # Default owner to current user
            validated_data['owner'] = user
        else:
            # Should never happen with authenticated requests
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='owner')
            )
        
        # Create instance
        instance = Territory(**validated_data)
        instance.save(user=user)
        
        return instance


# ============================================================================
# UPDATE SERIALIZER
# ============================================================================

class TerritoryUpdateSerializer(TerritoryValidationMixin, ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for territory modifications (PATCH).
    
    Features:
        - All fields optional
        - Cannot modify is_system territories (blocked in viewset)
        - Name uniqueness check (exclude current instance)
    """
    
    owner_id = serializers.UUIDField(
        required=False,
        allow_null=False,
        write_only=True
    )
    
    class Meta:
        model = Territory
        fields = [
            'name', 'description', 'type',
            'is_default', 'filter_definition',
            'owner_id'
        ]
        extra_kwargs = {
            'name': {'required': False},
        }
    
    def validate_name(self, value):
        """Validate territory name."""
        if value is not None and not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Name')
            )
        return value.strip() if value else value
    
    def validate_type(self, value):
        """Validate type field."""
        if value is None or value == '':
            return value
        
        valid_types = [choice[0] for choice in TerritoryType.choices]
        if value not in valid_types:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='Type')
            )
        return value
    

    def validate(self, attrs):
        """Global validation for updates."""
        try:
            client_id = self._get_client_id_from_context()
            
            # Validate uniqueness if name changed
            if 'name' in attrs and attrs['name']:
                self.validate_client_scoped_uniqueness(
                    data={'name': attrs['name'], 'client_id': client_id},
                    unique_fields=['name'],
                    model_class=Territory,
                    error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(fields='name'),
                )
            
            # Validate owner if provided
            if attrs.get('owner_id'):
                self._validate_owner(attrs['owner_id'], client_id)
            
            return attrs
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            )
    
    def update(self, instance, validated_data):
        """Update territory with audit fields."""
        user = self.context.get('request').user if self.context.get('request') else None
        
        # Handle owner_id
        owner_id = validated_data.pop('owner_id', None)
        if owner_id is not None:
            instance.owner_id = owner_id
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save(user=user)
        return instance