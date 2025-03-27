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
        """
        Apply signal to account using the appropriate historical tracking method.
        
        Args:
            signal: Signal to apply
            user: User applying the signal
            
        Returns:
            bool: Success indicator
        """
        try:
            account = signal.account
            field_name = signal.field_name
            value = signal.value
            
            # For qualification category signals, use update_qualification_field
            if signal.category == Signal.Category.QUALIFICATION:
                return account.update_qualification_field(field_name, value, user, signal)
            
            # For profile category signals, use update_tracked_field
            if signal.category == Signal.Category.PROFILE:
                return account.update_tracked_field(field_name, value, user)
            
            # For other categories, choose based on field name
            json_array_fields = [
                'objectives', 'motivations', 'metrics', 
                'pain_points', 'implications', 'partners'
            ]
            
            if field_name in json_array_fields:
                return account.update_qualification_field(field_name, value, user, signal)
            else:
                return account.update_tracked_field(field_name, value, user)
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_OPERATION.format(
                    operation=f"Error applying signal: {str(e)}"
                )
            )

    @classmethod
    def _apply_to_contact(cls, signal, user):
        """Apply signal to contact with the updated field structure"""
        try:
            contact = signal.contact
            field_name = signal.field_name
            value = signal.value
            
            # Qualification JSON fields
            json_array_fields = [
                'objectives', 'motivations', 'metrics', 
                'pain_points', 'implications'
            ]
            
            # Profile fields
            profile_fields = [
                'first_name', 'last_name', 'job_title', 'department',
                'has_buying_authority', 'influence_level', 'email', 'phone'
            ]
            
            # For JSON array fields (qualifications)
            if field_name in json_array_fields:
                # Single item to add to array
                if isinstance(value, dict):
                    if hasattr(contact, 'add_qualification_item'):
                        return contact.add_qualification_item(field_name, value, user, signal)
                # Complete array replacement
                elif isinstance(value, list):
                    if hasattr(contact, 'update_qualification_field'):
                        return contact.update_qualification_field(field_name, value, user, signal)
            
            # For profile fields (regular contact properties)
            elif field_name in profile_fields:
                if hasattr(contact, 'update_tracked_field'):
                    return contact.update_tracked_field(field_name, value, user)
            
            # Fallback: use the most appropriate method available
            if hasattr(contact, 'update_qualification_field'):
                return contact.update_qualification_field(field_name, value, user, signal)
            elif hasattr(contact, 'update_tracked_field'):
                return contact.update_tracked_field(field_name, value, user)
            
            # Last resort: direct update with historical tracking
            from apps.core_apps.services.historical_tracking_service import HistoricalTrackingService
            return HistoricalTrackingService.update_field(
                instance=contact,
                field_name=field_name,
                new_value=value,
                user=user,
                signal=signal,
                update_model=True
            )
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_OPERATION.format(
                    operation=f"Error applying signal: {str(e)}"
                )
            )
        
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