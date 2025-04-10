from django.db import models
from django.utils import timezone
from apps.core_apps.services.historical_tracking_service import HistoricalTrackingService

class SignalAwareMixin(models.Model):
    """Mixin that provides signal awareness capabilities to models."""
    signal_metadata = models.JSONField(blank=True, null=True, verbose_name='Signal Metadata')
    
    class Meta:
        abstract = True
    
    def get_related_signals(self, field_name=None, category=None, department=None, 
                           source_contact=None, include_expired=False):
        """
        Get all signals that contributed to a field value.
        
        Args:
            field_name: Optional field name to filter by
            category: Optional category to filter by
            department: Optional department to filter by
            source_contact: Optional source contact to filter by
            include_expired: Whether to include expired signals
            
        Returns:
            dict: Dictionary of signal querysets by status
        """
        from apps.signals.models import Signal
        from django.db.models import Q
        
        # Base query for signals related to this entity
        query = Signal.objects.filter(account_id=self.account_id if hasattr(self, 'account_id') else self.id)
        
        # Add entity-specific filters
        entity_map = {
            'account': (Signal.EntityType.ACCOUNT, None),
            'techstack': (Signal.EntityType.ACCOUNT, 'tech_stack_id')
        }
        
        model_name = self._meta.model_name
        if model_name in entity_map:
            entity_type, metadata_field = entity_map[model_name]
            query = query.filter(entity_type=entity_type)
            
            # Add metadata filter for TechStack
            if metadata_field and hasattr(self, 'id'):
                query = query.filter(metadata__contains={metadata_field: str(self.id)})
        
        # Add field filter if provided
        if field_name:
            query = query.filter(field_name=field_name)
            
        # Add category filter if provided
        if category:
            query = query.filter(category=category)
            
        # Add department filter if provided
        if department:
            query = query.filter(source_department=department)
            
        # Add source contact filter if provided
        if source_contact:
            query = query.filter(source_contact=source_contact)
        
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
            from apps.signals.services.signal_lifecycle_service import SignalLifecycleService
            
            # Calculate expiration cutoffs
            profile_expiry = timezone.now() - timezone.timedelta(days=SignalLifecycleService.TIME_TO_EXPIRED_PROFILE)
            process_expiry = timezone.now() - timezone.timedelta(days=SignalLifecycleService.TIME_TO_EXPIRED_PROCESS)
            
            # Find expired signals
            expired_signals = active_signals.filter(
                Q(category__in=['PROFILE', 'QUALIFICATION'], last_confirmed_at__lte=profile_expiry) |
                Q(category='PROCESS', last_confirmed_at__lte=process_expiry)
            )
            
            if expired_signals.exists():
                result['expired'] = expired_signals
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
            
        # Initialize field entry if needed
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
            'applied_by': str(signal.approved_by.id) if signal.approved_by else None,
            'source_contact_id': str(signal.source_contact.id) if signal.source_contact else None,
            'source_department_id': str(signal.source_department.id) if signal.source_department else None
        }
        
        self.signal_metadata[field_name]['updates'].append(update_entry)
        self.signal_metadata[field_name]['last_signal_id'] = str(signal.id)
        self.signal_metadata[field_name]['confirmation_count'] = signal.confirmation_count
        self.signal_metadata[field_name]['last_confirmed_at'] = timezone.now().isoformat()
        
        self.save(update_fields=['signal_metadata'])
