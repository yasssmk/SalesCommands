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
from .constants import ActivityType, ActivityStatus, ActivityOutcome


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
    
    class Meta:
        model = Contact
        fields = ['id', 'first_name', 'last_name', 'full_name', 'email', 'job_title']
        read_only_fields = fields
    
    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()


class ActivityOwnerSerializer(serializers.ModelSerializer):
    """Minimal user serializer for activity owner."""
    
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
    decision_cycle_detail = ActivityDecisionCycleSerializer(source='decision_cycle', read_only=True)
    decision_step_detail = ActivityDecisionStepSerializer(source='decision_step', read_only=True)
    
    # Previous/Next activity info
    previous_activity_info = serializers.SerializerMethodField(read_only=True)
    next_activity_info = serializers.SerializerMethodField(read_only=True)
    
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
            
            # Next Step Agreement
            'next_step_agreed', 'no_next_step_reason',
            
            # Description & CTA
            'description', 'call_to_action',
            
            # Scheduling
            'scheduled_date', 'scheduled_time',
            'due_date', 'completed_at',
            
            # Relations (IDs)
            'account', 'owner',
            'decision_cycle', 'decision_step',
            
            # Relations (detailed)
            'account_detail', 'contacts_detail', 'owner_detail',
            'decision_cycle_detail', 'decision_step_detail',
            
            # Linked list
            'previous_activity', 'next_activity',
            'previous_activity_info', 'next_activity_info',
            
            # Future fields (stubs)
            'transcript', 'preparation_notes',
            
            # Computed
            'is_overdue', 'is_scheduled',
            'has_previous', 'has_next',
            
            # Audit
            'created_by', 'updated_by',
            'created_at', 'updated_at'
        ]

        read_only_fields = [
            'id', 'activity_type_display', 'status_display', 'outcome_display',
            'account_detail', 'contacts_detail', 'owner_detail',
            'decision_cycle_detail', 'decision_step_detail',
            'previous_activity_info', 'next_activity_info',
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
        if obj.previous_activity:
            return {
                'id': str(obj.previous_activity.id),
                'title': obj.previous_activity.title,
                'activity_type': obj.previous_activity.activity_type,
                'status': obj.previous_activity.status
            }
        return None
    
    def get_next_activity_info(self, obj):
        if obj.next_activity:
            return {
                'id': str(obj.next_activity.id),
                'title': obj.next_activity.title,
                'activity_type': obj.next_activity.activity_type,
                'status': obj.next_activity.status
            }
        return None


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
            'contact_ids',
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
            
            # Validate account
            account_id = attrs.pop('account_id', None)
            if not account_id:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='Account')
                )
            
            try:
                account = CompanyAccount.objects.get(id=account_id, client_id=client_id)
                attrs['account'] = account
            except CompanyAccount.DoesNotExist:
                raise StandardizedValidationError(
                    CoreErrorMessages.NOT_FOUND.format(resource='Account')
                )
            
            # Validate contacts (optional)
            contact_ids = attrs.pop('contact_ids', [])
            if contact_ids:
                contacts = Contact.objects.filter(
                    id__in=contact_ids,
                    client_id=client_id,
                    account=account
                )
                if contacts.count() != len(contact_ids):
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(field='Some contacts not found or not belonging to this account')
                    )
                attrs['_contacts'] = contacts
            
            # Validate decision_cycle (optional)
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
                        CoreErrorMessages.NOT_FOUND.format(resource='Decision Cycle')
                    )
            
            # Validate decision_step (optional)
            decision_step_id = attrs.pop('decision_step_id', None)
            if decision_step_id:
                try:
                    decision_step = DecisionStep.objects.get(
                        id=decision_step_id,
                        client_id=client_id
                    )
                    # Auto-set decision_cycle if not provided
                    if not attrs.get('decision_cycle'):
                        attrs['decision_cycle'] = decision_step.cycle
                    attrs['decision_step'] = decision_step
                except DecisionStep.DoesNotExist:
                    raise StandardizedValidationError(
                        CoreErrorMessages.NOT_FOUND.format(resource='Decision Step')
                    )
            
            # Validate previous_activity (optional)
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
        client_id = validated_data.pop('client_id', None)
        
        # Set owner to current user
        validated_data['owner'] = user
        
        # Create instance
        instance = Activity(**validated_data)
        instance.save(user=user, client_id=client_id)
        
        # Set M2M contacts
        if contacts:
            instance.contacts.set(contacts)
        
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
    """
    
    contact_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    decision_cycle_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    decision_step_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    
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
            'contact_ids',
            'decision_cycle_id', 'decision_step_id',
            
            # Future fields
            'transcript', 'preparation_notes'
        ]
    
    def validate(self, attrs):
        """Validate update data."""
        try:
            client_id = self._get_client_id_from_context()
            instance = self.instance
            account = instance.account
            
            # Validate contacts (optional)
            if 'contact_ids' in attrs:
                contact_ids = attrs.pop('contact_ids')
                if contact_ids:
                    contacts = Contact.objects.filter(
                        id__in=contact_ids,
                        client_id=client_id,
                        account=account
                    )
                    if contacts.count() != len(contact_ids):
                        raise StandardizedValidationError(
                            CoreErrorMessages.INVALID_FIELD.format(field='Some contacts not found')
                        )
                    attrs['_contacts'] = contacts
                else:
                    attrs['_contacts'] = []
            
            # Validate decision_cycle (optional)
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
            
            # Validate decision_step (optional)
            if 'decision_step_id' in attrs:
                decision_step_id = attrs.pop('decision_step_id')
                if decision_step_id:
                    try:
                        decision_step = DecisionStep.objects.get(
                            id=decision_step_id,
                            client_id=client_id
                        )
                        attrs['decision_step'] = decision_step
                    except DecisionStep.DoesNotExist:
                        raise StandardizedValidationError(
                            CoreErrorMessages.NOT_FOUND.format(resource='Decision Step')
                        )
                else:
                    attrs['decision_step'] = None
            
            return attrs
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            )
    
    def update(self, instance, validated_data):
        """Update activity with proper audit fields."""
        user = self.context.get('request').user if self.context.get('request') else None
        contacts = validated_data.pop('_contacts', None)
        
        # Update fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Auto-set completed_at if status changed to COMPLETED
        if validated_data.get('status') == ActivityStatus.COMPLETED and not instance.completed_at:
            from django.utils import timezone
            instance.completed_at = timezone.now()
        
        instance.save(user=user)
        
        # Update M2M contacts if provided
        if contacts is not None:
            instance.contacts.set(contacts)
        
        return instance