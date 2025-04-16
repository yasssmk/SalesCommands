# apps/signals/utils/signal_helpers.py

from django.db.models import Q
from ..models.qualification_signal_model import QualificationSignal
from ..models.tech_stack_signal_model import TechStackSignal
from ..models.profile_signal_model import ProfileSignal
from ..models.base_signal_model import BaseSignal
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
    
    @classmethod
    def validate_for_approval(cls, signal):
        """
        Check if a signal has all required fields for approval.
        
        Args:
            signal: Signal instance to validate
            
        Returns:
            dict: Dictionary with validation results
            {
                'is_valid': bool,
                'missing_fields': list,
                'suggested_actions': list
            }
        """
        result = {
            'is_valid': True,
            'missing_fields': [],
            'suggested_actions': []
        }
        
        # Common validation for all signal types
        if not signal:
            result['is_valid'] = False
            result['missing_fields'].append('signal')
            return result
            
        if signal.status != BaseSignal.Status.PENDING:
            result['is_valid'] = False
            result['missing_fields'].append('status')
            result['suggested_actions'].append("Only pending signals can be approved")
            return result
        
        # Type-specific validation
        if isinstance(signal, QualificationSignal):
            # Qualification signals require a source contact
            if not signal.source_contact:
                result['is_valid'] = False
                result['missing_fields'].append('source_contact')
                result['suggested_actions'].append("Select a contact who provided this information")
        
        # Tech stack signals require a tech_stack or pending_tech_name
        elif isinstance(signal, TechStackSignal):
            if not signal.tech_stack:
                # Check if we have a pending tech name in metadata
                tech_name = None
                if signal.metadata and 'pending_tech_name' in signal.metadata:
                    tech_name = signal.metadata['pending_tech_name']
                    
                if not tech_name:
                    result['is_valid'] = False
                    result['missing_fields'].append('tech_stack')
                    result['suggested_actions'].append("Select or create a technology for this signal")
                else:
                    # We have a pending tech name but no tech stack yet
                    result['suggested_actions'].append(f"Create or select a tech stack for '{tech_name}'")
        
        return result

    @classmethod
    def get_required_fields_for_approval(cls, category):
        """
        Get a list of fields required for approving a signal of the given category.
        
        Args:
            category (str): Signal category 
            
        Returns:
            list: List of required field names
        """
        common_fields = ['value']
        
        if category.upper() == 'QUALIFICATION':
            return common_fields + ['source_contact']
        elif category.upper() == 'TECH_STACK':
            return common_fields + ['tech_stack']
        elif category.upper() == 'PROFILE':
            return common_fields
        
        return common_fields