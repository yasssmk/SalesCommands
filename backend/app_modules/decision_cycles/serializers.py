# app_modules/decision_cycles/serializers.py
"""
Serializers for Decision Cycle module.

Follows the same patterns as CompanyAccountSerializer for consistency.
"""

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from app_modules.core_modules.models import StandardDepartment
from .models import DecisionCycle, DecisionStep, DecisionStepContact
from .constants import DecisionStage, DecisionStepStatus


# ============================================================================
# HELPER SERIALIZERS
# ============================================================================

class DecisionStepContactSerializer(serializers.ModelSerializer):
    """Serializer for junction table between DecisionStep and Contact."""
    
    contact_name = serializers.SerializerMethodField(read_only=True)
    contact_email = serializers.SerializerMethodField(read_only=True)
    contact_job_title = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = DecisionStepContact
        fields = ['id', 'contact', 'contact_name', 'contact_email', 'contact_job_title', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_contact_name(self, obj):
        if obj.contact:
            return f"{obj.contact.first_name or ''} {obj.contact.last_name or ''}".strip()
        return None
    
    def get_contact_email(self, obj):
        return obj.contact.email if obj.contact else None
    
    def get_contact_job_title(self, obj):
        return obj.contact.job_title if obj.contact else None


class StepMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for step references (previous/next)."""
    
    class Meta:
        model = DecisionStep
        fields = ['id', 'name', 'stage', 'status']
        read_only_fields = fields


# ============================================================================
# DECISION STEP SERIALIZERS
# ============================================================================

class DecisionStepListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Lightweight serializer for step lists (timeline display).
    """
    
    stage_display = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.SerializerMethodField(read_only=True)
    previous_step_info = serializers.SerializerMethodField(read_only=True)
    next_step_info = serializers.SerializerMethodField(read_only=True)
    is_current = serializers.BooleanField(read_only=True)
    has_parallel_steps = serializers.BooleanField(read_only=True)
    contacts_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = DecisionStep
        fields = [
            # Identity
            'id', 'name',
            
            # Stage & Status
            'stage', 'stage_display',
            'status', 'status_display',
            
            # Linked list
            'previous_step', 'previous_step_info',
            'next_step_info',
            
            # Flags
            'is_current', 'has_parallel_steps',
            
            # Summary fields
            'stakeholder', 'department_name',
            'expected_days', 'contacts_count',
            
            # Timestamps
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_stage_display(self, obj):
        return obj.get_stage_display() if obj.stage else None
    
    def get_status_display(self, obj):
        return obj.get_status_display() if obj.status else None
    
    def get_department_name(self, obj):
        if obj.standard_department:
            return obj.standard_department.get_name_display()
        return None
    
    def get_previous_step_info(self, obj):
        if obj.previous_step:
            return {
                'id': str(obj.previous_step.id),
                'name': obj.previous_step.name
            }
        return None
    
    def get_next_step_info(self, obj):
        next_step = obj.next_step
        if next_step:
            return {
                'id': str(next_step.id),
                'name': next_step.name
            }
        return None
    
    def get_contacts_count(self, obj):
        return obj.contacts.count()


class DecisionStepSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Complete serializer for step detail view.
    """
    
    stage_display = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.SerializerMethodField(read_only=True)
    previous_step_info = serializers.SerializerMethodField(read_only=True)
    next_step_info = serializers.SerializerMethodField(read_only=True)
    is_current = serializers.BooleanField(read_only=True)
    has_parallel_steps = serializers.BooleanField(read_only=True)
    step_contacts = DecisionStepContactSerializer(many=True, read_only=True)
    
    class Meta:
        model = DecisionStep
        fields = [
            # Identity
            'id', 'name', 'cycle',
            
            # Stage & Status
            'stage', 'stage_display',
            'status', 'status_display',
            
            # Linked list
            'previous_step', 'previous_step_info',
            'next_step_info',
            
            # Flags
            'is_current', 'has_parallel_steps',
            
            # Details
            'stakeholder',
            'standard_department', 'department_name',
            'description', 'goal',
            'influence_score',
            'criterias', 'metrics',
            'expected_days',
            
            # Contacts
            'step_contacts',
            
            # Audit
            'created_by', 'updated_by',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'stage_display', 'status_display', 'department_name',
            'previous_step_info', 'next_step_info', 'is_current',
            'has_parallel_steps', 'step_contacts',
            'created_by', 'updated_by', 'created_at', 'updated_at'
        ]
    
    def get_stage_display(self, obj):
        return obj.get_stage_display() if obj.stage else None
    
    def get_status_display(self, obj):
        return obj.get_status_display() if obj.status else None
    
    def get_department_name(self, obj):
        if obj.standard_department:
            return obj.standard_department.get_name_display()
        return None
    
    def get_previous_step_info(self, obj):
        if obj.previous_step:
            return {
                'id': str(obj.previous_step.id),
                'name': obj.previous_step.name
            }
        return None
    
    def get_next_step_info(self, obj):
        next_step = obj.next_step
        if next_step:
            return {
                'id': str(next_step.id),
                'name': next_step.name
            }
        return None


class DecisionStepCreateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for step creation.
    """
    
    cycle_id = serializers.UUIDField(write_only=True)
    previous_step_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    standard_department_id = serializers.PrimaryKeyRelatedField(
        source='standard_department',
        queryset=StandardDepartment.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
    )
    contact_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True
    )
    
    class Meta:
        model = DecisionStep
        fields = [
            'cycle_id',
            'name', 'stage', 'status',
            'previous_step_id',
            'stakeholder', 'standard_department_id',
            'description', 'goal',
            'influence_score', 'criterias', 'metrics',
            'expected_days',
            'contact_ids'
        ]
        extra_kwargs = {
            'name': {
                'required': True,
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Name'),
                }
            },
            'stage': {
                'required': True,
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Stage'),
                }
            },
            'status': {
                'required': False,
                'default': DecisionStepStatus.NOT_STARTED
            }
        }
    
    def validate_name(self, value):
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Name')
            )
        return value.strip()
    
    def validate_stage(self, value):
        valid_stages = [choice[0] for choice in DecisionStage.choices]
        if value not in valid_stages:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='Stage')
            )
        return value
    
    def validate_status(self, value):
        if not value:
            return DecisionStepStatus.NOT_STARTED
        
        valid_statuses = [choice[0] for choice in DecisionStepStatus.choices]
        if value not in valid_statuses:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='Status')
            )
        return value
    
    def validate(self, attrs):
        # Validate cycle exists
        cycle_id = attrs.get('cycle_id')
        if cycle_id:
            try:
                cycle = DecisionCycle.objects.get(id=cycle_id)
                attrs['cycle'] = cycle
            except DecisionCycle.DoesNotExist:
                raise StandardizedValidationError(
                    CoreErrorMessages.NOT_FOUND.format(resource='Decision Cycle')
                )
        
        # Validate previous_step exists and belongs to same cycle
        previous_step_id = attrs.pop('previous_step_id', None)
        if previous_step_id:
            try:
                previous_step = DecisionStep.objects.get(id=previous_step_id)
                if previous_step.cycle_id != cycle_id:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field='Previous step must belong to the same cycle'
                        )
                    )
                attrs['previous_step'] = previous_step
            except DecisionStep.DoesNotExist:
                raise StandardizedValidationError(
                    CoreErrorMessages.NOT_FOUND.format(resource='Previous Step')
                )
        
        return attrs
    
    def create(self, validated_data):
        contact_ids = validated_data.pop('contact_ids', [])
        validated_data.pop('cycle_id', None)
        
        instance = super().create(validated_data)
        
        # Add contacts
        if contact_ids:
            from app_modules.contacts.models import Contact
            contacts = Contact.objects.filter(id__in=contact_ids)
            for contact in contacts:
                DecisionStepContact.objects.create(
                    step=instance,
                    contact=contact,
                    client_id=instance.client_id
                )
        
        return instance


class DecisionStepUpdateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for step updates.
    """
    
    previous_step_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    standard_department_id = serializers.PrimaryKeyRelatedField(
        source='standard_department',
        queryset=StandardDepartment.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
    )
    contact_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True
    )
    
    class Meta:
        model = DecisionStep
        fields = [
            'name', 'stage', 'status',
            'previous_step_id',
            'stakeholder', 'standard_department_id',
            'description', 'goal',
            'influence_score', 'criterias', 'metrics',
            'expected_days',
            'contact_ids'
        ]
    
    def validate(self, attrs):
        # Validate previous_step if provided
        previous_step_id = attrs.pop('previous_step_id', None)
        if previous_step_id is not None:
            if previous_step_id:
                try:
                    previous_step = DecisionStep.objects.get(id=previous_step_id)
                    if previous_step.cycle_id != self.instance.cycle_id:
                        raise StandardizedValidationError(
                            CoreErrorMessages.INVALID_FIELD.format(
                                field='Previous step must belong to the same cycle'
                            )
                        )
                    attrs['previous_step'] = previous_step
                except DecisionStep.DoesNotExist:
                    raise StandardizedValidationError(
                        CoreErrorMessages.NOT_FOUND.format(resource='Previous Step')
                    )
            else:
                attrs['previous_step'] = None
        
        return attrs
    
    def update(self, instance, validated_data):
        contact_ids = validated_data.pop('contact_ids', None)
        
        instance = super().update(instance, validated_data)
        
        # Update contacts if provided
        if contact_ids is not None:
            from app_modules.contacts.models import Contact
            
            # Clear existing
            instance.step_contacts.all().delete()
            
            # Add new
            contacts = Contact.objects.filter(id__in=contact_ids)
            for contact in contacts:
                DecisionStepContact.objects.create(
                    step=instance,
                    contact=contact,
                    client_id=instance.client_id
                )
        
        return instance


# ============================================================================
# DECISION CYCLE SERIALIZERS
# ============================================================================

class DecisionCycleListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Lightweight serializer for cycle lists.
    """
    
    account_name = serializers.SerializerMethodField(read_only=True)
    steps_count = serializers.IntegerField(read_only=True)
    validated_steps_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = DecisionCycle
        fields = [
            'id', 'name', 'description',
            'account', 'account_name',
            'is_active',
            'steps_count', 'validated_steps_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_account_name(self, obj):
        return obj.account.company_name if obj.account else None


class DecisionCycleSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Complete serializer for cycle detail view.
    """
    
    account_name = serializers.SerializerMethodField(read_only=True)
    steps = DecisionStepListSerializer(many=True, read_only=True)
    steps_count = serializers.IntegerField(read_only=True)
    validated_steps_count = serializers.IntegerField(read_only=True)
    estimated_timeline_days = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = DecisionCycle
        fields = [
            'id', 'name', 'description',
            'account', 'account_name',
            'is_active',
            'steps', 'steps_count', 'validated_steps_count',
            'estimated_timeline_days',
            'created_by', 'updated_by',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'account_name', 'steps', 'steps_count',
            'validated_steps_count', 'estimated_timeline_days',
            'created_by', 'updated_by', 'created_at', 'updated_at'
        ]
    
    def get_account_name(self, obj):
        return obj.account.company_name if obj.account else None


class DecisionCycleCreateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for cycle creation.
    """
    
    account_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = DecisionCycle
        fields = ['account_id', 'name', 'description', 'is_active']
        extra_kwargs = {
            'name': {
                'required': True,
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Name'),
                }
            }
        }
    
    def validate_name(self, value):
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Name')
            )
        return value.strip()
    
    def validate(self, attrs):
        account_id = attrs.get('account_id')
        if account_id:
            from app_modules.accounts.models import CompanyAccount
            try:
                account = CompanyAccount.objects.get(id=account_id)
                attrs['account'] = account
            except CompanyAccount.DoesNotExist:
                raise StandardizedValidationError(
                    CoreErrorMessages.NOT_FOUND.format(resource='Account')
                )
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('account_id', None)
        return super().create(validated_data)


class DecisionCycleUpdateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for cycle updates.
    """
    
    class Meta:
        model = DecisionCycle
        fields = ['name', 'description', 'is_active']