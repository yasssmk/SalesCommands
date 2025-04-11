# apps/signals/services/signal_manager.py

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from ..models.base_signal_model import BaseSignal
from ..models.qualification_signal_model import QualificationSignal
from ..models.tech_stack_signal_model import TechStackSignal
from ..models.profile_signal_model import ProfileSignal


class SignalManager:
    """
    Service class to handle complex signal operations and business logic.
    Centralizes signal lifecycle management, approval workflows, and merging.
    """
    
    @classmethod
    def get_signal_model_for_category(cls, category):
        """
        Get the appropriate signal model class based on category.
        
        Args:
            category (str): Signal category identifier
            
        Returns:
            Model class for the specified category
        """
        category_map = {
            'QUALIFICATION': QualificationSignal,
            'TECH_STACK': TechStackSignal,
            'PROFILE': ProfileSignal,
        }
        
        return category_map.get(category.upper())
    
    @classmethod
    def create_signal(cls, data, user=None, client_id=None):
        """
        Create a new signal with the appropriate model based on category.
        
        Args:
            data (dict): Signal data
            user: User creating the signal
            client_id: Client ID for the signal
            
        Returns:
            Newly created signal instance
        """
        try:
            # Determine which model to use based on category
            category = data.pop('category', None)
            if not category:
                raise StandardizedValidationError({
                    'category': CoreErrorMessages.REQUIRED_FIELD.format(field='category')
                })
                
            signal_model = cls.get_signal_model_for_category(category)
            if not signal_model:
                raise StandardizedValidationError({
                    'category': CoreErrorMessages.INVALID_FIELD.format(field='category')
                })
            
            # Auto-approve manual entries
            if data.get('source') == 'manual_entry':
                data['status'] = BaseSignal.Status.APPROVED
            
            # Create signal with proper client ID and user tracking
            
                signal = signal_model(**data)
                signal.save(user=user, client_id=client_id)
                return signal
                    # Auto-approve manual entries
        except ValidationError as e:
            raise StandardizedValidationError(e.message_dict)
        except Exception as e:
            raise StandardizedValidationError(str(e))
    
    @classmethod
    @transaction.atomic
    def approve_signal(cls, signal, user, updated_value=None, source_contact=None, source_department=None):
        """
        Approve a pending signal.
        
        Args:
            signal: Signal instance to approve
            user: User approving the signal
            updated_value: Optional new value for the signal
            source_contact: Optional source contact to assign
            source_department: Optional source department to assign
            
        Returns:
            Updated signal instance
        """
        try:
            if not signal:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
                
            if signal.status != BaseSignal.Status.PENDING:
                raise StandardizedValidationError({
                    'status': "Only pending signals can be approved"
                })
            
            # Update signal value if provided
            if updated_value is not None:
                signal.value = updated_value
            
            # Update source attribution if provided
            if source_contact:
                # Verify contact belongs to the signal's account
                if hasattr(source_contact, 'account_id') and signal.account_id != source_contact.account_id:
                    raise StandardizedValidationError({
                        'source_contact': "Contact must belong to the signal's account"
                    })
                    
                signal.source_contact = source_contact
                
                # Auto-assign department if not set
                if not signal.source_department and hasattr(source_contact, 'standard_department'):
                    signal.source_department = source_contact.standard_department
                    
            if source_department:
                signal.source_department = source_department
            
            # Set approval information
            signal.status = BaseSignal.Status.APPROVED
            signal.approved_by = user
            signal.approved_at = timezone.now()
            
            signal.full_clean()  # Validate before saving
            signal.save(user=user)
            return signal
            
        except ValidationError as e:
            raise StandardizedValidationError(e.message_dict)
        except StandardizedValidationError:
            raise  # Re-raise StandardizedValidationError as is
        except Exception as e:
            raise StandardizedValidationError(str(e))
    
    @classmethod
    def reject_signal(cls, signal, user, reason=None):
        """
        Reject a pending signal.
        
        Args:
            signal: Signal instance to reject
            user: User rejecting the signal
            reason: Optional reason for rejection
            
        Returns:
            Updated signal instance
        """
        try:
            if not signal:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
                
            if signal.status != BaseSignal.Status.PENDING:
                raise StandardizedValidationError({
                    'status': "Only pending signals can be rejected"
                })
            
            # Store rejection reason in metadata
            if reason:
                if not signal.metadata:
                    signal.metadata = {}
                signal.metadata['rejection_reason'] = reason
                signal.metadata['rejected_at'] = timezone.now().isoformat()
                signal.metadata['rejected_by'] = str(user.id) if user else None
            
            signal.status = BaseSignal.Status.REJECTED
            signal.save(user=user)
            
            return signal
            
        except ValidationError as e:
            raise StandardizedValidationError(e.message_dict)
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(str(e))
    
    def merge_signals(cls, source_signal, target_signal, user):
        """
        Merge source signal into target signal, combining confirmation history.
        
        Args:
            source_signal: Signal to merge from
            target_signal: Signal to merge into
            user: User performing the merge
            
        Returns:
            Updated target signal instance
        """
        try:
            # Validate signals can be merged
            if not source_signal.can_be_merged_with(target_signal):
                field_name_check = ''
                if hasattr(source_signal, 'field_name') and hasattr(target_signal, 'field_name'):
                    if source_signal.field_name != target_signal.field_name:
                        field_name_check = "Signals have different field names. "
                        
                raise StandardizedValidationError({
                    'error': f"Cannot merge these signals. {field_name_check}Ensure both signals are compatible."
                })
                
            # Update confirmation count on target signal
            target_signal.confirmation_count += source_signal.confirmation_count
            target_signal.last_confirmed_at = timezone.now()
            
            # Track merge history
            target_signal.add_merge_history(source_signal, user)
            
            # Mark source signal as merged
            source_signal.mark_as_merged(target_signal, user)
            
            # Save target signal
            target_signal.save(user=user)
            
            return target_signal
            
        except Exception as e:
            raise StandardizedValidationError(str(e))
    
    @classmethod
    def confirm_signal(cls, signal, user, source_contact=None):
        """
        Confirm a signal, incrementing its confirmation count.
        
        Args:
            signal: Signal to confirm
            user: User confirming the signal
            source_contact: Optional contact who confirmed the information
            
        Returns:
            Updated signal instance
        """
        if signal.status != BaseSignal.Status.APPROVED:
            raise StandardizedValidationError({
                CoreErrorMessages.INVALID_OPERATION: "Only approved signals can be confirmed"
            })
        
        # Track confirmation history
        if source_contact:
            if not signal.metadata:
                signal.metadata = {}
                
            if 'confirmation_history' not in signal.metadata:
                signal.metadata['confirmation_history'] = []
                
            # Add confirmation record
            signal.metadata['confirmation_history'].append({
                'contact_id': str(source_contact.id),
                'contact_name': f"{getattr(source_contact, 'first_name', '')} {getattr(source_contact, 'last_name', '')}".strip(),
                'timestamp': timezone.now().isoformat(),
                'confirmed_by': str(user.id)
            })
        
        # Increment confirmation count
        signal.confirmation_count += 1
        signal.last_confirmed_at = timezone.now()
        signal.save(user=user)
        
        return signal
    
    @classmethod
    def get_account_signals(cls, account_id, category=None, status='APPROVED', **filters):
        """
        Get signals for an account with optional filters.
        
        Args:
            account_id: Account ID to filter by
            category: Signal category (QUALIFICATION, PROFILE, TECH_STACK)
            status: Signal status to filter by (default: APPROVED)
            **filters: Additional filters
            
        Returns:
            QuerySet of signals
        """
        try:
            # Determine which model to use based on category
            if category:
                signal_model = cls.get_signal_model_for_category(category)
                queryset = signal_model.objects.filter(account_id=account_id)
            else:
                # If no category specified, union queries from all signal types
                qualification_signals = QualificationSignal.objects.filter(account_id=account_id)
                profile_signals = ProfileSignal.objects.filter(account_id=account_id)
                tech_stack_signals = TechStackSignal.objects.filter(account_id=account_id)
                
                # This is a placeholder - in practice, you would use union queries
                # or combine results programmatically based on your requirements
                queryset = qualification_signals
                
            # Apply status filter
            if status:
                queryset = queryset.filter(status=status)
                
            # Apply additional filters
            for field, value in filters.items():
                if value is not None:
                    queryset = queryset.filter(**{field: value})
                    
            return queryset
            
        except Exception as e:
            raise StandardizedValidationError(str(e))