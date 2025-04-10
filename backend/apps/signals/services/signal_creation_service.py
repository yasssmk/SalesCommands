# apps/signals/services/signal_creation_service.py

from ..models import Signal
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from ..serializers.signal_serializer import SignalBulkSerializer
from django.db import transaction
from django.utils import timezone

class SignalCreationService:
    """Service for creating signals consistently across the application."""
    
    @classmethod
    def create_signal_for_field(cls, instance, field_name, value, source, user=None,
                            department=None, contact=None, auto_approve=False):
        """
        Create a signal for a field.
        
        Args:
            instance: Model instance (Account, TechStack, etc.)
            field_name: Field name for the signal
            value: Value for the signal
            source: Source of the signal (manual_entry, ai_analysis, etc.)
            user: User creating the signal
            department: Optional department for the signal
            contact: Optional contact for the signal
            auto_approve: Whether to automatically approve the signal
            
        Returns:
            Signal: Created signal
        """
        # Skip if no value or empty list
        if value is None or (isinstance(value, list) and len(value) == 0):
            return None
        
        # Get category from Signal model's mapping
        category = Signal.FIELD_CATEGORIES.get(field_name)
        if not category:
            raise StandardizedValidationError({
                CoreErrorMessages.INVALID_FIELD: f"Unknown field: {field_name}"
            })
        
        # Get account from the entity
        account = instance if hasattr(instance, 'company_name') else instance.account
        
        # Determine entity type (default to ACCOUNT)
        entity_type = Signal.EntityType.ACCOUNT
        
        # Create metadata based on entity type
        metadata = {}
        if hasattr(instance, 'tech_name'):  # It's a TechStack
            metadata['tech_stack_id'] = str(instance.id)
            metadata['tech_name'] = instance.tech_name
        
        # Set status based on auto_approve flag or source
        status = Signal.Status.PENDING
        approved_by = None
        approved_at = None
        
        # Auto-approve for manual entries or when explicitly requested
        if auto_approve or source == 'manual_entry':
            status = Signal.Status.APPROVED
            approved_by = user
            approved_at = timezone.now()
        
        # Prepare signal data
        signal_data = {
            'account': account,
            'entity_type': entity_type,
            'category': category,
            'field_name': field_name,
            'value': value,
            'status': status,
            'source': source,
            'source_contact': contact,
            'source_department': department,
            'client_id': account.client_id,
            'created_by': user,
            'updated_by': user,
            'approved_by': approved_by,
            'approved_at': approved_at,
            'metadata': metadata or None
        }

        serializer = SignalBulkSerializer(data=signal_data)
        if not serializer.is_valid():
            errors = serializer.errors
            detail = errors.get('non_field_errors', errors)
            raise StandardizedValidationError({
                CoreErrorMessages.INVALID_DATA: {
                    'detail': f"Invalid value for field '{field_name}': {detail}"
                }
            })
        # Use validated data
        signal_data = serializer.validated_data

        signal = Signal.objects.create(**signal_data)
        
        return signal
    
    @classmethod
    def create_signals_from_dict(cls, instance, data_dict, source, user=None, 
                                department=None, contact=None, auto_approve=False):
        """
        Create signals for multiple fields from a dictionary.
        
        Args:
            instance: Model instance
            data_dict: Dictionary of field_name -> value pairs
            source: Source of the signals
            user: User creating the signals
            department: Optional department for the signals
            contact: Optional contact for the signals
            auto_approve: Whether to automatically approve the signals
            
        Returns:
            list: Created signals
        """
        created_signals = []
        
        for field_name, value in data_dict.items():
            try:
                signal = cls.create_signal_for_field(
                    instance=instance, 
                    field_name=field_name, 
                    value=value, 
                    source=source,
                    user=user,
                    department=department,
                    contact=contact,
                    auto_approve=auto_approve
                )
                if signal:
                    created_signals.append(signal)
            except StandardizedValidationError as e:
                # Log the error but continue with other fields
                print(f"Error creating signal for {field_name}: {str(e)}")
                continue
        
        return created_signals
    
    @classmethod
    @transaction.atomic
    def bulk_create_signals(cls, signals_data, auto_approve=False):
        """
        Efficiently create multiple signals in a single transaction.
        
        Args:
            signals_data: List of signal data dictionaries
            auto_approve: Whether to automatically approve the signals
            
        Returns:
            list: Created Signal objects
        """
        if not signals_data:
            return []
            
        # Apply auto-approval if requested
        if auto_approve:
            now = timezone.now()
            for data in signals_data:
                data['status'] = Signal.Status.APPROVED
                data['approved_at'] = now
                data['approved_by'] = data.get('created_by')
            
        # Validate with serializer
        serializer = SignalBulkSerializer(data=signals_data, many=True)
        
        if serializer.is_valid():
            return Signal.objects.bulk_create([
                Signal(**data) for data in serializer.validated_data
            ])
        else:
            # Return only valid signals if there are validation errors
            valid_signals = []
            errors = []
            
            for idx, item_data in enumerate(signals_data):
                if idx not in serializer.errors:
                    valid_signals.append(Signal(**item_data))
                else:
                    error = {
                        'index': idx,
                        'field_name': item_data.get('field_name'),
                        'errors': serializer.errors[idx]
                    }
                    errors.append(error)
                    print(f"Validation error for signal: {error}")
            
            if not valid_signals:
                raise StandardizedValidationError({
                    'detail': 'All signals failed validation',
                    'errors': errors
                })
                    
            return Signal.objects.bulk_create(valid_signals)
    
    @classmethod
    def create_manual_signal(cls, account, field_name, value, entity_type, user, 
                           source='manual_entry', **related_entities):
        """
        Create a signal manually with auto-approval.
        
        Args:
            account: Account object
            field_name: Field name
            value: Signal value
            entity_type: Entity type (ACCOUNT, ACCOUNT_PRODUCT, etc.)
            user: User creating the signal
            source: Source of the signal (default: manual_entry)
            **related_entities: Additional related entities (contact, department, etc.)
            
        Returns:
            Signal: Created and approved signal
        """
        # Get category from field name
        category = Signal.FIELD_CATEGORIES.get(field_name)
        if not category:
            raise StandardizedValidationError({
                CoreErrorMessages.INVALID_FIELD: f"Unknown field: {field_name}"
            })
        
        # Prepare signal data with auto-approval
        signal_data = {
            'account': account,
            'entity_type': entity_type,
            'category': category,
            'field_name': field_name,
            'value': value,
            'status': Signal.Status.APPROVED,
            'source': source,
            'client_id': account.client_id,
            'created_by': user,
            'updated_by': user,
            'approved_by': user,
            'approved_at': timezone.now()
        }
        
        # Add related entities
        for key, value in related_entities.items():
            if value is not None:
                signal_data[key] = value
        
        # Validate and create signal
        serializer = SignalBulkSerializer(data=signal_data)
        if not serializer.is_valid():
            errors = serializer.errors
            detail = errors.get('non_field_errors', errors)
            raise StandardizedValidationError({
                CoreErrorMessages.INVALID_DATA: {
                    'detail': f"Invalid signal data: {detail}"
                }
            })
        
        # Create and return signal
        signal = Signal.objects.create(**serializer.validated_data)
        return signal