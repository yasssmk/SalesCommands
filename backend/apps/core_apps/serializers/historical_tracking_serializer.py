from rest_framework import serializers
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from django.db import models

class HistoricalTrackingSerializerMixin:
    """
    Serializer mixin for models that use HistoricalTrackingModel.
    Handles historical data tracking and provides consistent field access.
    Enhanced to support signal-based qualification data.
    """
    historical_data = serializers.JSONField(read_only=True)
    
    def update(self, instance, validated_data):
        """
        Override update to track field changes and create signals.
        """
        try:
            # Get user from request context
            user = self.context.get('request').user if self.context.get('request') else None
            
            # Store original values for comparison
            original_values = {}
            for field_name in validated_data.keys():
                if hasattr(instance, field_name):
                    original_values[field_name] = getattr(instance, field_name)
            
            # Check for qualification fields that should create signals
            qualification_fields = self.get_qualification_fields()
            for field_name in list(validated_data.keys()):
                if field_name in qualification_fields:
                    value = validated_data.pop(field_name)
                    self._create_signal_for_field(instance, field_name, value, user)
            
            # Call the parent update method to update remaining fields
            instance = serializers.ModelSerializer.update(self, instance, validated_data)
            
            # Now track the changes explicitly for regular fields
            from apps.core_apps.services.historical_tracking_service import HistoricalTrackingService
            
            for field_name, old_value in original_values.items():
                if field_name not in qualification_fields:  # Skip fields handled via signals
                    new_value = getattr(instance, field_name)
                    
                    # Compare values and track if different
                    if old_value != new_value:
                        HistoricalTrackingService.update_field(
                            instance=instance,
                            field_name=field_name,
                            new_value=new_value,
                            user=user,
                            update_model=False
                        )
            
            return instance
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(CoreErrorMessages.UNEXPECTED_ERROR.format(detail=str(e)))
    
    def get_qualification_fields(self):
        """Get qualification fields that should create signals."""
        # Default set of qualification fields
        qualification_fields = {
            'objectives', 'motivations', 'metrics', 'pain_points', 'implications',
            'pros', 'cons', 'purpose', 'annual_costs', 'renewal_date', 'start_year_of_usage'
        }
        
        # Filter to fields that are actually in the initial data
        return set(self.initial_data.keys()).intersection(qualification_fields)
    
    def _create_signal_for_field(self, instance, field_name, value, user):
        from apps.signals.services.signal_creation_service import SignalCreationService
        return SignalCreationService.create_signal_for_field(instance, field_name, value, user)