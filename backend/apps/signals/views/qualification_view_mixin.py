# apps/signals/views/qualification_view_mixin.py

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages

class QualificationViewMixin:
    """
    Mixin for views to handle qualification data endpoints.
    Provides common methods for qualification and tech evaluation endpoints.
    """
    
    @action(detail=True, methods=['get'])
    def qualification(self, request, pk=None):
        """
        Get qualification data for an entity.
        
        GET /api/{entity}/{id}/qualification/
        """
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
    
    @qualification.mapping.post
    def create_qualification(self, request, pk=None):
        """
        Create qualification signals for an entity.
        
        POST /api/{entity}/{id}/qualification/
        """
        try:
            entity = self.get_objects([pk]).first()
            if not entity:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Data should be a dictionary of field_name -> value pairs
            data = request.data
            
            # Validate the data format
            if not isinstance(data, dict):
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_DATA: "Data should be a dictionary of field_name -> value pairs"
                })
            
            # Create signals for the fields
            from apps.signals.services.signal_creation_service import SignalCreationService
            
            created_signals = SignalCreationService.create_signals_from_dict(
                instance=entity,
                data_dict=data,
                user=request.user,
                source='api'
            )
            
            # Return the created signals
            from apps.signals.serializers import SignalSerializer
            serializer = SignalSerializer(created_signals, many=True)
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return self.handle_exception(e)