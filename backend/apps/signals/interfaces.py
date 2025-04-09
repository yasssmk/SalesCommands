# apps/signals/interfaces.py

from abc import ABC, abstractmethod

class SignalQualifiedEntity(ABC):
    """
    Interface for entities that can be qualified with signals.
    Provides a common API for retrieving qualification data from signals.
    """
    
    @abstractmethod
    def get_qualification_signals(self, field_name=None, department=None, 
                                min_confirmations=None, include_expired=False):
        """
        Get qualification signals for this entity.
        
        Args:
            field_name: Optional field name to filter by
            department: Optional department to filter by
            min_confirmations: Minimum number of confirmations required
            include_expired: Whether to include expired signals
            
        Returns:
            QuerySet: Filtered signals
        """
        pass
    
    @abstractmethod
    def get_qualification_data(self, include_signal_info=False, department=None, 
                             min_confirmations=None, field_names=None):
        """
        Get qualification data for this entity.
        
        Args:
            include_signal_info: Whether to include signal metadata
            department: Optional department to filter by
            min_confirmations: Minimum number of confirmations required
            field_names: Optional list of specific fields to retrieve
            
        Returns:
            dict: Qualification data
        """
        pass
    
    @abstractmethod
    def get_qualification_by_department(self):
        """
        Get qualification data organized by department.
        
        Returns:
            dict: Qualification data by department
        """
        pass