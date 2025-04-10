# apps/core_apps/views/historical_tracking_mixin.py

from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
import copy
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages

class HistoricalTrackingViewMixin:
    """
    Mixin for API views to track changes to model fields and create signals
    for qualification data when updates are made through PUT/PATCH requests.
    """
    
    # Override in child classes to specify which fields should be tracked
    tracked_fields = None  # example: {'company_name', 'industry', 'type', 'classification'}
    
    # Override in child classes to specify which fields should create signals
    signal_fields = None  # example: {'objectives', 'motivations', 'metrics', 'pain_points'}
    
    def _track_update(self, request, *args, partial=False, **kwargs):
        """
        Handle tracking for updates by comparing before and after states
        """
        instance = self.get_object()
        
        # Store original values before update
        original_values = {}
        
        # Track regular fields
        if self.tracked_fields:
            for field in self.tracked_fields:
                if hasattr(instance, field):
                    original_values[field] = copy.deepcopy(getattr(instance, field))
        
        # Track signal fields
        if self.signal_fields:
            for field in self.signal_fields:
                if field in request.data:
                    # Create signals for these fields instead of updating model fields
                    self._create_signal_for_field(instance, field, request.data[field], request.user)
        
        # Call parent update method (from DRF's UpdateModelMixin)
        update_method = super().partial_update if partial else super().update
        response = update_method(request, *args, **kwargs)
        
        # If update was successful, track changes to regular fields
        if response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED):
            # Refresh instance from database to get updated values
            instance.refresh_from_db()
            user = request.user if hasattr(request, 'user') else None
            
            # Process tracked fields
            if self.tracked_fields:
                self._process_field_changes(instance, original_values, user)
        
        return response
    
    def _create_signal_for_field(self, instance, field_name, value, user):
        from apps.signals.services.signal_creation_service import SignalCreationService
        return SignalCreationService.create_signal_for_field(instance, field_name, value, user)
    
    def _process_field_changes(self, instance, original_values, user):
        """Process changes to regular fields"""
        changed = False
        
        for field in self.tracked_fields:
            if field in original_values:
                old_value = original_values[field]
                new_value = getattr(instance, field)
                
                # Only track if value changed
                if old_value != new_value:
                    changed = True
                    
                    if hasattr(instance, 'track_field_change'):
                        # Track the change
                        instance.track_field_change(field, old_value, new_value, user)
        
        # If changes were detected but not tracked, force historical data update
        if changed and (not instance.historical_data or instance.historical_data == {}):
            # Initialize historical_data if empty
            if not instance.historical_data:
                instance.historical_data = {}
            instance.save(update_fields=['historical_data'])
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """
        Get historical data for an entity.
        
        GET /api/{entity}/{id}/history/
        """
        try:
            instance = self.get_object()
            
            # Check if instance has historical data
            if not hasattr(instance, 'historical_data') or not instance.historical_data:
                return Response({
                    'message': 'No historical data available for this entity'
                })
            
            # Get field filter if provided
            field_filter = request.query_params.get('field')
            
            # Filter historical data if field specified
            if field_filter:
                if field_filter in instance.historical_data:
                    history = {field_filter: instance.historical_data[field_filter]}
                else:
                    history = {}
            else:
                history = instance.historical_data
            
            return Response(history)
            
        except Exception as e:
            return self.handle_exception(e)