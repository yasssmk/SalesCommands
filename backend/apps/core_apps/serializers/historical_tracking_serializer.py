# apps/core_apps/serializers/historical_tracking_serializer.py

from rest_framework import serializers
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages

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
            
            # Store original values for comparison
            original_values = {}
            for field_name in validated_data.keys():
                if hasattr(instance, field_name):
                    original_values[field_name] = getattr(instance, field_name)
            
            # Call the parent update method to update fields
            instance = super().update(instance, validated_data)
            
            # Now track the changes explicitly
            if hasattr(instance, 'track_field_change'):
                for field_name, old_value in original_values.items():
                    new_value = getattr(instance, field_name)
                    
                    # Compare values and track if different
                    if old_value != new_value:
                        instance.track_field_change(field_name, old_value, new_value, user)
                
                # Make sure changes are saved
                if hasattr(instance, 'save'):
                    instance.save(update_fields=['historical_data'])
            
            return instance
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(CoreErrorMessages.UNEXPECTED_ERROR)
    
    def to_representation(self, instance):
        """
        Override to_representation to ensure historical_data is included.
        """
        representation = super().to_representation(instance)
        
        # Ensure historical_data is included if supported by the model
        if hasattr(instance, 'historical_data'):
            representation['historical_data'] = instance.historical_data
        
        return representation