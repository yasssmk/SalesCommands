# apps/signals/services/signal_application_service.py

from django.utils import timezone
from django.db import transaction
from ..models import Signal

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
            raise StandardizedValidationError({
                CoreErrorMessages.INVALID_OPERATION: "Only approved signals can be applied"
            })
        
        # Apply signal based on entity type and category
        with transaction.atomic():
            success = False
            
            if signal.entity_type == Signal.EntityType.ACCOUNT:
                if signal.category == Signal.Category.TECH_STACK:
                    # If it's a tech stack signal for an account, find the relevant tech stack
                    success = cls._apply_to_techstack(signal, user)
                else:
                    # Otherwise it's a regular account signal
                    success = cls._apply_to_account(signal, user)
            elif signal.entity_type == Signal.EntityType.ACCOUNT_PRODUCT:
                success = cls._apply_to_account_product(signal, user)
            else:
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_FIELD: f"Unknown entity type: {signal.entity_type}"
                })
                
            if success:
                # Update signal status
                signal.status = Signal.Status.APPLIED
                signal.applied_date = timezone.now()
                signal.save(update_fields=['status', 'applied_date'])
                
            return success
        
    @classmethod
    def _apply_to_account(cls, signal, user):
        """
        Apply signal to account. For qualification data, we just mark the signal as applied.
        For direct model fields, we update the account model.
        """
        try:
            account = signal.account
            field_name = signal.field_name
            value = signal.value
            
            # For qualification category signals, the signal itself is the source of truth
            if signal.category == Signal.Category.QUALIFICATION:
                # Track the signal application in signal_metadata
                if not account.signal_metadata:
                    account.signal_metadata = {}
                    
                # Initialize field entry if needed
                if field_name not in account.signal_metadata:
                    account.signal_metadata[field_name] = {
                        'applied_signals': [],
                        'last_application': None
                    }
                
                # Add application record
                application_record = {
                    'signal_id': str(signal.id),
                    'applied_at': timezone.now().isoformat(),
                    'applied_by': str(user.id) if user else None,
                    'value': value,
                    'source_contact_id': str(signal.source_contact.id) if signal.source_contact else None,
                    'source_department_id': str(signal.source_department.id) if signal.source_department else None
                }
                
                account.signal_metadata[field_name]['applied_signals'].append(application_record)
                account.signal_metadata[field_name]['last_application'] = application_record
                
                # Also track in historical_data for audit trail
                if hasattr(account, 'track_field_change'):
                    account.track_field_change(
                        field_name=field_name,
                        old_value=None,  # We don't track previous values for qualification data
                        new_value=value,
                        user=user,
                        signal=signal
                    )
                
                account.save(update_fields=['signal_metadata', 'historical_data'])
                return True
            
            # For PROFILE category signals, update direct account fields
            if signal.category == Signal.Category.PROFILE:
                # Only update certain profile fields that are on the model
                direct_fields = ['company_size', 'annual_revenue']
                
                if field_name in direct_fields:
                    # Track the change using historical tracking
                    old_value = getattr(account, field_name, None)
                    setattr(account, field_name, value)
                    
                    # Record in historical data
                    if hasattr(account, 'track_field_change'):
                        account.track_field_change(field_name, old_value, value, user, signal)
                    
                    # Also track in signal_metadata
                    if not account.signal_metadata:
                        account.signal_metadata = {}
                        
                    if field_name not in account.signal_metadata:
                        account.signal_metadata[field_name] = {
                            'applied_signals': [],
                            'last_application': None
                        }
                    
                    application_record = {
                        'signal_id': str(signal.id),
                        'applied_at': timezone.now().isoformat(),
                        'applied_by': str(user.id) if user else None,
                        'old_value': old_value,
                        'new_value': value,
                        'source_contact_id': str(signal.source_contact.id) if signal.source_contact else None,
                        'source_department_id': str(signal.source_department.id) if signal.source_department else None
                    }
                    
                    account.signal_metadata[field_name]['applied_signals'].append(application_record)
                    account.signal_metadata[field_name]['last_application'] = application_record
                    
                    account.save(update_fields=[field_name, 'historical_data', 'signal_metadata'])
                    return True
                
                # For other profile fields, just mark as applied without updating model
                return True
                
            # Unknown category, just mark as applied
            return True
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError({
                CoreErrorMessages.INVALID_OPERATION: f"Error applying signal: {str(e)}"
            })
    @classmethod
    def _apply_to_techstack(cls, signal, user):
        """
        Apply tech stack signal, finding the relevant tech stack or creating it if needed.
        
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
            
            # Get tech stack name from signal metadata
            tech_stack_name = None
            if signal.metadata and 'tech_stack_name' in signal.metadata:
                tech_stack_name = signal.metadata['tech_stack_name']
            elif signal.metadata and 'tech_name' in signal.metadata:
                tech_stack_name = signal.metadata['tech_name']
            
            # Find the relevant tech stack or create one
            tech_stack = None
            if tech_stack_name:
                from apps.accounts.models import TechStack
                # Try to find existing tech stack
                tech_stack = TechStack.objects.filter(
                    account=account,
                    tech_name__iexact=tech_stack_name
                ).first()
                
                # Create if not found
                if not tech_stack:
                    tech_stack = TechStack.objects.create(
                        account=account,
                        tech_name=tech_stack_name,
                        client_id=account.client_id,
                        created_by=user
                    )
            
            # If we couldn't determine the tech stack, store the signal at account level
            if not tech_stack:
                if hasattr(account, 'track_field_change'):
                    account.track_field_change(
                        field_name=f"tech_stack_{field_name}",
                        old_value=None,
                        new_value=value,
                        user=user,
                        signal=signal
                    )
                return True
                
            # Track the signal application in tech stack's historical_data
            if hasattr(tech_stack, 'track_field_change'):
                tech_stack.track_field_change(
                    field_name=field_name,
                    old_value=None,  # We don't have a previous value
                    new_value=value,
                    user=user,
                    signal=signal
                )
                
            # Update the signal with tech stack reference
            if not signal.metadata:
                signal.metadata = {}
                
            signal.metadata['applied_to_tech_stack_id'] = str(tech_stack.id)
            signal.save(update_fields=['metadata'])
                
            return True
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError({
                CoreErrorMessages.INVALID_OPERATION: f"Error applying tech stack signal: {str(e)}"
            })

    @classmethod
    def _apply_to_account_product(cls, signal, user):
        """Apply signal to account product relationship."""
        try:
            apr = signal.account_product_relationship
            field_name = signal.field_name
            value = signal.value
            
            # Track application in historical_data
            if hasattr(apr, 'track_field_change'):
                apr.track_field_change(
                    field_name=field_name,
                    old_value=None,  # We don't have a previous value
                    new_value=value,
                    user=user,
                    signal=signal
                )
            
            return True
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError({
                CoreErrorMessages.INVALID_OPERATION: f"Error applying signal: {str(e)}"
            })
        
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
                results['failed_ids'].append({
                    'id': str(signal.id),
                    'error': str(e)
                })
                
        return results