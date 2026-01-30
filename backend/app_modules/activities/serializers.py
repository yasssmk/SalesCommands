# app_modules/activities/serializers.py
"""
Serializers for Activity module.

Follows the same patterns as CompanyAccountSerializer and DecisionCycleSerializer.
"""

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from app_modules.accounts.models import CompanyAccount
from app_modules.contacts.models import Contact
from app_modules.decision_cycles.models import DecisionCycle, DecisionStep
from end_users.models import User
from .models import Activity
from .constants import ActivityType, ActivityStatus, ActivityOutcome, NoNextStepReason
from .services import ActivitySequenceService, SequenceScope

# ============================================================================
# HELPER SERIALIZERS
# ============================================================================

class ActivityAccountSerializer(serializers.ModelSerializer):
    """Minimal account serializer for activity responses."""
    
    class Meta:
        model = CompanyAccount
        fields = ['id', 'company_name']
        read_only_fields = fields


class ActivityContactSerializer(serializers.ModelSerializer):
    """Minimal contact serializer for activity responses."""
    
    full_name = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Contact
        fields = [
            'id', 'first_name', 'last_name', 'full_name',
            'email', 'phone_number', 'job_title', 'department_name'
        ]
        read_only_fields = fields
    
    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()
    
    def get_department_name(self, obj):
        """Get department display name from standard_department."""
        if obj.standard_department:
            return obj.standard_department.get_name_display()
        return None


class ActivityOwnerSerializer(serializers.ModelSerializer):
    """Minimal user serializer for activity owner."""
    
    full_name = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name']
        read_only_fields = fields
    
    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()

class ActivityInvitedUserSerializer(serializers.ModelSerializer):
    """Minimal user serializer for invited users."""
    
    full_name = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name']
        read_only_fields = fields
    
    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()


class ActivityDecisionCycleSerializer(serializers.ModelSerializer):
    """Minimal decision cycle serializer for activity responses."""
    
    class Meta:
        model = DecisionCycle
        fields = ['id', 'name']
        read_only_fields = fields


class ActivityDecisionStepSerializer(serializers.ModelSerializer):
    """Minimal decision step serializer for activity responses."""
    
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    
    class Meta:
        model = DecisionStep
        fields = ['id', 'name', 'stage', 'stage_display', 'status']
        read_only_fields = fields


class ActivityMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for previous/next activity references."""
    
    class Meta:
        model = Activity
        fields = ['id', 'title', 'activity_type', 'status']
        read_only_fields = fields


# ============================================================================
# LIST SERIALIZER (Performance optimized)
# ============================================================================

class ActivityListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Lightweight serializer for activity lists (performance optimized).
    
    Principles:
        - Minimum fields for table display
        - SerializerMethodField for relations (avoid N+1)
        - No deep nested serializers
    """
    
    # Display fields
    activity_type_display = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)
    outcome_display = serializers.SerializerMethodField(read_only=True)
    
    # Relations as simple objects
    account = serializers.SerializerMethodField(read_only=True)
    owner = serializers.SerializerMethodField(read_only=True)
    decision_step = serializers.SerializerMethodField(read_only=True)
    
    # Computed fields
    is_overdue = serializers.BooleanField(read_only=True)
    is_scheduled = serializers.BooleanField(read_only=True)
    contacts_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Activity
        fields = [
            # Identity
            'id', 'title',
            
            # Type & Status
            'activity_type', 'activity_type_display',
            'status', 'status_display',
            'outcome', 'outcome_display',
            
            # Scheduling
            'scheduled_date', 'scheduled_time',
            'due_date', 'completed_at',
            
            # Call to action
            'call_to_action',
            
            # Next Step Agreement
            'next_step_agreed',
            
            # Relations (simple objects)
            'account', 'owner', 'decision_step',
            
            # Computed
            'is_overdue', 'is_scheduled', 'contacts_count',
            
            # Timestamps
            'created_at', 'updated_at'
        ]

        read_only_fields = fields
    
    def get_activity_type_display(self, obj):
        return obj.get_activity_type_display() if obj.activity_type else None
    
    def get_status_display(self, obj):
        return obj.get_status_display() if obj.status else None
    
    def get_outcome_display(self, obj):
        return obj.get_outcome_display() if obj.outcome else None
    
    def get_account(self, obj):
        if obj.account:
            return {
                'id': str(obj.account.id),
                'company_name': obj.account.company_name
            }
        return None
    
    def get_owner(self, obj):
        if obj.owner:
            return {
                'id': str(obj.owner.id),
                'email': obj.owner.email,
                'full_name': f"{obj.owner.first_name or ''} {obj.owner.last_name or ''}".strip()
            }
        return None
    
    def get_decision_step(self, obj):
        if obj.decision_step:
            return {
                'id': str(obj.decision_step.id),
                'name': obj.decision_step.name,
                'stage': obj.decision_step.stage
            }
        return None
    
    def get_contacts_count(self, obj):
        return obj.contacts.count()


