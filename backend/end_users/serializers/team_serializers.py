from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from ..models import Team, User

class TeamListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Lightweight serializer for team lists (performance optimized).
    
    Principles:
        - Minimum fields for table display
        - SerializerMethodField for relations (avoid N+1)
        - No deep nested serializers
    """
    
    # Relations as simple objects (frontend-friendly)
    manager = serializers.SerializerMethodField(read_only=True)
    parent_team = serializers.SerializerMethodField(read_only=True)

     # Counters
    members_count = serializers.SerializerMethodField(read_only=True)
    active_members_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Team
        fields = [
            # Minimal identity
            'id', 'name', 'description',
            
            # Relations (simple objects)
            'manager', 'parent_team',
            
            # Counts (from annotations)
            'members_count', 'active_members_count',
            
            # Essential timestamps
            'created_at'
        ]
        read_only_fields = fields
    
    def get_manager(self, obj):
        """
        Return manager as minimal object.
        Compatible avec TeamInfoPanel qui attend :
        - first_name
        - last_name
        - email
        """
        if obj.manager:
            return {
                'id': str(obj.manager_id),
                'first_name': obj.manager.first_name,
                'last_name': obj.manager.last_name,
                'email': obj.manager.email,
                'name': obj.manager.get_full_name(),
                'role_name': getattr(obj.manager, 'role_name', None),
            }
        return None
    
    def get_parent_team(self, obj):
        """
        Return parent team as minimal object.
        Compatible with frontend usage: row.original.parent_team?.name
        """
        if obj.parent_team:
            return {
                'id': str(obj.parent_team_id),
                'name': obj.parent_team.name
            }
        return None
    
    def get_members_count(self, obj):
        """
        Return total members count including all descendant teams.
        
        Uses pre-calculated hierarchical counts from context (in-memory calculation).
        Fallback to direct count if context not available.
        
        Performance: 0 additional queries (counts pre-calculated for all teams).
        """
        # Try to get from context (injected by ViewSet)
        hierarchical_counts = self.context.get('hierarchical_counts', {})
        team_id = str(obj.id)
        
        if team_id in hierarchical_counts:
            return hierarchical_counts[team_id]['total']
        
        # Fallback: direct count only (no hierarchy)
        return obj.members.count()

    def get_active_members_count(self, obj):
        """
        Return total active members count including all descendant teams.
        
        Uses pre-calculated hierarchical counts from context (in-memory calculation).
        Fallback to direct count if context not available.
        
        Performance: 0 additional queries (counts pre-calculated for all teams).
        """
        # Try to get from context (injected by ViewSet)
        hierarchical_counts = self.context.get('hierarchical_counts', {})
        team_id = str(obj.id)
        
        if team_id in hierarchical_counts:
            return hierarchical_counts[team_id]['active']
        
        # Fallback: direct count only (no hierarchy)
        return obj.members.filter(is_active=True).count()



class TeamSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer pour Team avec client scoping
    """
    # Read-only relations
    # organization_name = serializers.CharField(source='organization.name', read_only=True)
    client_account_name = serializers.CharField(
        source='client_account.name', 
        read_only=True
    )

    manager_name = serializers.CharField(source='manager.get_full_name', read_only=True)

    # Hierarchy fields
    parent_id = serializers.UUIDField(
        source='parent_team_id',
        required=False,
        allow_null=True,
        write_only=True,
        help_text=_("ID of the parent team in the hierarchy.")
    )
    parent_team = serializers.SerializerMethodField(read_only=True)
    direct_child_teams = serializers.SerializerMethodField(read_only=True)
    
    # Counters
    members_count = serializers.SerializerMethodField(read_only=True)
    active_members_count = serializers.SerializerMethodField(read_only=True)
    
    # Writable relations
    # organization = serializers.PrimaryKeyRelatedField(
    #     queryset=Organization.objects.all(),
    #     error_messages={
    #         'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Organization'),
    #         'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
    #         'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Organization')
    #     }
    # )
    
    manager = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
        error_messages={
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Manager')
        }
    )
    
    class Meta:
        model = Team
        fields = [
            # Identifiers
            'id', 'name', 'description',
            
            # Relations
            'manager', 'manager_name',
            'parent_id', 'parent_team', 'direct_child_teams',
            
            # Client scoping (STANDARDIZATION)
            'client_id', 'client_account', 'client_account_name',
            
            # Computed counts
            'members_count', 'active_members_count',
            
            # Timestamps
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'created_at', 'updated_at',
            'members_count', 'active_members_count',
            'parent_team', 'direct_child_teams'
        ]

    
     # ==== Read helpers ====
    
    def get_members_count(self, obj):
        """
        Return total members count including all descendant teams.
        
        Uses pre-calculated hierarchical counts from context if available.
        Fallback to direct count (no hierarchy).
        """
        # Try to get from context (injected by ViewSet)
        hierarchical_counts = self.context.get('hierarchical_counts', {})
        team_id = str(obj.id)
        
        if team_id in hierarchical_counts:
            return hierarchical_counts[team_id]['total']
        
        # Fallback: direct count only
        return obj.members.count()

    def get_active_members_count(self, obj):
        """
        Return total active members count including all descendant teams.
        
        Uses pre-calculated hierarchical counts from context if available.
        Fallback to direct count (no hierarchy).
        """
        # Try to get from context (injected by ViewSet)
        hierarchical_counts = self.context.get('hierarchical_counts', {})
        team_id = str(obj.id)
        
        if team_id in hierarchical_counts:
            return hierarchical_counts[team_id]['active']
        
        # Fallback: direct count only
        return obj.members.filter(is_active=True).count()
    
    def get_parent_team(self, obj):
        """
        Return a lightweight representation of the parent team.
        """
        if not obj.parent_team:
            return None
        return {
            'id': str(obj.parent_team.id),
            'name': obj.parent_team.name,
        }
    
    def get_direct_child_teams(self, obj):
        """
        Return a lightweight list of direct child teams.
        """
        return [
            {
                'id': str(child.id),
                'name': child.name,
            }
            for child in obj.direct_child_teams.all()
        ]
    
    # ==== Validation ====
    
    # def validate_organization(self, value):
    #     """Valider que l'organisation appartient au même client"""
    #     if value:
    #         client_id = self._get_client_id_from_context()
    #         if str(value.client_id) != str(client_id):
    #             raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
    #     return value
    
    def validate_manager(self, value):
        """Valider que le manager appartient au même client"""
        if value:
            client_id = self._get_client_id_from_context()
            if str(value.client_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        return value
    
    def validate(self, data):
        """
        Global validation for Team, including parent/child hierarchy rules.
        """
        try:
            client_id = self._get_client_id_from_context()
            instance = getattr(self, 'instance', None)
            
            # Parent team validation if provided
            if 'parent_team_id' in data:
                parent_id = data.get('parent_team_id')
                self._validate_parent_team(parent_id, client_id, instance)
            
            return super().validate(data)
        
        except serializers.ValidationError as e:
            # Normalize DRF validation errors to standardized format
            raise StandardizedValidationError(e.detail)
    
    def _validate_parent_team(self, parent_id, client_id, instance):
        """
        Validate parent team relation:
        - Parent must exist
        - Parent must belong to same client_account
        - No self-reference
        - No circular hierarchy
        - Maximum depth of 4 levels (MVP constraint)
        """
        if parent_id is None:
            return
        
        try:
            parent = Team.objects.select_related('client_account').get(id=parent_id)
        except Team.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
        
        # Tenant isolation: parent must belong to the same client
        if str(parent.client_id) != str(client_id):
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        
        # No self-reference
        if instance and parent.id == instance.id:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(
                    detail="A team cannot be its own parent."
                )
            )
        
        # Check hierarchy depth and prevent circular references
        # Depth definition (MVP):
        # level 1: root team (no parent)
        # level 2: child
        # level 3: grand-child
        # level 4: great grand-child
        # → we disallow creating a level 5+ node
        depth = 1  # parent itself is at +1 level from current team
        current = parent
        
        visited_ids = set()
        if instance:
            visited_ids.add(instance.id)
        
        while current.parent_team:
            current = current.parent_team
            depth += 1
            
            # Circular hierarchy protection
            if current.id in visited_ids:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail="Circular team hierarchy detected."
                    )
                )
            visited_ids.add(current.id)
            
            # Max depth = 4 (parent chain length)
            if depth >= 4:
                # If we go beyond 4 when walking upwards,
                # assigning this parent would create a level > 4
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail="Maximum team hierarchy depth (4 levels) exceeded."
                    )
                )

class TeamCreateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Specialized serializer for team creation with strict validations.
    
    Business Rules:
        - Manager is required (per Q2)
        - Description max 500 characters (per Q3)
        - Parent team validation (depth, circular, client isolation)
        - Auto-inject client_account_id
    """
    
    # Write-only field for parent team
    parent_team = serializers.UUIDField(
        source='parent_team_id',
        required=False,
        allow_null=True,
        write_only=True,
        help_text=_("ID of the parent team in the hierarchy.")
    )
    
    class Meta:
        model = Team
        fields = [
            'name', 'description',
            'manager', 'parent_team'
        ]
        extra_kwargs = {
            'name': {'required': True},
            'description': {
                'required': False, 
                'max_length': 500,
                'help_text': 'Brief team description (max 500 characters)'
            },
            'manager': {
                'required': True,  # ✅ Q2: Manager required
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Manager'),
                    'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
                    'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Manager')
                }
            }
        }
    
    def validate_name(self, value):
        """
        Validate name uniqueness per client.
        
        Pattern:
            1. Normalize (trim)
            2. Check uniqueness in client
        """
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Team name')
            )
        
        # Normalize
        value = value.strip()
        
        # Client ID from context
        client_id = self._get_client_id_from_context()
        
        # Check uniqueness (case-insensitive)
        if Team.objects.filter(
            client_account_id=client_id,
            name__iexact=value
        ).exists():
            raise StandardizedValidationError(
                CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields=f"team name '{value}'"
                )
            )
        
        return value
    
    def validate_description(self, value):
        """
        Validate description length.
        """
        if value and len(value) > 500:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(
                    detail="Description must be 500 characters or less"
                )
            )
        return value
    
    def validate_manager(self, value):
        """
        Validate manager belongs to same client.
        """
        if value:
            client_id = self._get_client_id_from_context()
            if str(value.client_account_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        return value
    
    def validate(self, attrs):
        """
        Global validation for team creation.
        
        Steps:
            1. Inject client_account_id
            2. Validate parent team if provided
            3. Manager is already validated by Meta.extra_kwargs
        """
        try:
            # Inject client_account_id
            client_id = self._get_client_id_from_context()
            attrs['client_account_id'] = client_id
            
            # Validate parent team if provided
            if 'parent_team_id' in attrs:
                parent_id = attrs.get('parent_team_id')
                # Reuse existing validation logic from TeamSerializer
                self._validate_parent_team(parent_id, client_id, instance=None)
            
            return attrs
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            )
    
    def _validate_parent_team(self, parent_id, client_id, instance):
        """
        Validate parent team relation (reuse from TeamSerializer).
        
        Rules:
            - Parent must exist
            - Parent must belong to same client
            - No self-reference
            - No circular hierarchy
            - Max depth of 4 levels
        """
        if parent_id is None:
            return
        
        try:
            parent = Team.objects.select_related('client_account').get(id=parent_id)
        except Team.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
        
        # Tenant isolation
        if str(parent.client_account_id) != str(client_id):
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        
        # Check hierarchy depth
        depth = 1
        current = parent
        visited_ids = set()
        if instance:
            visited_ids.add(instance.id)
        
        while current.parent_team:
            current = current.parent_team
            depth += 1
            
            # Circular protection
            if current.id in visited_ids:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail="Circular team hierarchy detected."
                    )
                )
            visited_ids.add(current.id)
            
            # Max depth = 4
            if depth >= 4:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail="Maximum team hierarchy depth (4 levels) exceeded."
                    )
                )

class TeamUpdateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for team modifications (PATCH).
    
    Features:
        - All fields optional
        - Validation for hierarchy changes
        - Name uniqueness check (exclude current instance)
    """
    
    parent_team = serializers.UUIDField(
        source='parent_team_id',
        required=False,
        allow_null=True,
        write_only=True,
        help_text=_("ID of the parent team in the hierarchy.")
    )
    
    class Meta:
        model = Team
        fields = ['name', 'description', 'manager', 'parent_team']
        extra_kwargs = {
            'name': {'required': False},
            'description': {
                'required': False,
                'max_length': 500
            },
            'manager': {
                'required': False,
                'error_messages': {
                    'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
                    'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Manager')
                }
            }
        }
    
    def validate_name(self, value):
        """
        Validate name uniqueness (exclude current instance).
        """
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Team name')
            )
        
        value = value.strip()
        client_id = self._get_client_id_from_context()
        
        # Check uniqueness excluding current instance
        queryset = Team.objects.filter(
            client_account_id=client_id,
            name__iexact=value
        )
        
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)
        
        if queryset.exists():
            raise StandardizedValidationError(
                CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields=f"team name '{value}'"
                )
            )
        
        return value
    
    def validate_description(self, value):
        """Validate description length"""
        if value and len(value) > 500:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(
                    detail="Description must be 500 characters or less"
                )
            )
        return value
    
    def validate_manager(self, value):
        """Validate manager belongs to same client"""
        if value:
            client_id = self._get_client_id_from_context()
            if str(value.client_account_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        return value
    
    def validate(self, attrs):
        """
        Global validation for updates.
        
        Important:
            - Validate parent team changes (prevent circular, depth)
            - No client_account_id injection (immutable)
        """
        try:
            client_id = self._get_client_id_from_context()
            
            # Validate parent team changes if provided
            if 'parent_team_id' in attrs:
                parent_id = attrs.get('parent_team_id')
                self._validate_parent_team(parent_id, client_id, self.instance)
            
            return attrs
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            )
    
    def _validate_parent_team(self, parent_id, client_id, instance):
        """
        Validate parent team relation (same as create).
        Reused validation logic.
        """
        if parent_id is None:
            return
        
        try:
            parent = Team.objects.select_related('client_account').get(id=parent_id)
        except Team.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
        
        if str(parent.client_account_id) != str(client_id):
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        
        # No self-reference
        if instance and parent.id == instance.id:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(
                    detail="A team cannot be its own parent."
                )
            )
        
        # Check hierarchy depth
        depth = 1
        current = parent
        visited_ids = set()
        if instance:
            visited_ids.add(instance.id)
        
        while current.parent_team:
            current = current.parent_team
            depth += 1
            
            if current.id in visited_ids:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail="Circular team hierarchy detected."
                    )
                )
            visited_ids.add(current.id)
            
            if depth >= 4:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail="Maximum team hierarchy depth (4 levels) exceeded."
                    )
                )
    
    def update(self, instance, validated_data):
        """
        Update with business logic.
        
        Pattern:
            1. Apply modifications
            2. Save
            3. Post-processing if needed (denormalization, etc.)
        """
        # Apply modifications
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Post-processing if needed
        # Example: cascade updates, denormalization, etc.
        
        return instance