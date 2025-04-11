# apps/signals/views/qualification_signal_view.py

from rest_framework import status
from rest_framework.response import Response
from django.db.models import Q
from core.exceptions import StandardizedValidationError
from .base_signal_view import BaseSignalView
from ..models.qualification_signal_model import QualificationSignal
from ..serializers.qualification_signal_serializer import QualificationSignalSerializer


class QualificationSignalView(BaseSignalView):
    """
    API View for qualification signals (objectives, motivations, metrics, etc.)
    """
    serializer_class = QualificationSignalSerializer
    
    def get_queryset(self):
        """Get qualification signals with appropriate filters"""
        queryset = QualificationSignal.objects.select_related(
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
            
            # Confirmation count filter
            min_confirmations = self.request.query_params.get('min_confirmations')
            if min_confirmations and min_confirmations.isdigit():
                queryset = queryset.filter(confirmation_count__gte=int(min_confirmations))
            
            # Search filter
            search = self.request.query_params.get('search')
            if search:
                queryset = queryset.filter(
                    Q(value__icontains=search)
                )
        
        # Apply client scoping
        return self.filter_queryset_by_client(queryset)
    
    def by_account(self, request):
        """Get all qualification signals for an account grouped by field"""
        account_id = request.query_params.get('account_id')
        if not account_id:
            raise StandardizedValidationError({
                'account_id': 'Account ID is required'
            })
        
        # Get approved signals for this account
        queryset = self.get_queryset().filter(
            account_id=account_id,
            status=QualificationSignal.Status.APPROVED
        )
        
        # Group by field_name
        result = {}
        for field in QualificationSignal.Field.choices:
            field_code = field[0]  # Get the field code, e.g., 'objectives'
            field_signals = queryset.filter(field_name=field_code)
            
            if field_signals.exists():
                serializer = self.serializer_class(field_signals, many=True)
                result[field_code] = serializer.data
        
        return Response(result)
        
    # Empty implementations for methods not used in this view
    def by_tech_stack(self, request):
        raise StandardizedValidationError({'error': 'Method not available for qualification signals'})
        
    def account_tech_evaluation(self, request):
        raise StandardizedValidationError({'error': 'Method not available for qualification signals'})
        
    def account_profile(self, request):
        raise StandardizedValidationError({'error': 'Method not available for qualification signals'})