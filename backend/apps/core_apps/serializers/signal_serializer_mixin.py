# apps/core_apps/serializers/signal_serializer_mixin.py

from rest_framework import serializers
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages

class SignalAwareSerializerMixin(serializers.Serializer):
    """
    Mixin for serializers to handle signal-related fields and operations.
    Supports including signal data and metadata in API responses.
    """
    
    # Signal-related fields
    signal_metadata = serializers.JSONField(required=False, allow_null=True, read_only=True)
    
    # Method fields for signal data
    qualification_with_signals = serializers.SerializerMethodField(read_only=True)
    profile_with_signals = serializers.SerializerMethodField(read_only=True)
    
    def get_qualification_data(self, instance):
        """Get qualification data based on include_signal_info parameter."""
        try:
            include_signals = self.context.get('include_signal_info', False)
            
            # Check if instance supports qualification data
            if not hasattr(instance, 'get_qualification_data'):
                return None
                
            return instance.get_qualification_data(include_signal_info=include_signals)
        except Exception:
            return None
    
    def get_qualification_with_signals(self, instance):
        """Get qualification data with signals if requested."""
        try:
            include_signals = self.context.get('include_signal_info', False)
            if not include_signals:
                return None
                
            # Check if instance supports qualification data
            if not hasattr(instance, 'get_qualification_data'):
                return None
                
            return instance.get_qualification_data(include_signal_info=True)
        except Exception:
            return None
    
    def get_profile_with_signals(self, instance):
        """Get profile data with signals if requested."""
        try:
            include_signals = self.context.get('include_signal_info', False)
            if not include_signals:
                return None
                
            # Check if instance supports profile data
            if not hasattr(instance, 'get_profile_data'):
                return None
                
            return instance.get_profile_data(include_signal_info=True)
        except Exception:
            return None
    
    def to_representation(self, instance):
        """Customize output based on query parameters."""
        try:
            representation = super().to_representation(instance)
            
            include_signals = self.context.get('include_signal_info', False)
            
            # Only include signal-related fields when requested
            if not include_signals:
                representation.pop('qualification_with_signals', None)
                representation.pop('profile_with_signals', None)
            
            # Ensure signal_metadata is included if supported by the model
            if hasattr(instance, 'signal_metadata'):
                representation['signal_metadata'] = instance.signal_metadata
            
            return representation
        except StandardizedValidationError:
            # Re-raise standardized errors
            raise
        except Exception as e:
            # Handle unexpected errors
            raise StandardizedValidationError(CoreErrorMessages.UNEXPECTED_ERROR)
    
    def create(self, validated_data):
        """Remove signal-specific fields before creating the model instance."""
        try:
            # Remove signal-specific fields
            if 'include_signal_info' in validated_data:
                validated_data.pop('include_signal_info')
                
            # Call the parent's create method
            return super().create(validated_data)
        except StandardizedValidationError:
            # Re-raise standardized errors
            raise
        except Exception as e:
            # Handle unexpected errors
            raise StandardizedValidationError(CoreErrorMessages.UNEXPECTED_ERROR)
    
    def update(self, instance, validated_data):
        """Remove signal-specific fields before updating the model instance."""
        try:
            # Remove signal-specific fields
            if 'include_signal_info' in validated_data:
                validated_data.pop('include_signal_info')
                
            # Call the parent's update method
            return super().update(instance, validated_data)
        except StandardizedValidationError:
            # Re-raise standardized errors
            raise
        except Exception as e:
            # Handle unexpected errors
            raise StandardizedValidationError(CoreErrorMessages.UNEXPECTED_ERROR)