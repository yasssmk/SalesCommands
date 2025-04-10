# apps/core_apps/views/signal_view_mixins.py

from rest_framework.response import Response
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError

class SignalAwareViewMixin:
    """Mixin for views to handle signal-related endpoints."""
    
    def get_serializer_context(self):
        """Add signal info flag and department filter to serializer context."""
        context = super().get_serializer_context()
        
        # Check if signal info was requested via query param
        include_signal_info = self.request.query_params.get('include_signal_info', 'false').lower() == 'true'
        context['include_signal_info'] = include_signal_info
        
        # Check if department filter was specified
        department_id = self.request.query_params.get('department_id')
        if department_id:
            try:
                from apps.core_apps.models import StandardDepartment
                department = StandardDepartment.objects.get(id=department_id)
                context['department'] = department
            except StandardDepartment.DoesNotExist:
                # Just ignore invalid department
                pass
        
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
                    
            elif endpoint_type == 'qualification':
                if request.method == 'GET':
                    return self.get_qualification(request, *args, **kwargs)
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_signals(self, request, pk=None, *args, **kwargs):
        """Get all signals related to this entity."""
        try:
            entity = self.get_objects([pk]).first()
            if not entity:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Check if entity implements SignalQualifiedEntity interface
            if not hasattr(entity, 'get_qualification_signals'):
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_OPERATION: "Entity does not support qualification signals"
                })
            
            field_name = request.query_params.get('field_name')
            department_id = request.query_params.get('department_id')
            min_confirmations = request.query_params.get('min_confirmations')
            include_expired = request.query_params.get('include_expired', 'false').lower() == 'true'
            
            # Build filters
            filters = {}
            
            if field_name:
                filters['field_name'] = field_name
            
            if department_id:
                try:
                    from apps.core_apps.models import StandardDepartment
                    department = StandardDepartment.objects.get(id=department_id)
                    filters['department'] = department
                except StandardDepartment.DoesNotExist:
                    pass
            
            if min_confirmations and min_confirmations.isdigit():
                filters['min_confirmations'] = int(min_confirmations)
            
            filters['include_expired'] = include_expired
            
            # Get signals
            signals = entity.get_qualification_signals(**filters)
            
            # Serialize signals
            from apps.signals.serializers import SignalSerializer
            serializer = SignalSerializer(signals, many=True)
            
            return Response(serializer.data)
            
        except Exception as e:
            return self.handle_exception(e)
    
    def get_field_signals(self, request, pk=None, *args, **kwargs):
        """Get signals related to a specific field."""
        try:
            entity = self.get_objects([pk]).first()
            if not entity:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            field_name = request.query_params.get('field_name')
            if not field_name:
                raise StandardizedValidationError({
                    CoreErrorMessages.REQUIRED_FIELD: "field_name is required"
                })
            
            # Use signal data service to get field data with signals
            from apps.signals.services.signal_data_service import SignalDataService
            
            department_id = request.query_params.get('department_id')
            department = None
            
            if department_id:
                try:
                    from apps.core_apps.models import StandardDepartment
                    department = StandardDepartment.objects.get(id=department_id)
                except StandardDepartment.DoesNotExist:
                    pass
            
            # Get account from entity
            account = entity if hasattr(entity, 'get_qualification_signals') else entity.account
            
            # Get field data with signals
            field_data = SignalDataService.get_field_data(
                account=account,
                field_name=field_name,
                department=department,
                include_signal_info=True
            )
            
            if not field_data:
                return Response({
                    'field_name': field_name,
                    'value': None,
                    'signals': []
                })
            
            return Response(field_data)
            
        except Exception as e:
            return self.handle_exception(e)
    
    def get_qualification(self, request, pk=None, *args, **kwargs):
        """Get qualification data with filtering options."""
        try:
            entity = self.get_objects([pk]).first()
            if not entity:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Check if entity implements SignalQualifiedEntity interface
            if not hasattr(entity, 'get_qualification_data'):
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_OPERATION: "Entity does not support qualification data"
                })
            
            # Parse filter parameters
            department_id = request.query_params.get('department_id')
            field_names = request.query_params.get('field_names')
            min_confirmations = request.query_params.get('min_confirmations')
            include_signal_info = request.query_params.get('include_signal_info', 'false').lower() == 'true'
            
            # Build filters
            filters = {}
            
            if department_id:
                try:
                    from apps.core_apps.models import StandardDepartment
                    department = StandardDepartment.objects.get(id=department_id)
                    filters['department'] = department
                except StandardDepartment.DoesNotExist:
                    pass
            
            if field_names:
                # Convert from comma-separated string to list if needed
                if ',' in field_names:
                    field_list = [name.strip() for name in field_names.split(',')]
                    filters['field_names'] = field_list
                else:
                    filters['field_names'] = [field_names]
            
            if min_confirmations and min_confirmations.isdigit():
                filters['min_confirmations'] = int(min_confirmations)
            
            filters['include_signal_info'] = include_signal_info
            
            # Get qualification data
            qualification_data = entity.get_qualification_data(**filters)
            
            return Response(qualification_data)
            
        except Exception as e:
            return self.handle_exception(e)