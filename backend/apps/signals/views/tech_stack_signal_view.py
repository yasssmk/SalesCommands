# apps/signals/views/tech_stack_signal_view.py

from rest_framework import status
from rest_framework.response import Response
from django.db.models import Q
from core.exceptions import StandardizedValidationError
from .base_signal_view import BaseSignalView
from ..models.tech_stack_signal_model import TechStackSignal
from ..serializers.tech_stack_signal_serializer import TechStackSignalSerializer


class TechStackSignalView(BaseSignalView):
    """
    API View for technology stack signals (pros, cons, costs, etc.)
    """
    serializer_class = TechStackSignalSerializer
    
    def get_queryset(self):
        """Get tech stack signals with appropriate filters"""
        queryset = TechStackSignal.objects.select_related(
            'account',
            'tech_stack',
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
            
            # Tech stack filter
            tech_stack_id = self.request.query_params.get('tech_stack_id')
            if tech_stack_id:
                queryset = queryset.filter(tech_stack_id=tech_stack_id)
            
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
            
            # Search filter
            search = self.request.query_params.get('search')
            if search:
                queryset = queryset.filter(
                    Q(value__icontains=search) | 
                    Q(tech_stack__tech_name__icontains=search)
                )
        
        # Apply client scoping
        return self.filter_queryset_by_client(queryset)
    
    def by_tech_stack(self, request):
        """Get all signals for a specific tech stack grouped by field"""
        tech_stack_id = request.query_params.get('tech_stack_id')
        if not tech_stack_id:
            raise StandardizedValidationError({
                'tech_stack_id': 'Tech Stack ID is required'
            })
        
        # Get approved signals for this tech stack
        queryset = self.get_queryset().filter(
            tech_stack_id=tech_stack_id,
            status=TechStackSignal.Status.APPROVED
        )
        
        # Group by field_name
        result = {}
        for field in TechStackSignal.Field.choices:
            field_code = field[0]  # Get the field code, e.g., 'pros'
            field_signals = queryset.filter(field_name=field_code)
            
            if field_signals.exists():
                serializer = self.serializer_class(field_signals, many=True)
                result[field_code] = serializer.data
        
        return Response(result)
    
    def account_tech_evaluation(self, request):
        """Get tech stack evaluation data for an account"""
        account_id = request.query_params.get('account_id')
        if not account_id:
            raise StandardizedValidationError({
                'account_id': 'Account ID is required'
            })
        
        # Get all approved tech stack signals for this account
        queryset = self.get_queryset().filter(
            account_id=account_id,
            status=TechStackSignal.Status.APPROVED
        )
        
        # Get all tech stacks for this account
        from apps.accounts.models import TechStack
        tech_stacks = TechStack.objects.filter(account_id=account_id)
        
        # Group signals by tech stack
        result = {}
        for tech_stack in tech_stacks:
            tech_signals = queryset.filter(tech_stack=tech_stack)
            
            if tech_signals.exists():
                tech_data = {
                    'tech_id': str(tech_stack.id),
                    'tech_name': tech_stack.tech_name,
                    'signals': {}
                }
                
                # Group by field name within each tech stack
                for field in TechStackSignal.Field.choices:
                    field_code = field[0]
                    field_signals = tech_signals.filter(field_name=field_code)
                    
                    if field_signals.exists():
                        serializer = self.serializer_class(field_signals, many=True)
                        tech_data['signals'][field_code] = serializer.data