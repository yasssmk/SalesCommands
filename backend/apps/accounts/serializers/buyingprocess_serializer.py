# apps/accounts/serializers/buyingprocess_serializer.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.core_apps.serializers import AccountLinkedSerializerMixin, HistoricalTrackingSerializerMixin
from apps.accounts.serializers.contact_serializer import ContactSerializer
from apps.accounts.models.buyingProcess import BuyingProcess, BuyingProcessStep, BuyingProcessStepContact
from apps.accounts.models.contacts import Contact
from app_modules.core_modules.models import StandardDepartment

class BuyingProcessStepContactSerializer(serializers.ModelSerializer):
    """Serializer for junction table between BuyingProcessStep and Contact"""
    contact = ContactSerializer(read_only=True)
    
    class Meta:
        model = BuyingProcessStepContact
        fields = ['id', 'contact', 'created_at']
        read_only_fields = ['id', 'created_at']

class BuyingProcessStepSerializer(AccountLinkedSerializerMixin,
                                 ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for BuyingProcessStep with related contacts.
    """
    contacts = ContactSerializer(many=True, read_only=True)
    contact_ids = serializers.PrimaryKeyRelatedField(
        source='contacts',
        queryset=Contact.objects.all(),
        write_only=True,
        many=True,
        required=False
    )
    
    previous_step_id = serializers.PrimaryKeyRelatedField(
        source='previous_step',
        queryset=BuyingProcessStep.objects.all(),
        write_only=True,
        required=True,
        allow_null=True
    )
    
    next_step = serializers.SerializerMethodField()
    
    standard_department_id = serializers.PrimaryKeyRelatedField(
        source='standard_department',
        queryset=StandardDepartment.objects.all(),
        write_only=True,
        required=False,
        allow_null=True
    )
    
    standard_department_name = serializers.SerializerMethodField(read_only=True)
    
    step_contacts = BuyingProcessStepContactSerializer(many=True, read_only=True)
    
    process = serializers.SerializerMethodField(read_only=True)
    process_id = serializers.IntegerField(
        write_only=True,
        required=True
    )
    
    class Meta:
        model = BuyingProcessStep
        fields = [
            'id',
            'process',
            'process_id',
            'account',
            'previous_step',
            'previous_step_id',
            'next_step',
            'stakeholder',
            'standard_department',
            'standard_department_id',
            'standard_department_name',
            'step_description',
            'step_goal',
            'influence_score',
            'criterias',
            'metrics',
            'average_time_in_days',
            'contacts',
            'contact_ids',
            'step_contacts',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'process', 'next_step', 'created_at', 'updated_at']
        
    
    def get_process(self, obj):
        """Get the process data"""
        if obj.process:
            return {
                'id': obj.process.id,
                'name': obj.process.name
            }
        return None
    
    def get_next_step(self, obj):
        """Get the next step data"""
        next_step = obj.next_step
        if next_step:
            return {
                'id': next_step.id,
                'step_description': next_step.step_description
            }
        return None
    
    def get_standard_department_name(self, obj):
        """Get the standard department name"""
        if obj.standard_department:
            return obj.standard_department.get_name_display()
        return None
    
    def validate_standard_department(self, value):
        """Validate that the standard department exists"""
        if value is None:
            return value
            
        try:
            if not StandardDepartment.objects.filter(id=value.id).exists():
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="Department")
                )
        except Exception:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Department")
            )
            
        return value
    
    def validate_process_id(self, value):
        """Validate that the process exists"""
        try:
            BuyingProcess.objects.get(id=value)
            return value
        except BuyingProcess.DoesNotExist:
            raise StandardizedValidationError(
                CoreErrorMessages.OBJECT_NOT_FOUND
            )
    
    def validate_contact_ids(self, value):
        """Validate that contact_ids is a list"""
        if not isinstance(value, list):
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="contact_ids must be a list")
            )
        return value
    
    def validate(self, data):
        """Validate buying process step data"""
        data = super().validate(data)
        
        # Get process from process_id
        process_id = data.pop('process_id', None)
        process=None
        if process_id:
            try:
                process = BuyingProcess.objects.get(id=process_id)
                data['process'] = process
                
                # Set account from process if not provided
                if 'account' not in data:
                    data['account'] = process.account
            except BuyingProcess.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
        
        # Ensure account belongs to the client
        client_id = self._get_client_id_from_context()
        account = data.get('account')
        
        if account and str(account.client_id) != str(client_id):
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        
        # Validate process belongs to account
        process = data.get('process')
        if process and account and process.account_id != account.id:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field="Process must belong to the same account"
                )
            )
        
        # Validate previous step belongs to the same process
        previous_step = data.get('previous_step')
        if previous_step and process and previous_step.process_id != process.id:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field="Previous step must belong to the same process"
                )
            )
        
        # Validate that contacts belong to the same account
        if 'contacts' in data:
            contacts = data['contacts']
            invalid_contacts = [
                contact for contact in contacts
                if contact.account_id != account.id
            ]
            
            if invalid_contacts:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field="Contacts must belong to the same account"
                    )
                )
        
        return data
    
    def create(self, validated_data):
        """Create buying process step with correct previous/next step linking"""
        contacts = validated_data.pop('contacts', [])
        previous_step = validated_data.get('previous_step')

        process_id = validated_data.pop('process_id', None)
        if process_id:
            process = BuyingProcess.objects.get(id=process_id)
            validated_data['process'] = process
            
            # Set account from process if not already set
            if 'account' not in validated_data:
                validated_data['account'] = process.account
        
        # Handle case when previous_step is null - place at beginning
        if previous_step is None:
            # Find the first step in the process
            first_step = BuyingProcessStep.objects.filter(
                process=validated_data['process'],
                previous_step__isnull=True
            ).first()
            
            # If there is a first step, make our new step the first
            if first_step:
                # Set first step's previous to our new step
                validated_data['next_step_id'] = first_step.id
        
        # Create the step
        instance = super().create(validated_data)
        
        # Update next step reference
        if previous_step and previous_step.next_steps.exists():
            # If previous step already had a next step, update the chain
            old_next = previous_step.next_steps.first()
            if old_next:
                # Set our new step's next to be the old next
                old_next.previous_step = instance
                old_next.save(update_fields=['previous_step'])
        
        # Add contacts
        if contacts:
            instance.contacts.set(contacts)
            
        return instance
    
    def update(self, instance, validated_data):
        """Update buying process step with correct previous/next step linking"""
        contacts = validated_data.pop('contacts', None)
        old_previous_step = instance.previous_step
        new_previous_step = validated_data.get('previous_step')
        
        # Update step fields
        instance = super().update(instance, validated_data)
        
        # If previous step changed, update the chain
        if old_previous_step != new_previous_step:
            # If this step had a previous step, update its next pointer
            if old_previous_step:
                # Find the old previous step's next step (might not be this instance
                # if the chain was broken previously)
                old_next = old_previous_step.next_steps.first()
                if old_next and old_next.id == instance.id:
                    # Clear the next pointer from old previous step
                    old_next.previous_step = None
                    old_next.save(update_fields=['previous_step'])
            
            # If new previous step already had a next step, update the chain
            if new_previous_step and new_previous_step.next_steps.exists():
                old_next = new_previous_step.next_steps.first()
                if old_next:
                    # Set our next to be the old next
                    old_next.previous_step = instance
                    old_next.save(update_fields=['previous_step'])
                    
                    # And set our previous to be the new previous
                    instance.previous_step = new_previous_step
                    instance.save(update_fields=['previous_step'])
        
        # Update contacts if provided
        if contacts is not None:
            instance.contacts.set(contacts)
            
        return instance


class BuyingProcessSerializer(AccountLinkedSerializerMixin, HistoricalTrackingSerializerMixin,
                             ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for BuyingProcess model with nested steps.
    """
    steps = BuyingProcessStepSerializer(many=True, read_only=True)
    estimated_timeline_days = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = BuyingProcess
        fields = [
            'id',
            'name',
            'description',
            'estimated_timeline_days',
            'product',
            'account',
            'steps',
            'historical_data',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'estimated_timeline_days', 'historical_data', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validate buying process data"""
        data = super().validate(data)
        
        # Ensure account belongs to the client
        client_id = self._get_client_id_from_context()
        account = data.get('account')
        
        if account and str(account.client_id) != str(client_id):
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        
        # Validate uniqueness of account+name combination
        self.validate_client_scoped_uniqueness(
            data=data,
            unique_fields=['account', 'name'],
            model_class=BuyingProcess,
            error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                fields='Account and Name'
            )
        )
        
        # If product is provided, validate uniqueness of account+product combination
        if 'product' in data and data.get('product'):
            self.validate_client_scoped_uniqueness(
                data=data,
                unique_fields=['account', 'product'],
                model_class=BuyingProcess,
                error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields='Account and Product'
                )
            )
        
        # Ensure product belongs to the client if provided
        product = data.get('product')
        if product and str(product.client_id) != str(client_id):
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        
        return data