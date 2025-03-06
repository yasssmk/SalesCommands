# apps/core_apps/models/signal_aware_mixin.py

from django.db import models
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class SignalAwareMixin(models.Model):
    """
    Mixin that provides signal awareness capabilities to models.
    Used to track signal history and provide a consistent interface
    for signal-related operations across Account, OrgUnit, Contact, and APD models.
    """
    # Field to store signal-specific metadata
    signal_metadata = models.JSONField(
        blank=True, 
        null=True, 
        verbose_name='Signal Metadata'
    )
    
    class Meta:
        abstract = True
    
    def get_related_signals(self, field_name=None, category=None, include_expired=False):
        """
        Get all signals that contributed to a field value.
        
        Args:
            field_name (str, optional): Specific field to get signals for
                                        If None, returns all signals
            category (str, optional): Filter by signal category
            include_expired (bool): Whether to include signals with effective status 'EXPIRED'
        
        Returns:
            dict: Dictionary with active, merged, and expired signals for the field
        """
        from apps.sales_insight.models import Signal
        from django.db.models import Q
        
        # Base query for signals related to this entity
        query = Signal.objects.filter(
            account_id=self.account_id if hasattr(self, 'account_id') else self.id
        )
        
        # Add entity-specific filters
        entity_map = {
            'account': (Signal.EntityType.ACCOUNT, None),
            'accountorganizationunit': (Signal.EntityType.ORG_UNIT, 'org_unit_id'),
            'contact': (Signal.EntityType.CONTACT, 'contact_id'),
            'accountproductdetail': (Signal.EntityType.ACCOUNT_PRODUCT, 'account_product_detail_id')
        }
        
        model_name = self._meta.model_name
        if model_name in entity_map:
            entity_type, field_id = entity_map[model_name]
            query = query.filter(entity_type=entity_type)
            if field_id and hasattr(self, 'id'):
                query = query.filter(**{field_id: self.id})
        
        # Add field filter if provided
        if field_name:
            query = query.filter(field_name=field_name)
            
        # Add category filter if provided
        if category:
            query = query.filter(category=category)
        
        # Get active signals (approved or applied)
        active_signals = query.filter(
            status__in=['APPROVED', 'APPLIED']
        )
        
        # Get merged signals
        merged_signals = query.filter(
            status='MERGED',
            merged_into__in=active_signals
        )
        
        result = {
            'active': active_signals,
            'merged': merged_signals
        }
        
        # Add expired signals if requested
        if include_expired:
            from apps.sales_insight.services.signal_lifecycle_service import SignalLifecycleService
            
            # We need to manually check for expired signals
            potentially_expired = query.filter(
                status__in=['APPROVED', 'APPLIED']
            )
            
            expired_ids = []
            for signal in potentially_expired:
                if SignalLifecycleService.get_effective_status(signal) == "EXPIRED":
                    expired_ids.append(signal.id)
                    
            if expired_ids:
                result['expired'] = query.filter(id__in=expired_ids)
            else:
                result['expired'] = Signal.objects.none()
                
        return result
    
    def get_field_signal_metadata(self, field_name):
        """
        Get all signal metadata for a specific field.
        
        Args:
            field_name (str): Field name to get metadata for
            
        Returns:
            dict: Signal metadata for the field
        """
        if not self.signal_metadata or field_name not in self.signal_metadata:
            return {}
            
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
        # Initialize signal_metadata if needed
        if not self.signal_metadata:
            self.signal_metadata = {}
            
        # Initialize field history if needed
        if field_name not in self.signal_metadata:
            self.signal_metadata[field_name] = {
                'updates': [],
                'last_signal_id': None,
                'confirmation_count': 0,
                'last_confirmed_at': None
            }
            
        # Add signal update to history
        update_entry = {
            'signal_id': str(signal.id),
            'signal_category': signal.category,
            'signal_source': signal.source,
            'old_value': old_value,
            'new_value': new_value,
            'updated_at': timezone.now().isoformat(),
            'applied_by': str(signal.approved_by.id) if signal.approved_by else None
        }
        
        self.signal_metadata[field_name]['updates'].append(update_entry)
        self.signal_metadata[field_name]['last_signal_id'] = str(signal.id)
        self.signal_metadata[field_name]['confirmation_count'] = signal.confirmation_count
        self.signal_metadata[field_name]['last_confirmed_at'] = timezone.now().isoformat()
        
        self.save(update_fields=['signal_metadata'])