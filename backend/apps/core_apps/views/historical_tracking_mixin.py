# apps/core_apps/views/historical_tracking_mixin.py

from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.response import Response
import copy
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages


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
                field_data = request_data.get(field)
                
                # Check if this is an item operation rather than full field replacement
                operation_performed = False
                
                if isinstance(field_data, dict) and 'operation' in field_data:
                    operation = field_data.get('operation')
                    item_id = field_data.get('item_id')
                    item = field_data.get('item')
                    id_key = field_data.get('id_key', 'id')
                    
                    # Handle different operations
                    try:
                        if operation == 'add' and item:
                            if hasattr(instance, 'add_tracked_json_item'):
                                operation_performed = instance.add_tracked_json_item(
                                    field, item, user
                                )
                            elif hasattr(instance, 'add_qualification_item'):
                                operation_performed = instance.add_qualification_item(
                                    field, item, user
                                )
                                
                        elif operation == 'update' and item_id and item:
                            if hasattr(instance, 'update_tracked_json_item'):
                                operation_performed = instance.update_tracked_json_item(
                                    field, item_id, item, id_key, user
                                )
                            elif hasattr(instance, 'update_qualification_item'):
                                operation_performed = instance.update_qualification_item(
                                    field, item_id, item, user
                                )
                                
                        elif operation == 'remove' and item_id:
                            if hasattr(instance, 'remove_tracked_json_item'):
                                operation_performed = instance.remove_tracked_json_item(
                                    field, item_id, id_key, user
                                )
                            elif hasattr(instance, 'remove_qualification_item'):
                                operation_performed = instance.remove_qualification_item(
                                    field, item_id, user
                                )
                    except StandardizedValidationError:
                        # Re-raise standardized errors
                        raise
                    except Exception:
                        raise StandardizedValidationError(
                            CoreErrorMessages.INVALID_OPERATION.format(
                                operation=f"Failed to perform {operation} operation on {field}"
                            )
                        )
                
                # If no item operation was performed, track as complete field update
                if not operation_performed:
                    # Get old and new values
                    old_json = original_values[field] or []
                    new_json = getattr(instance, field) or []
                    
                    # If overall field was changed
                    if old_json != new_json:
                        # Track entire field update
                        if hasattr(instance, 'track_field_change'):
                            instance.track_field_change(field, old_json, new_json, user)


class AccountHistoricalTrackingMixin(HistoricalTrackingViewMixin):
    """Account-specific implementation of the historical tracking mixin"""
    
    # Fields to track for Account model
    tracked_fields = {
        'company_name', 'industry', 'type', 'classification', 
        'company_size', 'annual_revenue', 'has_buying_decision'
    }
    
    # JSON fields to track for Account model
    tracked_json_fields = {
        'objectives', 'motivations', 'metrics', 'pain_points', 'implications'
    }

class ContactHistoricalTrackingMixin(HistoricalTrackingViewMixin):
    """Contact-specific implementation of the historical tracking mixin"""
    
    # Fields to track for Contact model
    tracked_fields = {
        'first_name', 'last_name', 'job_title', 'department', 
        'influence_level', 'email', 'phone', 'has_buying_authority'
    }
    
    # JSON fields to track for Contact model
    tracked_json_fields = {
        'objectives', 'motivations', 'pain_points', 'metrics'
    }

class TechStackHistoricalTrackingMixin(HistoricalTrackingViewMixin):
    """TechStack-specific implementation of the historical tracking mixin"""
    
    # Fields to track for TechStack model
    tracked_fields = {
        'tech_name', 'purpose', 'annual_cost', 
        'renewal_date', 'years_of_usage', 'notes'
    }
    
    # JSON fields to track for TechStack model
    tracked_json_fields = {
        'pros', 'cons'
    }