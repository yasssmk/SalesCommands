# apps/accounts_app/accounts/models.py (or in a new file tech_stack.py if you prefer)

from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core_apps.models import BaseModelApp
from core.client_scope import ClientScopeManager
from .accounts import Account
from apps.core_apps.models import AccountLinkedModel, HistoricalTrackingModel
from apps.signals.services import SignalDataService

class TechStack(BaseModelApp, AccountLinkedModel, ClientScopeManager.ModelMixin, HistoricalTrackingModel):
    """
    Model to track technologies used by an account.
    """
    tech_name = models.CharField(
        max_length=255,
        verbose_name=_('Technology Name')
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes')
    )
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints()):
        verbose_name = _('Tech Stack')
        verbose_name_plural = _('Tech Stacks')
        ordering = ['tech_name']
    
    def __str__(self):
        return f"{self.tech_name} ({self.account.company_name})"
    
    def get_qualification_signals(self, field_name=None, department=None, 
                                min_confirmations=None, include_expired=False):
        """Get tech evaluation signals for this tech stack."""
        from apps.signals.models import Signal
        
        # Base query for tech stack signals
        return SignalDataService.get_field_signals(
            account=self.account,
            field_name=field_name,
            entity_type=Signal.EntityType.ACCOUNT,
            department=department,
            min_confirmations=min_confirmations,
            include_expired=include_expired,
            status=[Signal.Status.APPROVED, Signal.Status.APPLIED]
        )
    
    def get_qualification_data(self, include_signal_info=False, department=None, 
                             min_confirmations=None, field_names=None):
        """Get tech evaluation data from signals."""
        return SignalDataService.get_tech_stack_data(
            account=self.account,
            tech_stack=self,
            field_names=field_names,
            department=department,
            min_confirmations=min_confirmations,
            include_signal_info=include_signal_info
        )
    
    def get_qualification_by_department(self):
        """Get tech evaluation data organized by department."""
        return SignalDataService.get_tech_stack_by_department(self.account)
    
    def get_tech_evaluation_by_source(self, department=None, contact=None):
        """
        Get tech evaluation data organized by source.
        
        Args:
            department: Optional department to filter by
            contact: Optional contact to filter by
            
        Returns:
            dict: Tech evaluation data by source
        """
        from apps.signals.models import Signal
        from django.db.models import Count
        
        # Get all tech stack signals for this tech stack
        signals = Signal.objects.filter(
            account=self.account,
            category=Signal.Category.TECH_STACK,
            entity_type=Signal.EntityType.ACCOUNT,
            status__in=[Signal.Status.APPROVED, Signal.Status.APPLIED],
            metadata__contains={'tech_stack_id': str(self.id)}
        )
        
        if department:
            signals = signals.filter(source_department=department)
        
        if contact:
            signals = signals.filter(source_contact=contact)
        
        # Group by source
        results = {}
        sources = signals.values('source').annotate(count=Count('id')).order_by('-count')
        
        for source_info in sources:
            source = source_info['source'] or 'unknown'
            source_signals = signals.filter(source=source)
            
            # Group by field
            source_data = {}
            for signal in source_signals:
                field_name = signal.field_name
                if field_name not in source_data:
                    source_data[field_name] = []
                
                # Add value to field data
                if isinstance(signal.value, list):
                    source_data[field_name].extend(signal.value)
                else:
                    source_data[field_name].append(signal.value)
            
            results[source] = source_data
        
        return results