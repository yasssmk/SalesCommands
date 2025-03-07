from rest_framework import serializers

class SignalAwareSerializerMixin(serializers.Serializer):
    """Mixin for serializers to handle signal-related fields."""
    
    signal_metadata = serializers.JSONField(required=False, allow_null=True, read_only=True)
    include_signal_info = serializers.BooleanField(write_only=True, required=False, default=False)
    
    qualification_with_signals = serializers.SerializerMethodField(read_only=True)
    profile_with_signals = serializers.SerializerMethodField(read_only=True)
    
    def get_qualification_with_signals(self, obj):
        """Get qualification data with signals if requested."""
        include_signals = self.context.get('include_signal_info', False)
        if not include_signals:
            return None
            
        return obj.get_qualification_data(include_signal_info=True)
    
    def get_profile_with_signals(self, obj):
        """Get profile data with signals if requested."""
        include_signals = self.context.get('include_signal_info', False)
        if not include_signals:
            return None
            
        return obj.get_profile_data(include_signal_info=True)
    
    def to_representation(self, instance):
        """Customize output based on query parameters."""
        representation = super().to_representation(instance)
        
        include_signals = self.context.get('include_signal_info', False)
        
        if not include_signals:
            representation.pop('qualification_with_signals', None)
            representation.pop('profile_with_signals', None)
        
        return representation