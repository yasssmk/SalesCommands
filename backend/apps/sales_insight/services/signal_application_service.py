# apps/sales_insight/services/signal_application_service.py

from django.utils import timezone
from django.db import transaction
from ..models import Signal
from apps.accounts.models import Contact
# from apps.accounts_app.account_product_detail.models import AccountProductDetail
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages

class SignalApplicationService:
    """
    Service responsible for applying approved signals to target entities.
    Handles the business logic of updating entities based on signal data.
    """
    
    @classmethod
    def apply_signal(cls, signal, user=None):
        """
        Apply a signal to its target entity.
        
        Args:
            signal: The Signal to apply
            user: User performing the action
            
        Returns:
            bool: Success status
            
        Raises:
            StandardizedValidationError: If signal cannot be applied
        """
        # Validate signal is in the correct status
        if signal.status != Signal.Status.APPROVED:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_OPERATION.format(
                    operation="Only approved signals can be applied"
                )
            )
        
        # Apply signal based on entity type
        with transaction.atomic():
            success = False
            
            if signal.entity_type == Signal.EntityType.ACCOUNT:
                success = cls._apply_to_account(signal, user)
            elif signal.entity_type == Signal.EntityType.CONTACT:
                success = cls._apply_to_contact(signal, user)
            elif signal.entity_type == Signal.EntityType.ACCOUNT_PRODUCT:
                success = cls._apply_to_account_product(signal, user)
            else:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Unknown entity type: {signal.entity_type}"
                    )
                )
                
            if success:
                # Update signal status
                signal.status = Signal.Status.APPLIED
                signal.applied_date = timezone.now()
                signal.save(update_fields=['status', 'applied_date'])
                
            return success
        
    @classmethod
    def _apply_to_account(cls, signal, user):
        """Apply signal to account with comprehensive historical tracking"""
        account = signal.account
        field_name = signal.field_name
        value = signal.value
        
        # Qualification fields 
        qualification_fields = [
            'objectives', 'compelling_events', 'motivations', 
            'key_kpis', 'criteria', 'pain_points', 'implications',
        ]
        
        # Ensure historical_data exists
        if not hasattr(account, 'historical_data') or not account.historical_data:
            account.historical_data = {}
        
        # Current value before update
        current_value = getattr(account, field_name, None)
        
        # Update the field
        setattr(account, field_name, value)
        
        # Prepare history entry
        history_entry = {
            'old_value': current_value,
            'new_value': value,
            'changed_at': timezone.now().isoformat(),
            'changed_by': str(user.id) if user else None,
            'source': 'signal',
            'signal_id': str(signal.id)
        }
        
        # Add signal-specific details
        if signal:
            history_entry.update({
                'signal_category': signal.category,
                'signal_source': signal.source,
                'confirmation_count': signal.confirmation_count
            })
        
        # Initialize field history if needed
        if field_name not in account.historical_data:
            account.historical_data[field_name] = []
        
        # Add to historical data
        account.historical_data[field_name].append(history_entry)
        
        # Track signal update in signal metadata
        if hasattr(account, 'track_signal_update'):
            account.track_signal_update(signal, field_name, current_value, value)
        
        # Save the account
        account.save(user=user, update_fields=[field_name, 'historical_data'])
        
        return True

    @classmethod
    def _apply_to_contact(cls, signal, user):
        """Apply signal to contact with comprehensive historical tracking"""
        contact = signal.contact
        field_name = signal.field_name
        value = signal.value
        
        # Qualification fields 
        qualification_fields = [
            'objectives', 'compelling_events', 'motivations', 
            'key_kpis', 'criteria', 'pain_points', 'implications',
        ]
        
        # Ensure historical_data exists
        if not hasattr(contact, 'historical_data') or not contact.historical_data:
            contact.historical_data = {}
        
        # Current value before update
        current_value = getattr(contact, field_name, None)
        
        # Update the field
        setattr(contact, field_name, value)
        
        # Prepare history entry
        history_entry = {
            'old_value': current_value,
            'new_value': value,
            'changed_at': timezone.now().isoformat(),
            'changed_by': str(user.id) if user else None,
            'source': 'signal',
            'signal_id': str(signal.id)
        }
        
        # Add signal-specific details
        if signal:
            history_entry.update({
                'signal_category': signal.category,
                'signal_source': signal.source,
                'confirmation_count': signal.confirmation_count
            })
        
        # Initialize field history if needed
        if field_name not in contact.historical_data:
            contact.historical_data[field_name] = []
        
        # Add to historical data
        contact.historical_data[field_name].append(history_entry)
        
        # Track signal update in signal metadata
        if hasattr(contact, 'track_signal_update'):
            contact.track_signal_update(signal, field_name, current_value, value)
        
        # Save the contact
        contact.save(user=user, update_fields=[field_name, 'historical_data'])
        
        return True
        
    @classmethod
    def bulk_apply_signals(cls, signals, user=None):
        """
        Apply multiple signals in bulk.
        
        Args:
            signals: QuerySet or list of Signal objects to apply
            user: User performing the action
            
        Returns:
            dict: Summary of results with counts
        """
        results = {
            'total': len(signals),
            'success_count': 0,
            'failed_count': 0,
            'failed_ids': []
        }
        
        for signal in signals:
            try:
                success = cls.apply_signal(signal, user)
                if success:
                    results['success_count'] += 1
                else:
                    results['failed_count'] += 1
                    results['failed_ids'].append(str(signal.id))
            except Exception as e:
                results['failed_count'] += 1
                results['failed_ids'].append(str(signal.id))
                
        return results