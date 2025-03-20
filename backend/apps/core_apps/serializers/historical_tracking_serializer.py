# apps/core_apps/serializers/historical_tracking_serializer.py

from rest_framework import serializers

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
        # Get user from request context
        user = self.context.get('request').user if self.context.get('request') else None
        
        # Track changes for all fields
        for field_name, new_value in validated_data.items():
            # Skip tracking for non-model fields
            if field_name not in instance._meta.fields_map and field_name not in instance._meta.private_fields:
                continue
                
            # Get current value
            old_value = getattr(instance, field_name)
            
            # Only track if value has changed
            if old_value != new_value:
                instance.track_field_change(field_name, old_value, new_value, user)
        
        # Call the parent update method
        return super().update(instance, validated_data)