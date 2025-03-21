from django.db import models
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class SignalAwareMixin(models.Model):
    """Mixin that provides signal awareness capabilities to models."""
    signal_metadata = models.JSONField(blank=True, null=True, verbose_name='Signal Metadata')
    
    class Meta:
        abstract = True
    
    def get_related_signals(self, field_name=None, category=None, include_expired=False):
        """Get all signals that contributed to a field value."""
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
        active_signals = query.filter(status__in=['APPROVED', 'APPLIED'])
        
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
            
            potentially_expired = query.filter(status__in=['APPROVED', 'APPLIED'])
            
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
        """Get all signal metadata for a specific field."""
        if not self.signal_metadata or field_name not in self.signal_metadata:
            return {}
            
        return self.signal_metadata[field_name]
    
    def track_signal_update(self, signal, field_name, old_value, new_value):
        """Track a signal update in the model's signal metadata."""
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


class SignalEnabledQualificationMixin(models.Model):
    """Mixin that extends QualificationModel with signal-aware methods."""
    
    class Meta:
        abstract = True
        
    def update_qualification_field(self, field_name, new_value, user, signal=None):
        """Enhanced update method for qualification fields that tracks signal information."""
        # Get current value
        current_value = getattr(self, field_name)
        
        # Update the field
        setattr(self, field_name, new_value)
        
        # Initialize historical_data if it doesn't exist
        if not self.historical_data:
            self.historical_data = {}
        
        # Initialize field history if it doesn't exist
        if field_name not in self.historical_data:
            self.historical_data[field_name] = []
        
        # Create history entry
        history_entry = {
            'old_value': current_value,
            'new_value': new_value,
            'changed_at': timezone.now().isoformat(),
            'changed_by': str(user.id) if user else None,
        }
        
        # Add signal data if provided
        if signal:
            history_entry.update({
                'source': 'signal',
                'signal_id': str(signal.id),
                'signal_category': signal.category,
                'signal_confidence': signal.confidence,
                'confirmation_count': signal.confirmation_count
            })
            
            # Also track in signal_metadata
            self.track_signal_update(signal, field_name, current_value, new_value)
        
        # Add to historical data
        self.historical_data[field_name].append(history_entry)
        
        # Save the model
        self.save(user=user)
        
        return True
    
    def get_qualification_data(self, include_signal_info=False):
        """Get all qualification data with optional signal information."""
        qualification_fields = [
            'objectives', 'compelling_events', 'motivations', 'key_kpis',
            'criteria', 'pain_points', 'implications', 
        ]
        
        return self._get_field_data_with_signals(qualification_fields, include_signal_info)
    
    def get_profile_data(self, include_signal_info=False, profile_fields=None):
        """Get profile data with optional signal information."""
        if profile_fields is None:
            # Default profile fields - override in subclasses if needed
            profile_fields = []
            
        return self._get_field_data_with_signals(profile_fields, include_signal_info, 'PROFILE')
    
    def _get_field_data_with_signals(self, fields, include_signal_info=False, category=None):
        """Shared method to get field data with optional signal information."""
        result = {}
        
        for field in fields:
            if hasattr(self, field):
                value = getattr(self, field)
                result[field] = value
                
                if include_signal_info and value is not None:
                    # Add signal information if available
                    signals = self.get_related_signals(
                        field_name=field,
                        category=category,
                        include_expired=True
                    )
                    
                    # Only include if we have signals
                    if any(s.exists() for s in signals.values()):
                        signal_info = {}
                        
                        for status, queryset in signals.items():
                            if queryset.exists():
                                signal_info[status] = [{
                                    'id': s.id,
                                    'category': s.category,
                                    'source': s.source,
                                    'created_at': s.created_at,
                                    'confirmation_count': s.confirmation_count,
                                    'confidence': getattr(s, 'confidence', None),
                                    'potential_value': getattr(s, 'potential_value', None)
                                } for s in queryset]
                                
                        result[f"{field}_signals"] = signal_info
                        
                    # Add signal metadata from the model
                    metadata = self.get_field_signal_metadata(field)
                    if metadata:
                        result[f"{field}_metadata"] = metadata
                    
        return result