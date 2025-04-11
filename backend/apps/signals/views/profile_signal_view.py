# apps/signals/views/profile_signal_view.py

from rest_framework import status
from rest_framework.response import Response
from django.db.models import Q
from core.exceptions import StandardizedValidationError
from .base_signal_view import BaseSignalView
from ..models.profile_signal_model import ProfileSignal
from ..serializers.profile_signal_serializer import ProfileSignalSerializer


class ProfileSignalView(BaseSignalView):
    """
    API View for profile signals (company size, revenue, etc.)
    """
    serializer_class = ProfileSignalSerializer
    
    def get_queryset(self):
        """Get profile signals with appropriate filters"""
        queryset = ProfileSignal.objects.select_related(
            'account',
            'source_contact',
            'source_department',
            'approved_by',
            'merged_into'
        )
        
        # Apply filters
        if self.request.method == 'GET':
            # Account filter
            account_id = self.request.query_params.get('account_id')
            if account_id:
                queryset = queryset.filter(account_id=account_id)
            
            # Field name filter
            field_name = self.request.query_params.get('field_name')
            if field_name:
                queryset = queryset.filter(field_name=field_name)
            
            # Status filter
            status_filter = self.request.query_params.get('status')
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            
            # Source filter
            source = self.request.query_params.get('source')
            if source:
                queryset = queryset.filter(source=source)
            
            # Value range filters for numeric values
            min_value = self.request.query_params.get('min_value')
            if min_value and min_value.isdigit():
                queryset = queryset.filter(value__gte=float(min_value))
                
            max_value = self.request.query_params.get('max_value')
            if max_value and max_value.isdigit():
                queryset = queryset.filter(value__lte=float(max_value))
        
        # Apply client scoping
        return self.filter_queryset_by_client(queryset)
    
    def account_profile(self, request):
        """Get approved profile signals for an account"""
        account_id = request.query_params.get('account_id')
        if not account_id:
            raise StandardizedValidationError({
                'account_id': 'Account ID is required'
            })
        
        # Get approved signals for this account
        queryset = self.get_queryset().filter(
            account_id=account_id,
            status=ProfileSignal.Status.APPROVED
        )
        
        # Convert to dictionary by field_name
        result = {}
        for signal in queryset:
            # For each field, use the most recent signal (or one with highest confirmation count)
            if signal.field_name not in result or result[signal.field_name]['confirmation_count'] < signal.confirmation_count:
                serializer = self.serializer_class(signal)
                result[signal.field_name] = serializer.data
        
        return Response(result)
        
    # Empty implementations for methods not used in this view
    def by_account(self, request):
        # Redirect to account_profile for consistency
        return self.account_profile(request)
        
    def by_tech_stack(self, request):
        raise StandardizedValidationError({'error': 'Method not available for profile signals'})
        
    def account_tech_evaluation(self, request):
        raise StandardizedValidationError({'error': 'Method not available for profile signals'})