# ============================================================================
# DETAIL SERIALIZER
# ============================================================================

class ActivitySerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Complete serializer for activity detail view.
    """
    
    # Display fields
    activity_type_display = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)
    outcome_display = serializers.SerializerMethodField(read_only=True)
    
    # Nested serializers for relations
    account_detail = ActivityAccountSerializer(source='account', read_only=True)
    contacts_detail = ActivityContactSerializer(source='contacts', many=True, read_only=True)
    owner_detail = ActivityOwnerSerializer(source='owner', read_only=True)
    invited_users_detail = ActivityInvitedUserSerializer(source='invited_users', many=True, read_only=True)
    decision_cycle_detail = ActivityDecisionCycleSerializer(source='decision_cycle', read_only=True)
    decision_step_detail = ActivityDecisionStepSerializer(source='decision_step', read_only=True)
    
    # Previous/Next activity info
    previous_activity_info = serializers.SerializerMethodField(read_only=True)
    next_activity_info = serializers.SerializerMethodField(read_only=True)

    # Sequence context (NEW - dynamic calculation based on scope)
    # Replaces manual previous/next with calculated sequence
    sequence_context = serializers.SerializerMethodField(read_only=True)

    # Next Step Agreement (computed fields for UX logic)
    no_next_step_reason_display = serializers.SerializerMethodField(read_only=True)
    has_next_in_sequence = serializers.SerializerMethodField(read_only=True)
    effective_has_next_step = serializers.SerializerMethodField(read_only=True)
    
    # Computed fields
    is_overdue = serializers.BooleanField(read_only=True)
    is_scheduled = serializers.BooleanField(read_only=True)
    has_previous = serializers.BooleanField(read_only=True)
    has_next = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Activity
        fields = [
            # Identity
            'id', 'title',
            
            # Type & Status
            'activity_type', 'activity_type_display',
            'status', 'status_display',
            'outcome', 'outcome_display',
            'outcome_notes',
            
            # Scheduling
            'scheduled_date', 'scheduled_time',
            'due_date', 'completed_at',
            
            # Content
            'description', 'call_to_action',
            
            # Next Step Agreement
            'next_step_agreed', 'no_next_step_reason',
            'no_next_step_reason_display', 'has_next_in_sequence', 'effective_has_next_step',
            
            # Relations (IDs for write)
            
            # Relations (IDs for write)
            'account', 'decision_cycle', 'decision_step',
            
            # Relations (nested for read)
            'account_detail', 'contacts_detail', 'owner_detail', 
            'invited_users_detail',
            'decision_cycle_detail', 'decision_step_detail',
            
            # Previous/Next activity (DEPRECATED - kept for backward compatibility)
            'previous_activity', 'next_activity',
            'previous_activity_info', 'next_activity_info',
            
            # Sequence context (NEW - dynamic playlist calculation)
            'sequence_context',
            
            # Future fields (stubs)
            'transcript', 'preparation_notes',
            
            # Computed
            'is_overdue', 'is_scheduled', 'has_previous', 'has_next',
            'created_by', 'updated_by', 'created_at', 'updated_at'
        ]

        read_only_fields = [
            'id', 'activity_type_display', 'status_display', 'outcome_display',
            'account_detail', 'contacts_detail', 'owner_detail',
            'decision_cycle_detail', 'decision_step_detail',
            'previous_activity_info', 'next_activity_info',
            'no_next_step_reason_display', 'has_next_in_sequence', 'effective_has_next_step',
            'is_overdue', 'is_scheduled', 'has_previous', 'has_next',
            'created_by', 'updated_by', 'created_at', 'updated_at'
        ]
    
    def get_activity_type_display(self, obj):
        return obj.get_activity_type_display() if obj.activity_type else None
    
    def get_status_display(self, obj):
        return obj.get_status_display() if obj.status else None
    
    def get_outcome_display(self, obj):
        return obj.get_outcome_display() if obj.outcome else None
    
    def get_previous_activity_info(self, obj):
        """
        DEPRECATED: Use sequence_context.previous_activities instead.
        
        Kept for backward compatibility during frontend migration.
        Now returns first activity from sequence_context if available,
        falls back to manual previous_activity field.
        """
        # If activity belongs to a cycle, use calculated sequence
        if obj.decision_cycle_id:
            context = ActivitySequenceService.get_sequence_context(
                activity=obj,
                scope=SequenceScope.DECISION_CYCLE
            )
            if context and context.get('previous_activities'):
                # Return first previous activity for backward compatibility
                return context['previous_activities'][0]
            return None
        
        # Fallback to manual field for standalone activities
        if obj.previous_activity:
            return {
                'id': str(obj.previous_activity.id),
                'title': obj.previous_activity.title,
                'activity_type': obj.previous_activity.activity_type,
                'status': obj.previous_activity.status
            }
        return None
    
    def get_next_activity_info(self, obj):
        """
        DEPRECATED: Use sequence_context.next_activities instead.
        
        Kept for backward compatibility during frontend migration.
        Now returns first activity from sequence_context if available,
        falls back to manual next_activity field.
        """
        # If activity belongs to a cycle, use calculated sequence
        if obj.decision_cycle_id:
            context = ActivitySequenceService.get_sequence_context(
                activity=obj,
                scope=SequenceScope.DECISION_CYCLE
            )
            if context and context.get('next_activities'):
                # Return first next activity for backward compatibility
                return context['next_activities'][0]
            return None
        
        # Fallback to manual field for standalone activities
        if obj.next_activity:
            return {
                'id': str(obj.next_activity.id),
                'title': obj.next_activity.title,
                'activity_type': obj.next_activity.activity_type,
                'status': obj.next_activity.status
            }
        return None
    
    def get_sequence_context(self, obj):
        """
        Get the dynamic sequence context for this activity.
        
        Calculates previous/next activities based on:
        - decision_step.order (pipeline position)
        - COALESCE(scheduled_date, due_date)
        - COALESCE(scheduled_time, due_time)
        - created_at (fallback)
        
        Returns None if activity doesn't belong to a decision_cycle.
        
        NOTE: Uses _get_cached_sequence_context to ensure consistency
        with get_effective_has_next_step calculations.
        """
        if not obj.decision_cycle_id:
            return None
        
        # Use cached version to ensure consistency across all computed fields
        return self._get_cached_sequence_context(obj)
    
    def get_no_next_step_reason_display(self, obj):
        """
        Get the display label for no_next_step_reason.
        
        Handles both standard codes (CLOSE_WON, etc.) and custom "OTHER: text" format.
        """
        if not obj.no_next_step_reason:
            return None
        
        reason = obj.no_next_step_reason
        
        # Check if it's a standard code
        if reason in NoNextStepReason.values:
            return NoNextStepReason(reason).label
        
        # Handle "OTHER: custom text" format
        if reason.startswith('OTHER:'):
            return reason[6:].strip()  # Return the custom text
        
        # Fallback: return as-is
        return reason
    
    def get_has_next_in_sequence(self, obj):
        """
        Check if activity has PENDING next activities in its sequence.
        
        Returns:
            True: has pending (PLANNED/IN_PROGRESS) next activities
            False: no pending next activities in sequence
            None: activity is standalone (not in a cycle)
        """
        if not obj.decision_cycle_id:
            return None
        
        context = self._get_cached_sequence_context(obj)
        if context and context.get('next_activities'):
            # Only count PLANNED or IN_PROGRESS as valid "next steps"
            pending_next = [
                act for act in context['next_activities']
                if act.get('status') in ('PLANNED', 'IN_PROGRESS')
            ]
            return len(pending_next) > 0
        return False
    
    def get_effective_has_next_step(self, obj):
        """
        Determine the effective next step status for UX logic.
        
        Priority (UPDATED):
            1. If PENDING next_activities exist in sequence → True (reality wins)
            2. If next_activity FK is set and PENDING → True
            3. If next_step_agreed is explicitly set → return its value
            4. Otherwise → None (ask user to confirm)
        
        RATIONALE: If someone marked "no next step" but then a next activity
        was created, the reality (pending activities exist) should override
        the outdated explicit flag.
        
        Returns:
            True: next step exists or was agreed
            False: explicitly marked as no next step AND no pending activities
            None: unknown, UI should prompt user
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Priority 1: Check sequence context for PENDING activities in cycle
        # Reality (actual pending activities) takes precedence over past declarations
        if obj.decision_cycle_id:
            context = self._get_cached_sequence_context(obj)
            logger.info(f"[DEBUG effective_has_next_step] Activity {obj.id}: Priority 1 - checking sequence context")
            
            if context and context.get('next_activities'):
                all_next = context['next_activities']
                
                # Filter to only count PLANNED or IN_PROGRESS activities
                pending_next = [
                    act for act in all_next
                    if act.get('status') in ('PLANNED', 'IN_PROGRESS')
                ]
                logger.info(f"[DEBUG effective_has_next_step] Activity {obj.id}: pending_next count={len(pending_next)}")
                
                if pending_next:
                    logger.info(f"[DEBUG effective_has_next_step] Activity {obj.id}: returning True (has pending next in sequence)")
                    return True
        
        # Priority 2: Check legacy next_activity FK for standalone
        if obj.next_activity_id:
            logger.info(f"[DEBUG effective_has_next_step] Activity {obj.id}: Priority 2 - checking legacy FK")
            if obj.next_activity and obj.next_activity.status in ('PLANNED', 'IN_PROGRESS'):
                logger.info(f"[DEBUG effective_has_next_step] Activity {obj.id}: returning True (legacy FK pending)")
                return True
        
        # Priority 3: Explicit value (only applies when no pending activities exist)
        if obj.next_step_agreed is not None:
            logger.info(f"[DEBUG effective_has_next_step] Activity {obj.id}: Priority 3 - explicit next_step_agreed={obj.next_step_agreed}")
            return obj.next_step_agreed
        
        # Priority 4: Unknown - UI should prompt
        logger.info(f"[DEBUG effective_has_next_step] Activity {obj.id}: Priority 4 - returning None (unknown)")
        return None
    
    def _get_cached_sequence_context(self, obj):
        """
        Get sequence context with caching to avoid duplicate calculations.
        
        Uses instance._sequence_context_cache as temporary storage.
        """
        cache_attr = '_sequence_context_cache'
        
        if not hasattr(obj, cache_attr):
            if obj.decision_cycle_id:
                setattr(obj, cache_attr, ActivitySequenceService.get_sequence_context(
                    activity=obj,
                    scope=SequenceScope.DECISION_CYCLE
                ))
            else:
                setattr(obj, cache_attr, None)
        
        return getattr(obj, cache_attr)


