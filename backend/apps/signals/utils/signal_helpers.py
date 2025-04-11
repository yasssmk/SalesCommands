# apps/signals/utils/signal_helpers.py

from django.db.models import Q
from ..models.qualification_signal_model import QualificationSignal
from ..models.tech_stack_signal_model import TechStackSignal
from ..models.profile_signal_model import ProfileSignal
from core.exceptions import StandardizedValidationError


class SignalHelpers:
    """
    Helper utilities for common signal operations across views and services.
    """
    
    @staticmethod
    def get_signal_by_id(signal_id, client_id=None):
        """
        Find a signal by ID, checking all signal types.
        
        Args:
            signal_id: ID of the signal to find
            client_id: Optional client ID for filtering
            
        Returns:
            Signal instance or None if not found
        """
        # Try each signal type
        signal_models = [QualificationSignal, TechStackSignal, ProfileSignal]
        
        for model in signal_models:
            query = model.objects.filter(id=signal_id)
            if client_id:
                query = query.filter(client_id=client_id)
                
            signal = query.first()
            if signal:
                return signal
        
        return None
    
    @staticmethod
    def get_account_signals_by_type(account_id, client_id=None):
        """
        Get all signals for an account, organized by type.
        
        Args:
            account_id: Account ID to filter by
            client_id: Optional client ID for filtering
            
        Returns:
            Dictionary with signals organized by type
        """
        # Base filter
        account_filter = Q(account_id=account_id, status='APPROVED')
        if client_id:
            account_filter &= Q(client_id=client_id)
            
        # Get signals by type
        qualification_signals = QualificationSignal.objects.filter(account_filter)
        tech_stack_signals = TechStackSignal.objects.filter(account_filter)
        profile_signals = ProfileSignal.objects.filter(account_filter)
        
        return {
            'qualification': qualification_signals,
            'tech_stack': tech_stack_signals,
            'profile': profile_signals
        }
    
    @staticmethod
    def validate_field_name(field_name, signal_type):
        """
        Validate a field name for a specific signal type.
        
        Args:
            field_name: Field name to validate
            signal_type: Signal type class (QualificationSignal, etc.)
            
        Returns:
            bool: True if valid, raises exception if invalid
        """
        if not hasattr(signal_type, 'Field'):
            raise StandardizedValidationError({
                'field_name': f"Invalid signal type: {signal_type.__name__}"
            })
            
        valid_fields = [choice[0] for choice in signal_type.Field.choices]
        
        if field_name not in valid_fields:
            raise StandardizedValidationError({
                'field_name': f"Invalid field name. Must be one of: {', '.join(valid_fields)}"
            })
            
        return True