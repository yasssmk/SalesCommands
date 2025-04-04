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