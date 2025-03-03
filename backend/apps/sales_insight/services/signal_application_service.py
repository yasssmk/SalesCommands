# apps/sales_insight/services/signal_application_service.py

from django.utils import timezone
from django.db import transaction
from ..models import Signal
from apps.accounts_app.accounts.models import Account
from apps.accounts_app.org_units.models import AccountOrganizationUnit
from apps.accounts_app.contacts.models import Contact
from apps.accounts_app.account_product_detail.models import AccountProductDetail
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
            elif signal.entity_type == Signal.EntityType.ORG_UNIT:
                success = cls._apply_to_org_unit(signal, user)
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
        """Apply signal to account"""
        account = signal.account
        field_name = signal.field_name
        value = signal.value
        
        # Qualification fields vs. regular fields
        if field_name in ['objectives', 'compelling_events', 'motivations', 
                        'key_kpis', 'criteria', 'pain_points', 'implications',
                        'current_tech_stack', 'partners', 'buying_process', 
                        'projects', 'budget', 'new_budget_start_date']:
            # Use QualificationModel's update method to track history
            if hasattr(account, 'update_qualification_field'):
                account.update_qualification_field(field_name, value, user)
                return True
        else:
            # Regular field update
            if hasattr(account, field_name):
                # Simple fields like type, classification, etc.
                current_value = getattr(account, field_name)
                setattr(account, field_name, value)
                
                # Save with the user for audit trail
                if user:
                    account.save(user=user)
                else:
                    account.save()
                
                # Record history if available
                if hasattr(account, 'historical_data') and isinstance(account.historical_data, dict):
                    if field_name not in account.historical_data:
                        account.historical_data[field_name] = []
                    
                    account.historical_data[field_name].append({
                        'old_value': current_value,
                        'new_value': value,
                        'changed_at': timezone.now().isoformat(),
                        'changed_by': str(user.id) if user else None,
                        'source': 'signal',
                        'signal_id': str(signal.id)
                    })
                    
                    # Save historical data
                    account.save(update_fields=['historical_data'])
                
                return True
                
        return False
    
    @classmethod
    def _apply_to_org_unit(cls, signal, user):
        """Apply signal to organization unit"""
        org_unit = signal.org_unit
        if not org_unit:
            return False
            
        field_name = signal.field_name
        value = signal.value
        
        # Qualification fields vs. regular fields
        if field_name in ['objectives', 'compelling_events', 'motivations', 
                        'key_kpis', 'criteria', 'pain_points', 'implications',
                        'current_tech_stack', 'partners', 'buying_process', 
                        'projects', 'budget', 'new_budget_start_date']:
            # Use QualificationModel's update method to track history
            if hasattr(org_unit, 'update_qualification_field'):
                org_unit.update_qualification_field(field_name, value, user)
                return True
        else:
            # Regular field update
            if hasattr(org_unit, field_name):
                # Simple fields
                current_value = getattr(org_unit, field_name)
                setattr(org_unit, field_name, value)
                
                # Save with the user for audit trail
                if user:
                    org_unit.save(user=user)
                else:
                    org_unit.save()
                
                # Record history if available
                if hasattr(org_unit, 'historical_data') and isinstance(org_unit.historical_data, dict):
                    if field_name not in org_unit.historical_data:
                        org_unit.historical_data[field_name] = []
                    
                    org_unit.historical_data[field_name].append({
                        'old_value': current_value,
                        'new_value': value,
                        'changed_at': timezone.now().isoformat(),
                        'changed_by': str(user.id) if user else None,
                        'source': 'signal',
                        'signal_id': str(signal.id)
                    })
                    
                    # Save historical data
                    org_unit.save(update_fields=['historical_data'])
                
                return True
                
        return False
    
    @classmethod
    def _apply_to_contact(cls, signal, user):
        """Apply signal to contact"""
        contact = signal.contact
        if not contact:
            return False
            
        field_name = signal.field_name
        value = signal.value
        
        # Qualification fields vs. regular fields
        if field_name in ['objectives', 'compelling_events', 'motivations', 
                       'key_kpis', 'criteria', 'pain_points', 'implications',
                       'current_tech_stack', 'partners', 'buying_process', 
                       'projects', 'budget', 'new_budget_start_date']:
            # Use QualificationModel's update method to track history
            if hasattr(contact, 'update_qualification_field'):
                contact.update_qualification_field(field_name, value, user)
                return True
        else:
            # Regular field update
            if hasattr(contact, field_name):
                # Simple fields
                current_value = getattr(contact, field_name)
                setattr(contact, field_name, value)
                
                # Save with the user for audit trail
                if user:
                    contact.save(user=user)
                else:
                    contact.save()
                
                # Record history if available
                if hasattr(contact, 'historical_data') and isinstance(contact.historical_data, dict):
                    if field_name not in contact.historical_data:
                        contact.historical_data[field_name] = []
                    
                    contact.historical_data[field_name].append({
                        'old_value': current_value,
                        'new_value': value,
                        'changed_at': timezone.now().isoformat(),
                        'changed_by': str(user.id) if user else None,
                        'source': 'signal',
                        'signal_id': str(signal.id)
                    })
                    
                    # Save historical data
                    contact.save(update_fields=['historical_data'])
                
                return True
                
        return False
    
    @classmethod
    def _apply_to_account_product(cls, signal, user):
        """Apply signal to account product detail"""
        apd = signal.account_product_detail
        if not apd:
            return False
            
        field_name = signal.field_name
        value = signal.value
        
        # Handle special fields specific to AccountProductDetail
        if field_name == 'ai_relevance_score' and isinstance(value, (int, float)):
            apd.ai_relevance_score = value
            
            # Save with the user for audit trail
            if user:
                apd.save(user=user)
            else:
                apd.save()
            return True
            
        elif field_name == 'notes':
            # Append to existing notes if present
            existing_notes = apd.notes or ""
            new_notes = f"{existing_notes}\n\n{value}" if existing_notes else value
            apd.notes = new_notes
            
            # Save with the user for audit trail
            if user:
                apd.save(user=user)
            else:
                apd.save()
            return True
            
        elif field_name == 'estimated_units' and isinstance(value, (int, str)):
            # Convert to int if needed
            units = int(value) if isinstance(value, str) else value
            apd.estimated_units = units
            
            # Save with the user for audit trail
            if user:
                apd.save(user=user)
            else:
                apd.save()
            return True
            
        elif hasattr(apd, field_name):
            # Regular field update
            current_value = getattr(apd, field_name)
            setattr(apd, field_name, value)
            
            # Save with the user for audit trail
            if user:
                apd.save(user=user)
            else:
                apd.save()
            return True
                
        return False
        
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