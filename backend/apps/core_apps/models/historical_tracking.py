# apps/core_apps/models/historical_tracking.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class HistoricalTrackingModel(models.Model):
    """
    Model mixin that provides historical data tracking functionality.
    """
    historical_data = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_('Historical Data')
    )
    
    class Meta:
        abstract = True
    
    def track_field_change(self, field_name, old_value, new_value, user=None):
        """
        Track changes to any field in historical data
        
        Args:
            field_name (str): Field name that changed
            old_value: Previous value
            new_value: New value
            user (User, optional): User who made the change
        """
        # Initialize historical_data if it doesn't exist
        if not self.historical_data:
            self.historical_data = {}
        
        # Initialize field history if it doesn't exist
        if field_name not in self.historical_data:
            self.historical_data[field_name] = []
        
        # Create history entry
        history_entry = {
            'old_value': old_value,
            'new_value': new_value,
            'changed_at': timezone.now().isoformat(),
            'changed_by': str(user.id) if user else None,
            'source': 'manual'
        }
        
        # Add to historical data
        self.historical_data[field_name].append(history_entry)
        
        return True
    
    def track_signal_update(self, signal, field_name, old_value, new_value):
        """
        Track updates driven by signals
        
        Args:
            signal: Signal instance
            field_name: Field being updated
            old_value: Previous value
            new_value: New value
        """
        # Initialize historical_data if it doesn't exist
        if not self.historical_data:
            self.historical_data = {}
        
        # Initialize field history if it doesn't exist
        if field_name not in self.historical_data:
            self.historical_data[field_name] = []
        
        # Create history entry with signal data
        history_entry = {
            'old_value': old_value,
            'new_value': new_value,
            'changed_at': timezone.now().isoformat(),
            'changed_by': str(signal.created_by_id) if signal.created_by_id else None,
            'source': 'signal',
            'signal_id': str(signal.id),
            'signal_category': signal.category,
            'signal_confidence': getattr(signal, 'confidence', None)
        }
        
        # Add to historical data
        self.historical_data[field_name].append(history_entry)
        
        return True