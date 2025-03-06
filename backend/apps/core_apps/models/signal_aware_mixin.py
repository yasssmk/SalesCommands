from django.db import models
import logging

logger = logging.getLogger(__name__)

class SignalAwareMixin(models.Model):
    """
    Mixin that provides signal awareness capabilities to models.
    Used to track signal history and provide a consistent interface
    for signal-related operations across Account, OrgUnit, Contact, and APD models.
    """
    # Field to store signal metadata and history
    signal_metadata = models.JSONField(
        blank=True, 
        null=True, 
        verbose_name='Signal Metadata'
    )
    
    class Meta:
        abstract = True
    
    def get_related_signals(self, field_name=None):
        """
        Get all signals that contributed to a field value.
        
        Args:
            field_name (str, optional): Specific field to get signals for
                                        If None, returns all signals
        
        Returns:
            dict: Dictionary with active and merged signals for the field
        """
        from apps.sales_insight.models import Signal
        from django.db.models import Q
        
        # Base query for signals related to this entity
        query = Signal.objects.filter(
            account_id=self.account_id if hasattr(self, 'account_id') else self.id
        )
        
        # Add entity-specific filters
        if hasattr(self, '_meta') and self._meta.model_name == 'account':
            query = query.filter(entity_type=Signal.EntityType.ACCOUNT)
        elif hasattr(self, '_meta') and self._meta.model_name == 'accountorganizationunit':
            query = query.filter(entity_type=Signal.EntityType.ORG_UNIT, org_unit_id=self.id)
        elif hasattr(self, '_meta') and self._meta.model_name == 'contact':
            query = query.filter(entity_type=Signal.EntityType.CONTACT, contact_id=self.id)
        elif hasattr(self, '_meta') and self._meta.model_name == 'accountproductdetail':
            query = query.filter(entity_type=Signal.EntityType.ACCOUNT_PRODUCT, account_product_detail_id=self.id)
        
        # Add field filter if provided
        if field_name:
            query = query.filter(field_name=field_name)
        
        # Get active signals (approved or applied)
        active_signals = query.filter(
            status__in=['APPROVED', 'APPLIED']
        )
        
        # Get merged signals
        merged_signals = query.filter(
            status='MERGED',
            merged_into__in=active_signals
        )
        
        return {
            'active': active_signals,
            'merged': merged_signals
        }
    
    def get_field_signal_history(self, field_name):
        """
        Get the signal history for a specific field.
        
        Args:
            field_name (str): Field name to get history for
            
        Returns:
            list: List of signal history entries for the field
        """
        if not self.signal_metadata or field_name not in self.signal_metadata:
            return []
            
        return self.signal_metadata[field_name]
    
    def track_signal_update(self, signal, field_name, old_value, new_value):
        """
        Track a signal update in the model's signal metadata.
        
        Args:
            signal (Signal): Signal that triggered the update
            field_name (str): Field name that was updated
            old_value: Previous value
            new_value: New value
        """
        from django.utils import timezone
        
        # Initialize signal_metadata if needed
        if not self.signal_metadata:
            self.signal_metadata = {}
            
        # Initialize field history if needed
        if field_name not in self.signal_metadata:
            self.signal_metadata[field_name] = []
            
        # Add signal update to history
        self.signal_metadata[field_name].append({
            'signal_id': str(signal.id),
            'signal_category': signal.category,
            'signal_source': signal.source,
            'old_value': old_value,
            'new_value': new_value,
            'updated_at': timezone.now().isoformat(),
            'confirmation_count': signal.confirmation_count
        })
        
        self.save(update_fields=['signal_metadata'])