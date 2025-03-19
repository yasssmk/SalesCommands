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
                
                if hasattr(account, 'track_signal_update'):
                    account.track_signal_update(signal, field_name, current_value, value)

                # Initialize historical data tracking
                if not account.historical_data:
                    account.historical_data = {}

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

                # Save historical changes
                account.save(update_fields=[field_name,'historical_data'])
                return True
                
        return False
    
    @classmethod
    def _apply_to_org_unit(cls, signal, user):
        """Apply signal to organization unit, tracking both qualification and specific field changes."""
        org_unit_id = signal.org_unit_id
        if not org_unit_id:
            return False
            
        org_unit = AccountOrganizationUnit.objects.get(id=org_unit_id)
        field_name = signal.field_name
        value = signal.value

        if field_name in [
            'objectives', 'compelling_events', 'motivations', 'key_kpis',
            'criteria', 'pain_points', 'implications', 'current_tech_stack',
            'partners', 'buying_process', 'projects', 'budget', 'new_budget_start_date'
        ]:
            # ✅ Qualification fields: use `update_qualification_field()`
            if hasattr(org_unit, 'update_qualification_field'):
                org_unit.update_qualification_field(field_name, value, user)
                return True

        elif field_name in ['unit_type', 'organization_name', 'estimated_employee_count']:  # Add any org-unit-specific fields that need tracking
            # 🔥 Custom tracking for org-unit-specific fields
            current_value = getattr(org_unit, field_name, None)
        
            # For estimated_employee_count, ensure it's an integer
            if field_name == 'estimated_employee_count' and value is not None:
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    # If conversion fails, use the original value
                    pass
                    
            setattr(org_unit, field_name, value)

            if hasattr(org_unit, 'track_signal_update'):
                org_unit.track_signal_update(signal, field_name, current_value, value)

            if not org_unit.historical_data:
                org_unit.historical_data = {}

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

            update_fields = [field_name]
            if org_unit.historical_data:
                update_fields.append('historical_data')

            org_unit.save(update_fields=['historical_data'])
            return True

        return False

    @classmethod
    def _apply_to_contact(cls, signal, user):
        """Apply signal to contact, tracking both qualification and specific field changes."""
        contact_id = signal.contact_id
        if not contact_id:
            return False
            
        # Get a fresh contact instance for each signal application
        contact = Contact.objects.get(id=contact_id)
        field_name = signal.field_name
        value = signal.value

        if field_name in [
            'objectives', 'compelling_events', 'motivations', 'key_kpis',
            'criteria', 'pain_points', 'implications', 'current_tech_stack',
            'partners', 'buying_process', 'projects', 'budget', 'new_budget_start_date'
        ]:
            # ✅ Qualification fields: use `update_qualification_field()`
            if hasattr(contact, 'update_qualification_field'):
                contact.update_qualification_field(field_name, value, user)
                return True

        elif field_name in ['job_title', 'influence_level', 'first_name', 'last_name']:  # Add any contact-specific fields that need tracking
            # 🔥 Custom tracking for contact-specific fields
            current_value = getattr(contact, field_name, None)
            setattr(contact, field_name, value)

            if hasattr(contact, 'track_signal_update'):
                contact.track_signal_update(signal, field_name, current_value, value)

            if not contact.historical_data:
                contact.historical_data = {}

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

            contact.save(update_fields=['historical_data'])
            return True

        return False

    # @classmethod
    # def _apply_to_account_product(cls, signal, user):
    #     """Apply signal to account product detail, tracking relevant field changes."""
    #     apd = signal.account_product_detail
    #     if not apd:
    #         return False
            
    #     field_name = signal.field_name
    #     value = signal.value

    #     if field_name == 'ai_relevance_score' and isinstance(value, (int, float)):
    #         apd.ai_relevance_score = value
    #         apd.save(user=user)
    #         return True

    #     elif field_name == 'notes':
    #         existing_notes = apd.notes or ""
    #         new_notes = f"{existing_notes}\n\n{value}" if existing_notes else value
    #         apd.notes = new_notes
    #         apd.save(user=user)
    #         return True

    #     elif field_name == 'estimated_units' and isinstance(value, (int, str)):
    #         apd.estimated_units = int(value) if isinstance(value, str) else value
    #         apd.save(user=user)
    #         return True

    #     elif hasattr(apd, field_name):
    #         # 🔥 Custom tracking for account product-specific fields
    #         current_value = getattr(apd, field_name)
    #         setattr(apd, field_name, value)

    #         apd.save(user=user)

    #         if not apd.historical_data:
    #             apd.historical_data = {}

    #         if field_name not in apd.historical_data:
    #             apd.historical_data[field_name] = []

    #         apd.historical_data[field_name].append({
    #             'old_value': current_value,
    #             'new_value': value,
    #             'changed_at': timezone.now().isoformat(),
    #             'changed_by': str(user.id) if user else None,
    #             'source': 'signal',
    #             'signal_id': str(signal.id)
    #         })

    #         apd.save(update_fields=['historical_data'])
    #         return True

    #     return False
    
    
        
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