# ============================================================================
# CREATE SERIALIZER
# ============================================================================

class ActivityCreateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for activity creation.
    """
    
    account_id = serializers.UUIDField(write_only=True)
    contact_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        default=list
    )
    invited_user_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        default=list
    )
    decision_cycle_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    decision_step_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    previous_activity_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Activity
        fields = [
            # Required
            'title', 'activity_type', 'account_id',
            
            # Optional
            'description', 'call_to_action',
            'status', 'outcome', 'outcome_notes',
            'scheduled_date', 'scheduled_time', 'due_date',
            
            # Relations
            'contact_ids', 'invited_user_ids',
            'decision_cycle_id', 'decision_step_id',
            'previous_activity_id',
            
            # Future fields
            'transcript', 'preparation_notes'
        ]
        extra_kwargs = {
            'title': {
                'required': True,
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Title'),
                }
            },
            'activity_type': {
                'required': True,
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Activity Type'),
                }
            }
        }
    
    def validate_title(self, value):
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Title')
            )
        return value.strip()
    
    def validate(self, attrs):
        """Global validation for activity creation."""
        try:
            client_id = self._get_client_id_from_context()
            attrs['client_id'] = client_id
            
            # =================================================================
            # Validate account
            # =================================================================
            account_id = attrs.pop('account_id')
            try:
                account = CompanyAccount.objects.get(id=account_id, client_id=client_id)
                attrs['account'] = account
            except CompanyAccount.DoesNotExist:
                raise StandardizedValidationError(
                    CoreErrorMessages.NOT_FOUND.format(resource='Account')
                )
            
            # =================================================================
            # REQUIRED: At least one contact
            # =================================================================
            contact_ids = attrs.pop('contact_ids', [])
            if not contact_ids:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='At least one contact')
                )
            
            contacts = Contact.objects.filter(
                id__in=contact_ids,
                client_id=client_id,
                account=account
            )
            if contacts.count() != len(contact_ids):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field='Some contacts not found or do not belong to this account')
                )
            attrs['_contacts'] = list(contacts)
            
            # =================================================================
            # REQUIRED: At least one date (scheduled_date OR due_date)
            # =================================================================
            scheduled_date = attrs.get('scheduled_date')
            due_date = attrs.get('due_date')
            
            if not scheduled_date and not due_date:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='Scheduled date or due date')
                )
            
            # =================================================================
            # Validate invited_users (optional)
            # =================================================================
            invited_user_ids = attrs.pop('invited_user_ids', [])
            if invited_user_ids:
                invited_users = User.objects.filter(
                    id__in=invited_user_ids,
                    client_account_id=client_id
                )
                if invited_users.count() != len(invited_user_ids):
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(field='Some invited users not found')
                    )
                attrs['_invited_users'] = list(invited_users)
            
            # =================================================================
            # Validate decision_cycle (optional)
            # =================================================================
            decision_cycle_id = attrs.pop('decision_cycle_id', None)
            if decision_cycle_id:
                try:
                    decision_cycle = DecisionCycle.objects.get(
                        id=decision_cycle_id,
                        client_id=client_id,
                        account=account
                    )
                    attrs['decision_cycle'] = decision_cycle
                except DecisionCycle.DoesNotExist:
                    raise StandardizedValidationError(
                        CoreErrorMessages.OBJECT_NOT_FOUND
                    )
            
            # =================================================================
            # Validate decision_step (optional, requires cycle)
            # =================================================================
            decision_step_id = attrs.pop('decision_step_id', None)
            if decision_step_id:
                decision_cycle = attrs.get('decision_cycle')
                if not decision_cycle:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_DATA.format(
                            detail='Decision step requires a decision cycle'
                        )
                    )
                try:
                    decision_step = DecisionStep.objects.get(
                        id=decision_step_id,
                        cycle=decision_cycle
                    )
                    attrs['decision_step'] = decision_step
                except DecisionStep.DoesNotExist:
                    raise StandardizedValidationError(
                        CoreErrorMessages.NOT_FOUND.format(resource='Decision Step')
                    )
            
            # RULE: If cycle is provided, step is REQUIRED (pipeline steps are fixed)
            if attrs.get('decision_cycle') and not attrs.get('decision_step'):
                raise StandardizedValidationError(
                    "A pipeline step is required when linking to a decision cycle"
                )
            
            # =================================================================
            # Validate previous_activity (optional)
            # =================================================================
            previous_activity_id = attrs.pop('previous_activity_id', None)
            if previous_activity_id:
                try:
                    previous_activity = Activity.objects.get(
                        id=previous_activity_id,
                        client_id=client_id,
                        account=account
                    )
                    attrs['previous_activity'] = previous_activity
                except Activity.DoesNotExist:
                    raise StandardizedValidationError(
                        CoreErrorMessages.NOT_FOUND.format(resource='Previous Activity')
                    )
            
            return attrs
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            )
    
    def create(self, validated_data):
        """Create activity with proper audit fields and M2M."""
        user = self.context.get('request').user if self.context.get('request') else None
        contacts = validated_data.pop('_contacts', [])
        invited_users = validated_data.pop('_invited_users', [])
        client_id = validated_data.pop('client_id', None)
        
        # Set owner to current user
        validated_data['owner'] = user
        
        # Create instance
        instance = Activity(**validated_data)
        instance.save(user=user, client_id=client_id)
        
        # Set M2M contacts
        if contacts:
            instance.contacts.set(contacts)
        
        # Set M2M invited_users
        if invited_users:
            instance.invited_users.set(invited_users)
        
        # Update previous activity's next_activity if needed
        if instance.previous_activity:
            instance.previous_activity.next_activity = instance
            instance.previous_activity.save(user=user)
        
        return instance


# ============================================================================
# UPDATE SERIALIZER
# ============================================================================

class ActivityUpdateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for activity updates.
    
    Business Rules:
        - contacts cannot be empty (at least 1 required)
        - outcome is only valid when status=COMPLETED
        - reopening (from COMPLETED to other status) clears outcome
    """

    owner_id = serializers.UUIDField(write_only=True, required=False)
    
    contact_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    invited_user_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    decision_cycle_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    decision_step_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    next_activity_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Activity
        fields = [
            # Editable
            'title', 'activity_type',
            'description', 'call_to_action',
            'status', 'outcome', 'outcome_notes',
            'scheduled_date', 'scheduled_time', 'due_date',
            
            # Next Step Agreement
            'next_step_agreed', 'no_next_step_reason',
            
            # Relations
            'owner_id', 'contact_ids', 'invited_user_ids',
            'decision_cycle_id', 'decision_step_id',
            'next_activity_id',
            
            # Future fields
            'transcript', 'preparation_notes'
        ]
    
    def validate(self, attrs):
        """Validate update data with status/outcome business rules."""
        try:
            client_id = self._get_client_id_from_context()
            instance = self.instance
            account = instance.account
            
            # =================================================================
            # STATUS CHANGE LOGIC
            # =================================================================
            new_status = attrs.get('status')
            current_status = instance.status
            
            if new_status and new_status != current_status:
                # Rule: If reopening (from COMPLETED to non-COMPLETED), clear outcome
                if current_status == ActivityStatus.COMPLETED and new_status != ActivityStatus.COMPLETED:
                    attrs['outcome'] = None
                    attrs['outcome_notes'] = None
                    attrs['completed_at'] = None
                
                # Rule: If completing, set completed_at
                if new_status == ActivityStatus.COMPLETED and current_status != ActivityStatus.COMPLETED:
                    from django.utils import timezone
                    attrs['completed_at'] = timezone.now()
            
            # =================================================================
            # OUTCOME VALIDATION
            # =================================================================
            new_outcome = attrs.get('outcome')
            final_status = new_status if new_status else current_status
            
            # Rule: outcome is only valid if status is COMPLETED
            if new_outcome and final_status != ActivityStatus.COMPLETED:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail='Outcome can only be set when activity is completed'
                    )
                )
            
            # =================================================================
            # CONTACTS VALIDATION (cannot be empty)
            # =================================================================
            if 'contact_ids' in attrs:
                contact_ids = attrs.pop('contact_ids')
                if contact_ids is not None:
                    if len(contact_ids) == 0:
                        raise StandardizedValidationError(
                            CoreErrorMessages.REQUIRED_FIELD.format(field='At least one contact')
                        )
                    contacts = Contact.objects.filter(
                        id__in=contact_ids,
                        client_id=client_id,
                        account=account
                    )
                    if contacts.count() != len(contact_ids):
                        raise StandardizedValidationError(
                            CoreErrorMessages.INVALID_FIELD.format(field='Some contacts not found')
                        )
                    attrs['_contacts'] = list(contacts)
            
            # =================================================================
            # OWNER VALIDATION
            # =================================================================
            if 'owner_id' in attrs:
                owner_id = attrs.pop('owner_id')
                if owner_id:
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
                        attrs['owner'] = owner
                    except User.DoesNotExist:
                        raise StandardizedValidationError(
                            CoreErrorMessages.OBJECT_NOT_FOUND
                        )
                    
            # =================================================================
            # INVITED USERS VALIDATION
            # =================================================================
            if 'invited_user_ids' in attrs:
                invited_user_ids = attrs.pop('invited_user_ids')
                if invited_user_ids is not None:
                    if invited_user_ids:
                        invited_users = User.objects.filter(
                            id__in=invited_user_ids,
                            client_account_id=client_id
                        )
                        if invited_users.count() != len(invited_user_ids):
                            raise StandardizedValidationError(
                                CoreErrorMessages.INVALID_FIELD.format(field='Some invited users not found')
                            )
                        attrs['_invited_users'] = list(invited_users)
                    else:
                        attrs['_invited_users'] = []
            
            # =================================================================
            # DECISION CYCLE VALIDATION
            # =================================================================
            if 'decision_cycle_id' in attrs:
                decision_cycle_id = attrs.pop('decision_cycle_id')
                if decision_cycle_id:
                    try:
                        decision_cycle = DecisionCycle.objects.get(
                            id=decision_cycle_id,
                            client_id=client_id,
                            account=account
                        )
                        attrs['decision_cycle'] = decision_cycle
                    except DecisionCycle.DoesNotExist:
                        raise StandardizedValidationError(
                            CoreErrorMessages.NOT_FOUND.format(resource='Decision Cycle')
                        )
                else:
                    attrs['decision_cycle'] = None
                    # Clear step if cycle is cleared
                    if 'decision_step_id' not in attrs:
                        attrs['decision_step'] = None
            
            # =================================================================
            # DECISION STEP VALIDATION
            # =================================================================
            if 'decision_step_id' in attrs:
                decision_step_id = attrs.pop('decision_step_id')
                if decision_step_id:
                    # Get cycle from attrs or instance
                    decision_cycle = attrs.get('decision_cycle', instance.decision_cycle)
                    if not decision_cycle:
                        raise StandardizedValidationError(
                            CoreErrorMessages.INVALID_DATA.format(
                                detail='Decision step requires a decision cycle'
                            )
                        )
                    try:
                        decision_step = DecisionStep.objects.get(
                            id=decision_step_id,
                            cycle=decision_cycle
                        )
                        attrs['decision_step'] = decision_step
                    except DecisionStep.DoesNotExist:
                        raise StandardizedValidationError(
                            CoreErrorMessages.NOT_FOUND.format(resource='Decision Step')
                        )
                else:
                    attrs['decision_step'] = None
            
            # =================================================================
            # NEXT ACTIVITY VALIDATION
            # =================================================================
            if 'next_activity_id' in attrs:
                next_activity_id = attrs.pop('next_activity_id')
                if next_activity_id:
                    try:
                        next_activity = Activity.objects.get(
                            id=next_activity_id,
                            client_id=client_id,
                            account=account
                        )
                        # Prevent circular reference
                        if next_activity.id == instance.id:
                            raise StandardizedValidationError(
                                CoreErrorMessages.INVALID_DATA.format(
                                    detail='Activity cannot be its own next activity'
                                )
                            )
                        attrs['next_activity'] = next_activity
                    except Activity.DoesNotExist:
                        raise StandardizedValidationError(
                            CoreErrorMessages.NOT_FOUND.format(resource='Next Activity')
                        )
                else:
                    attrs['next_activity'] = None
        
            # =================================================================
            # NEXT STEP AGREEMENT VALIDATION
            # =================================================================
            if 'next_step_agreed' in attrs:
                next_step_agreed = attrs.get('next_step_agreed')
                no_next_step_reason = attrs.get('no_next_step_reason')
                
                # Rule: If setting next_step_agreed to False, reason is REQUIRED
                if next_step_agreed is False:
                    if not no_next_step_reason:
                        raise StandardizedValidationError(
                            CoreErrorMessages.REQUIRED_FIELD.format(field='Reason for no next step')
                        )
                    
                    # Validate reason format: must be standard code or "OTHER: text"
                    valid_codes = [choice[0] for choice in NoNextStepReason.choices]
                    is_standard_code = no_next_step_reason in valid_codes
                    is_other_format = no_next_step_reason.startswith('OTHER:') and len(no_next_step_reason) > 6
                    
                    if not is_standard_code and not is_other_format:
                        raise StandardizedValidationError(
                            CoreErrorMessages.INVALID_FIELD.format(
                                field=f"Reason must be one of {', '.join(valid_codes)} or 'OTHER: <custom text>'"
                            )
                        )
                
                # Rule: If setting next_step_agreed to True or None, clear no_next_step_reason
                elif next_step_agreed is True or next_step_agreed is None:
                    attrs['no_next_step_reason'] = None
            
            return attrs
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            )
    
    def update(self, instance, validated_data):
        """Update activity with proper audit fields and M2M."""
        user = self.context.get('request').user if self.context.get('request') else None
        
        # Handle M2M contacts
        contacts = validated_data.pop('_contacts', None)
        if contacts is not None:
            instance.contacts.set(contacts)
        
        # Handle M2M invited_users
        invited_users = validated_data.pop('_invited_users', None)
        if invited_users is not None:
            instance.invited_users.set(invited_users)
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save(user=user)
        return instance