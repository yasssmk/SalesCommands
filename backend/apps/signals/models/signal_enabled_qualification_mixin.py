# apps/signals/models/signal_enabled_qualification_mixin.py

from django.db import models
from django.utils import timezone

class SignalEnabledQualificationMixin(models.Model):
    """
    Mixin that provides methods for working with qualification signals.
    Uses SignalCreationService to create signals.
    """
    
    class Meta:
        abstract = True
    
    def create_qualification_signal(self, field_name, value, user=None, source="manual", 
                                   department=None, contact=None):
        """
        Create a qualification signal for this entity.
        
        Args:
            field_name: Field name for the signal
            value: Value for the signal
            user: User creating the signal
            source: Source of the signal
            department: Optional department for the signal
            contact: Optional contact for the signal
            
        Returns:
            Signal: Created signal
        """
        from apps.signals.services.signal_creation_service import SignalCreationService
        
        # Use the service to create the signal
        return SignalCreationService.create_signal_for_field(
            instance=self,
            field_name=field_name,
            value=value,
            user=user,
            source=source,
            department=department,
            contact=contact
        )
    
    def get_qualification_data(self, include_signal_info=False, department=None, 
                             min_confirmations=None, field_names=None):
        """
        Get qualification data from signals.
        
        Args:
            include_signal_info: Whether to include signal metadata
            department: Optional department to filter by
            min_confirmations: Minimum number of confirmations required
            field_names: Optional list of specific fields to retrieve
            
        Returns:
            dict: Qualification data from signals
        """
        from apps.signals.services.signal_data_service import SignalDataService
        
        # Get account from the entity
        account = self if hasattr(self, 'company_name') else self.account
        
        # Use signal data service to get qualification data
        return SignalDataService.get_account_qualification_data(
            account=account,
            field_names=field_names,
            department=department,
            min_confirmations=min_confirmations,
            include_signal_info=include_signal_info
        )
    
    def get_qualification_by_department(self):
        """
        Get qualification data organized by department.
        
        Returns:
            dict: Qualification data by department
        """
        from apps.signals.services.signal_data_service import SignalDataService
        
        # Get account from the entity
        account = self if hasattr(self, 'company_name') else self.account
        
        # Use signal data service to get data by department
        return SignalDataService.get_profile_by_department(account)