# apps/core_apps/views/historical_tracking_mixin.py

from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.response import Response
import copy


class HistoricalTrackingViewMixin:
    """
    Mixin for API views to track changes to model fields automatically
    when updates are made through PUT/PATCH requests.
    """
    
    # Override in child classes to specify which fields should be tracked
    tracked_fields = None  # example: {'company_name', 'industry', 'type', 'classification'}
    
    # Override in child classes to specify which JSONFields have list operations 
    # and should track item changes
    tracked_json_fields = None  # example: {'objectives', 'motivations', 'key_kpis', 'pain_points'}
    
    def update(self, request, *args, **kwargs):
        """
        Override update method to track changes when objects are updated via PUT
        """
        return self._track_update(request, *args, partial=False, **kwargs)
        
    def partial_update(self, request, *args, **kwargs):
        """
        Override partial_update method to track changes when objects are updated via PATCH
        """
        return self._track_update(request, *args, partial=True, **kwargs)
    
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
        
        # Track JSON fields
        if self.tracked_json_fields:
            for field in self.tracked_json_fields:
                if hasattr(instance, field):
                    original_values[field] = copy.deepcopy(getattr(instance, field))
        
        # Call parent update method (from DRF's UpdateModelMixin)
        update_method = super().partial_update if partial else super().update
        response = update_method(request, *args, **kwargs)
        
        # If update was successful, track changes
        if response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED):
            # Refresh instance from database to get updated values
            instance.refresh_from_db()
            user = request.user if hasattr(request, 'user') else None
            
            # Process tracked fields
            if self.tracked_fields:
                self._process_field_changes(instance, original_values, user)
            
            # Process JSON fields (if applicable)
            if self.tracked_json_fields:
                self._process_json_field_changes(instance, original_values, request.data, user)
        
        return response
    
    def _process_field_changes(self, instance, original_values, user):
        """Process changes to regular fields"""
        for field in self.tracked_fields:
            if field in original_values:
                old_value = original_values[field]
                new_value = getattr(instance, field)
                
                # Only track if value changed
                if old_value != new_value:
                    if hasattr(instance, 'track_field_change'):
                        instance.track_field_change(field, old_value, new_value, user)
    
    def _process_json_field_changes(self, instance, original_values, request_data, user):
        """Process changes to JSON fields with array data"""
        for field in self.tracked_json_fields:
            # Only process field if it was in the request
            if field in request_data and field in original_values:
                # Get old and new values
                old_json = original_values[field] or []
                new_json = getattr(instance, field) or []
                
                # If overall field was changed
                if old_json != new_json:
                    # Complete field replacement
                    if not self._handle_json_item_operations(field, request_data):
                        # Track entire field update
                        if hasattr(instance, 'track_field_change'):
                            instance.track_field_change(field, old_json, new_json, user)
    
    def _handle_json_item_operations(self, field, request_data):
        """
        Check if request contains item operations rather than whole field replacement
        Return True if item operations were handled
        """
        # Detect operations on individual items
        field_data = request_data.get(field, {})
        
        # Check if this is a list operation by looking for operation key
        if isinstance(field_data, dict) and 'operation' in field_data:
            operation = field_data.get('operation')
            item_id = field_data.get('item_id')
            item = field_data.get('item')
            
            # Handle different operations
            if operation == 'add' and item:
                return True
            elif operation in ('update', 'remove') and item_id:
                return True
        
        return False


class AccountHistoricalTrackingMixin(HistoricalTrackingViewMixin):
    """Account-specific implementation of the historical tracking mixin"""
    
    # Fields to track for Account model
    tracked_fields = {
        'company_name', 'industry', 'type', 'classification', 
        'company_size', 'annual_revenue'
    }
    
    # JSON fields to track for Account model
    tracked_json_fields = {
        'objectives', 'motivations', 'key_kpis', 'pain_points', 'implications'
    }