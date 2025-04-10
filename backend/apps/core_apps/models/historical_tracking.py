# apps/core_apps/models/historical_tracking.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class HistoricalTrackingModel(models.Model):
    """
    Model mixin that provides historical data tracking functionality.
    Enhanced to work with signal-based qualification data.
    """
    historical_data = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_('Historical Data')
    )
    
    class Meta:
        abstract = True
    
    def track_field_change(self, field_name, old_value, new_value, user=None, signal=None, reason=None):
        """
        Track changes to any field in historical data
        
        Args:
            field_name (str): Field name that changed
            old_value: Previous value
            new_value: New value
            user (User, optional): User who made the change
            signal (Signal, optional): Signal that triggered the change
            reason (str, optional): Reason for the change (deprecated)
        """
        if self.historical_data is None:
            self.historical_data = {}
            
        # Initialize field entry if it doesn't exist
        if field_name not in self.historical_data:
            self.historical_data[field_name] = {
                'changes': []
            }
        elif not isinstance(self.historical_data.get(field_name), dict):
            # Handle case where it's not a dict (legacy format)
            old_value_stored = self.historical_data.get(field_name)
            self.historical_data[field_name] = {
                'changes': [old_value_stored] if old_value_stored else []
            }
        elif 'changes' not in self.historical_data[field_name]:
            # Handle case where 'changes' key is missing
            self.historical_data[field_name]['changes'] = []
            
        # Create change entry
        now = timezone.now().isoformat()
        change_entry = {
            'old_value': old_value,
            'new_value': new_value,
            'changed_at': now,
            'changed_by': str(user.id) if user else None,
            'source': 'signal' if signal else 'manual'
        }
        
        # Add signal information if present
        if signal:
            change_entry['signal_id'] = str(signal.id)
            change_entry['signal_category'] = getattr(signal, 'category', None)
            change_entry['signal_status'] = getattr(signal, 'status', None)
            change_entry['signal_source'] = getattr(signal, 'source', None)
            change_entry['source_contact_id'] = str(signal.source_contact.id) if getattr(signal, 'source_contact', None) else None
            change_entry['source_department_id'] = str(signal.source_department.id) if getattr(signal, 'source_department', None) else None
            change_entry['confirmation_count'] = getattr(signal, 'confirmation_count', None)
        
        # Add to changes list
        self.historical_data[field_name]['changes'].append(change_entry)
        
        # Save the instance
        self.save(update_fields=['historical_data'])
        
        return True
            
    def update_tracked_field(self, field_name, new_value, user=None):
        """
        Update a field and track the change
        
        Args:
            field_name (str): Field name to update
            new_value: New value for the field
            user (User, optional): User making the change
            
        Returns:
            bool: Whether the update was successful
        """
        from apps.core_apps.services.historical_tracking_service import HistoricalTrackingService
        
        return HistoricalTrackingService.update_field(
            instance=self,
            field_name=field_name,
            new_value=new_value,
            user=user
        )
    
    def create_field_signal(self, field_name, value, category, user=None, source=None, 
                           department=None, contact=None):
        """
        Create a signal for a field and track it in historical data.
        
        Args:
            field_name: Field name for the signal
            value: Value for the signal
            category: Signal category
            user: User creating the signal
            source: Source of the signal
            department: Optional department for the signal
            contact: Optional contact for the signal
            
        Returns:
            Signal: Created signal
        """
        from apps.signals.models import Signal
        
        # Determine entity type
        entity_type = Signal.EntityType.ACCOUNT
        
        # Get account from the entity
        account = self if hasattr(self, 'company_name') else self.account
        
        # Create metadata based on entity type
        metadata = {}
        if hasattr(self, 'tech_name'):  # It's a TechStack
            metadata['tech_stack_id'] = str(self.id)
            metadata['tech_name'] = self.tech_name
        
        # Create the signal
        signal = Signal.objects.create(
            account=account,
            entity_type=entity_type,
            category=category,
            field_name=field_name,
            value=value,
            status=Signal.Status.PENDING,
            source=source or 'manual',
            source_contact=contact,
            source_department=department,
            client_id=account.client_id,
            created_by=user,
            updated_by=user,
            metadata=metadata
        )
        
        # Track in historical data
        self.track_field_change(
            field_name=field_name,
            old_value=None,
            new_value=value,
            user=user,
            signal=signal
        )
        
        return signal