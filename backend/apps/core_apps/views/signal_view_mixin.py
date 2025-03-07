# apps/core_apps/views/signal_view_mixins.py

from rest_framework.response import Response
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError

class SignalAwareViewMixin:
    """Mixin for views to handle signal-related endpoints."""
    
    def get_serializer_context(self):
        """Add signal info flag to serializer context."""
        context = super().get_serializer_context()
        
        include_signal_info = self.request.query_params.get('include_signal_info', 'false').lower() == 'true'
        context['include_signal_info'] = include_signal_info
        
        return context
    
    def dispatch(self, request, *args, **kwargs):
        """Custom dispatch to handle different endpoints."""
        path = request.path.split('/')
        
        if len(path) > 4:
            endpoint_type = path[4]
            
            if endpoint_type == 'signals':
                if request.method == 'GET':
                    return self.get_signals(request, *args, **kwargs)
            
            elif endpoint_type == 'field-signals':
                if request.method == 'GET':
                    return self.get_field_signals(request, *args, **kwargs)
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_signals(self, request, pk=None, *args, **kwargs):
        """Get all signals related to this entity."""
        try:
            entity = self.get_objects([pk]).first()
            if not entity:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            field_name = request.query_params.get('field_name')
            category = request.query_params.get('category')
            include_expired = request.query_params.get('include_expired', 'false').lower() == 'true'
            
            signals = entity.get_related_signals(
                field_name=field_name,
                category=category,
                include_expired=include_expired
            )
            
            result = {}
            for status, queryset in signals.items():
                if queryset.exists():
                    from apps.sales_insight.serializers import SignalSerializer
                    result[status] = SignalSerializer(queryset, many=True).data
                else:
                    result[status] = []
            
            return Response(result)
            
        except Exception as exc:
            return self.handle_exception(exc)
    
    def get_field_signals(self, request, pk=None, *args, **kwargs):
        """Get signals related to a specific field."""
        try:
            entity = self.get_objects([pk]).first()
            if not entity:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            field_name = request.query_params.get('field_name')
            if not field_name:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="field_name")
                )
            
            signals = entity.get_related_signals(
                field_name=field_name,
                include_expired=True
            )
            
            field_metadata = entity.get_field_signal_metadata(field_name)
            
            result = {
                'field_name': field_name,
                'current_value': getattr(entity, field_name, None),
                'metadata': field_metadata
            }
            
            for status, queryset in signals.items():
                if queryset.exists():
                    from apps.sales_insight.serializers import SignalSerializer
                    result[f'{status}_signals'] = SignalSerializer(queryset, many=True).data
                else:
                    result[f'{status}_signals'] = []
            
            return Response(result)
            
        except Exception as exc:
            return self.handle_exception(exc)