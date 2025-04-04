# apps/core_apps/serializers/historical_tracking_serializer.py

from rest_framework import serializers
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from django.db import models

class HistoricalTrackingSerializerMixin:
    """
    Serializer mixin for models that use HistoricalTrackingModel.
    Handles historical data tracking and provides consistent field access.
    """
    historical_data = serializers.JSONField(read_only=True)
    
    def update(self, instance, validated_data):
        """
        Override update to track field changes.
        Detects changes to fields and records them in the historical_data.
        """
        try:
            # Get user from request context
            user = self.context.get('request').user if self.context.get('request') else None
            
            # Check for signal_id in context
            signal = None
            signal_id = self.context.get('signal_id')
            if signal_id:
                try:
                    from apps.sales_insight.models import Signal
                    try:
                        signal = Signal.objects.get(id=signal_id)
                    except Signal.DoesNotExist:
                        pass
                except ImportError:
                    pass
            
            # Store original values for comparison
            original_values = {}
            for field_name in validated_data.keys():
                if hasattr(instance, field_name):
                    original_values[field_name] = getattr(instance, field_name)
            
            # Call the parent update method to update fields
            # Use serializers.ModelSerializer.update directly to avoid MRO issues
            instance = serializers.ModelSerializer.update(self, instance, validated_data)
            
            # Now track the changes explicitly using HistoricalTrackingService directly
            from apps.core_apps.services.historical_tracking_service import HistoricalTrackingService
            
            for field_name, old_value in original_values.items():
                new_value = getattr(instance, field_name)
                
                # Compare values and track if different
                if old_value != new_value:
                    HistoricalTrackingService.update_field(
                        instance=instance,
                        field_name=field_name,
                        new_value=new_value,
                        user=user,
                        signal=signal,
                        update_model=False
                    )
            
            return instance
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(CoreErrorMessages.UNEXPECTED_ERROR.format(detail=e))
    
    def to_representation(self, instance):
        """
        Override to_representation to ensure historical_data is included.
        """
        representation = super().to_representation(instance)
        
        # Ensure historical_data is included if supported by the model
        if hasattr(instance, 'historical_data'):
            representation['historical_data'] = instance.historical_data
        
        return representation
    
    def get_signal_history(self, instance, field_name):
        """
        Get signal history for a specific field.
        Returns a list of signal IDs that have modified this field.
        """
        if not hasattr(instance, 'historical_data') or not instance.historical_data:
            return []
            
        # Check if field has historical entries
        if field_name not in instance.historical_data:
            return []
            
        # Extract signal IDs from changes
        signal_history = []
        
        # Handle both old and new format
        changes = instance.historical_data[field_name]
        if isinstance(changes, dict) and 'changes' in changes:
            changes = changes['changes']
            
        for change in changes:
            if isinstance(change, dict) and change.get('source') == 'signal':
                signal_id = change.get('signal_id')
                if signal_id and signal_id not in signal_history:
                    signal_history.append(signal_id)
                    
                # Also include merged signals if present
                merged_signals = change.get('merged_from_signals', [])
                for merged_id in merged_signals:
                    if merged_id and merged_id not in signal_history:
                        signal_history.append(merged_id)
                        
        return signal_history
    
    def _process_json_item_operation(self, instance, field_name, data, user):
        """Process JSON item operations - standardized handling for all models."""
        if not isinstance(data, dict):
            return False
            
        operation = data.get('operation')
        if not operation:
            return False
            
        try:
            # Dispatch based on operation type
            if operation == 'add':
                item = data.get('item')
                if not item:
                    return False
                    
                # Try qualification method first, then tracked method
                for method_name in ['add_qualification_item', 'add_tracked_json_item']:
                    if hasattr(instance, method_name):
                        method = getattr(instance, method_name)
                        return method(field_name, item, user)
                        
            elif operation == 'update':
                item_id = data.get('item_id')
                item = data.get('item')
                id_key = data.get('id_key', 'id')
                
                if not (item_id and item):
                    return False
                    
                # Try both methods
                if hasattr(instance, 'update_qualification_item'):
                    return instance.update_qualification_item(field_name, item_id, item, user, None, id_key)
                elif hasattr(instance, 'update_tracked_json_item'):
                    return instance.update_tracked_json_item(field_name, item_id, item, id_key, user)
                    
            elif operation == 'remove':
                item_id = data.get('item_id')
                id_key = data.get('id_key', 'id')
                
                if not item_id:
                    return False
                    
                # Try both methods
                if hasattr(instance, 'remove_qualification_item'):
                    return instance.remove_qualification_item(field_name, item_id, user, None)
                elif hasattr(instance, 'remove_tracked_json_item'):
                    return instance.remove_tracked_json_item(field_name, item_id, id_key, user)
            
            # Unknown operation
            return False
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_OPERATION.format(
                    operation=f"Failed to perform {operation} operation on {field_name}"
                )
            )
    
    def update(self, instance, validated_data):
        """
        Generic update method for models with historical tracking.
        Handles JSON item operations and tracks field changes.
        """
        # Get user from request context
        user = self.context.get('request').user if self.context.get('request') else None
        
        # Store original values for tracking changes
        original_values = {}
        for field_name in validated_data.keys():
            if hasattr(instance, field_name):
                original_values[field_name] = getattr(instance, field_name)
        
        # Check for JSON fields in the model
        json_field_names = []
        for field in instance._meta.get_fields():
            if isinstance(field, models.JSONField):
                json_field_names.append(field.name)
        
        # Process any JSON operations in the initial data
        for field_name in json_field_names:
            # Get the field data from the original request
            if field_name in self.initial_data:
                field_data = self.initial_data[field_name]
                
                # Try to process as an item operation
                if isinstance(field_data, dict) and 'operation' in field_data:
                    # Process operation and remove from validated_data if successful
                    if self._process_json_item_operation(instance, field_name, field_data, user):
                        if field_name in validated_data:
                            validated_data.pop(field_name)
        
        # Call parent update method to handle regular field updates
        instance = serializers.ModelSerializer.update(self, instance, validated_data)
        
        # Explicitly track any fields that might have been missed
        for field_name, old_value in original_values.items():
            new_value = getattr(instance, field_name)
            
            # Only track if value changed
            if old_value != new_value and hasattr(instance, 'track_field_change'):
                instance.track_field_change(field_name, old_value, new_value, user)
        
        return instance