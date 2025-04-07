# apps/accounts/views/buyingprocess_view.py

from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.db.models import Max, F
from core.apps_shared_methods import BaseAPIView
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from apps.accounts.models.buyingProcess import BuyingProcess, BuyingProcessStep, BuyingProcessStepContact
from apps.accounts.serializers.buyingprocess_serializer import BuyingProcessSerializer, BuyingProcessStepSerializer
from apps.core_apps.views import SignalAwareViewMixin, BuyingProcessTrackingMixin, BuyingProcessStepTrackingMixin

class BuyingProcessView(BaseAPIView, SignalAwareViewMixin, BuyingProcessTrackingMixin):
    """
    API view for managing buying processes with lifecycle tracking.
    """
    queryset = BuyingProcess.objects.select_related('account').prefetch_related('steps')
    serializer_class = BuyingProcessSerializer
    entity_name = 'buying_process'
    
    # Fields to track for BuyingProcess model
    tracked_fields = {
        'name', 'description', 'status', 'estimated_timeline_days', 'product'
    }
    
    def get_queryset(self):
        """Filter queryset by account if specified"""
        queryset = super().get_queryset()
        
        # Filter by account if provided in query params
        account_id = self.request.query_params.get('account_id')
        if account_id:
            queryset = queryset.filter(account_id=account_id)
            
        return queryset
    
    def get_with_steps(self, request, pk=None):
        """
        Get a buying process with all its steps in order.
        
        GET /api/buying-processes/{id}/with-steps
        """
        process = self.get_object()
        
        # Start with steps that have no previous step (the beginning of the chain)
        start_steps = process.steps.filter(previous_step__isnull=True).order_by('id')
        
        # Build the ordered list by following the next pointers
        ordered_steps = []
        for start_step in start_steps:
            # Add the start step
            ordered_steps.append(start_step)
            
            # Follow the chain
            current = start_step
            while True:
                # Get the next step in the chain
                next_step = current.next_steps.first()
                if not next_step:
                    break
                    
                # Add to the ordered list and move to the next step
                ordered_steps.append(next_step)
                current = next_step
        
        # Create response with nested steps
        process_data = self.get_serializer(process).data
        process_data['steps'] = BuyingProcessStepSerializer(ordered_steps, many=True).data
        
        return Response(process_data)

class BuyingProcessStepView(BaseAPIView, SignalAwareViewMixin, BuyingProcessStepTrackingMixin):
    """
    API view for managing buying process steps.
    """
    queryset = BuyingProcessStep.objects.select_related('process', 'account', 'standard_department').prefetch_related('contacts', 'next_steps')
    serializer_class = BuyingProcessStepSerializer
    entity_name = 'buying_process_step'
    
    # Fields to track for BuyingProcessStep model
    tracked_fields = {
        'previous_step', 'stakeholder', 'standard_department', 
        'step_description', 'step_goal', 'influence_score', 'average_time_in_days'
    }
    
    # JSON fields to track
    tracked_json_fields = {
        'criterias', 'metrics'
    }
    
    def get_queryset(self):
        """Filter queryset by process or account if specified"""
        queryset = super().get_queryset()
        
        # Filter by process if provided
        process_id = self.request.query_params.get('process_id')
        if process_id:
            queryset = queryset.filter(process_id=process_id)
        
        # Filter by account if provided
        account_id = self.request.query_params.get('account_id')
        if account_id:
            queryset = queryset.filter(account_id=account_id)
            
        return queryset
    
    @transaction.atomic
    def update_contacts(self, request, pk=None):
        """
        Update contacts for a buying process step.
        
        POST /api/buying-process-steps/{id}/contacts
        """
        step = self.get_object()
        serializer = self.get_serializer(instance=step, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def dispatch(self, request, *args, **kwargs):
        """Custom dispatch to handle different endpoints"""
        path = request.path.split('/')
        
        # Handle step-specific endpoints
        if len(path) > 4:
            endpoint_type = path[4]
            
            if endpoint_type == 'contacts':
                if request.method == 'POST':
                    return self.update_contacts(request, *args, **kwargs)
        
        # Default to standard dispatch
        return super().dispatch(request, *args, **kwargs)