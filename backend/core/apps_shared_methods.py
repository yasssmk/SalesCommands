from rest_framework import views, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from django.core.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
import logging
from .client_scope import ClientScopeManager
from django.utils.translation import gettext_lazy as _
from django.conf import settings
import uuid
from core.error_messages import CoreErrorMessages

logger = logging.getLogger(__name__)

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class BaseAPIView(ClientScopeManager.ViewMixin, views.APIView):
    """
    Base API View with simplified CRUD operations that handle both single and batch operations.
    """
    queryset = None
    serializer_class = None
    entity_name = None
    pagination_class = StandardResultsSetPagination
    mass_update_allowed_fields = set()

    @property
    def paginator(self):
        """
        The paginator instance associated with the view, or `None`.
        """
        if not hasattr(self, '_paginator'):
            if self.pagination_class is None:
                self._paginator = None
            else:
                self._paginator = self.pagination_class()
        return self._paginator

    def paginate_queryset(self, queryset):
        """
        Return a single page of results, or `None` if pagination is disabled.
        """
        if self.paginator is None:
            return None
        return self.paginator.paginate_queryset(queryset, self.request, view=self)

    def get_paginated_response(self, data):
        """
        Return a paginated style `Response` object.
        """
        assert self.paginator is not None
        return self.paginator.get_paginated_response(data)
    
    def get_queryset(self):
        """Get base queryset with client filtering"""
        assert self.queryset is not None, "Define queryset in your view"
        queryset = self.queryset.all()
        return self.filter_queryset_by_client(queryset)

    def get(self, request, *args, **kwargs):
        """Handle GET requests for single or multiple objects"""
        try:
            # Check for specific IDs
            id_param = request.query_params.get(f'{self.entity_name}_ids')
            if id_param:
                # Split and clean IDs
                ids = [id_.strip() for id_ in id_param.split(',') if id_.strip()]
                if not ids:
                    return Response([], status=status.HTTP_200_OK)
                
                # Get objects with the specified IDs
                objects = self.get_objects(ids)
            else:
                # Handle single object request if pk is in URL
                pk = kwargs.get('pk')
                if pk:
                    objects = self.get_objects([pk])
                else:
                    # No specific IDs requested, return full list
                    objects = self.get_queryset()
            
            if kwargs.get('pk'):
                objects = objects.first()
                if not objects:
                    return Response(
                        {'error': CoreErrorMessages.OBJECT_NOT_FOUND},
                        status=status.HTTP_404_NOT_FOUND
                    )
            
            # Determine if we need pagination
            many = bool(id_param or not kwargs.get('pk'))
            if many and self.paginator is not None:
                page = self.paginate_queryset(objects)
                if page is not None:
                    serializer = self.serializer_class(page, many=True)
                    return self.get_paginated_response(serializer.data)

            # If no pagination needed or single object request
            serializer = self.serializer_class(objects, many=many)
            return Response(serializer.data)
            
        except ValidationError as exc:
            return Response(
                {'error': str(exc.detail)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as exc:
            return self.handle_exception(exc)

    def get_objects(self, ids=None):
        """Get one or multiple objects with client scope checking"""
        queryset = self.get_queryset()
        
        if not ids:
            pk = self.kwargs.get('pk') or self.request.query_params.get(f'{self.entity_name}_id')
            if not pk:
                return queryset.none()
            ids = [pk]

        # Convert all IDs to strings for consistent comparison
        ids = [str(id_).strip() for id_ in ids]
        
        # Get and validate objects
        objects = queryset.filter(id__in=ids)
        if objects.count() != len(ids):
            raise ValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
        return objects
    

    def post(self, request, *args, **kwargs):
        """Handle POST requests for single or batch creation"""
        client_id = self.get_client_id()
        data = request.data if isinstance(request.data, list) else [request.data]
        
        created_objects = []
        try:
            with transaction.atomic():
                for item in data:
                    serializer = self.serializer_class(
                        data=item,
                        context={'request': request, 'client_id': client_id}
                    )
                    if serializer.is_valid():
                        instance = serializer.save(client_id=client_id)
                        created_objects.append(instance)
                    else:
                        raise ValidationError(f"Invalid data: {serializer.errors}")

            # Return paginated response for batch creations if needed
            if len(created_objects) > 1 and self.paginator is not None:
                page = self.paginate_queryset(created_objects)
                if page is not None:
                    serializer = self.serializer_class(page, many=True)
                    return self.get_paginated_response(serializer.data)

            serializer = self.serializer_class(created_objects, many=True)
            return Response(
                serializer.data if len(created_objects) > 1 else serializer.data[0],
                status=status.HTTP_201_CREATED
            )
        except Exception as exc:
            return self.handle_exception(exc)

    def put(self, request, *args, **kwargs):
        """Handle PUT requests"""
        return self._update(request, False)

    def patch(self, request, *args, **kwargs):
        """Handle PATCH requests"""
        return self._update(request, True)

    def _get_filtered_update_data(self, query_params):
        """Filter update data to only allow specific fields"""
        allowed_data = {}
        update_data = query_params.dict()
        
        for field in self.mass_update_allowed_fields:
            if field in update_data:
                allowed_data[field] = update_data[field]
                
        if not allowed_data:
            raise ValidationError({
                'error': CoreErrorMessages.MASS_UPDATE_INVALID,
                'allowed_fields': list(self.mass_update_allowed_fields)
            })
                
        return allowed_data
    
    def _batch_validate_client_scope(self, objects):
        """Validate client scope for multiple objects"""
        client_id = self.get_client_id()
        invalid_ids = []
        
        for obj in objects:
            try:
                if not hasattr(obj, 'client_id'):
                    raise ValidationError(CoreErrorMessages.CLIENT_SCOPE_UNSUPPORTED)
                if str(obj.client_id) != str(client_id):
                    invalid_ids.append(str(obj.id))
            except AttributeError:
                invalid_ids.append(str(obj.id))
                
        if invalid_ids:
            raise PermissionDenied({
                'error': CoreErrorMessages.CLIENT_MISMATCH,
                'invalid_ids': invalid_ids
            })

    def _update(self, request, partial):
        """Enhanced update with better client scope validation"""
        client_id = self.get_client_id()
        
        try:
            with transaction.atomic():
                # Handle multiple objects update
                id_param = request.query_params.get(f'{self.entity_name}_ids')
                if id_param:
                    # Split and clean IDs
                    ids = [id_.strip() for id_ in id_param.split(',') if id_.strip()]
                    if not ids:
                        raise ValidationError("No valid IDs provided")

                    # Get all objects at once
                    objects = self.get_objects(ids)
                    
                    # Validate client scope for all objects
                    self._batch_validate_client_scope(objects)
                    
                    # Use request.data as shared update data for all objects
                    update_data = request.data
                    
                    updated_objects = []
                    for obj in objects:
                        try:
                            serializer = self.serializer_class(
                                obj,
                                data=update_data,
                                partial=partial,
                                context={'request': request, 'client_id': client_id}
                            )
                            if serializer.is_valid():
                                updated = serializer.save()
                                updated_objects.append(updated)
                            else:
                                raise ValidationError(serializer.errors)
                        except Exception as e:
                            return self.handle_exception(e)
                    
                    serializer = self.serializer_class(updated_objects, many=True)
                    return Response(serializer.data)
                    
                else:
                    # Single object update
                    objects = self.get_objects()
                    if not objects.exists():
                        return Response(
                            {'error': CoreErrorMessages.OBJECT_NOT_FOUND},
                            status=status.HTTP_404_NOT_FOUND
                        )

                    instance = objects.first()
                    self.validate_client_id(instance)
                    
                    try:
                        serializer = self.serializer_class(
                            instance,
                            data=request.data,
                            partial=partial,
                            context={'request': request, 'client_id': client_id}
                        )
                        if serializer.is_valid():
                            updated = serializer.save()
                            return Response(self.serializer_class(updated).data)
                        else:
                            raise ValidationError(serializer.errors)
                    except Exception as e:
                        return self.handle_exception(e)
                    
        except Exception as exc:
            return self.handle_exception(exc)
                           

    def delete(self, request, *args, **kwargs):
        """Handle DELETE requests for single or multiple objects"""
        try:
            with transaction.atomic():
                # Handle different delete request formats
                if isinstance(request.data, list):
                    ids = request.data
                else:
                    # Try to get IDs from query params
                    id_param = request.query_params.get(f'{self.entity_name}_ids')
                    ids = [id.strip() for id in id_param.split(',')] if id_param else None
                
                # Get and validate objects
                objects = self.get_objects(ids)
                if not objects:
                    raise ValidationError("No objects found to delete")
                
                # Validate and delete each object
                deleted_count = 0
                failed_ids = []
                
                for obj in objects:
                    try:
                        self.validate_client_id(obj)
                        obj.delete()
                        deleted_count += 1
                    except Exception as e:
                        failed_ids.append(str(obj.id))
                
                response_data = {
                    "message": f"Successfully deleted {deleted_count} items",
                    "count": deleted_count
                }
                
                if failed_ids:
                    response_data["failed_ids"] = failed_ids
                    return Response(response_data, status=status.HTTP_207_MULTI_STATUS)
                
                return Response(response_data if deleted_count > 1 else None, 
                              status=status.HTTP_204_NO_CONTENT)
                
        except Exception as exc:
            return self.handle_exception(exc)

    def handle_exception(self, exc):
        """Improved error handling with consistent format"""
        if isinstance(exc, (ValidationError, DRFValidationError)):
            # Get the error detail, handling both DRF and Django validation errors
            if hasattr(exc, 'detail'):
                error_detail = exc.detail
            else:
                error_detail = exc.message if hasattr(exc, 'message') else exc.args[0]

            # Format the error response consistently
            if isinstance(error_detail, dict):
                response_data = {'error': error_detail}
            elif isinstance(error_detail, list):
                response_data = {'error': error_detail[0] if error_detail else str(exc)}
            else:
                response_data = {'error': str(error_detail)}

            return Response(
                response_data,
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if isinstance(exc, PermissionDenied):
            return Response(
                {'error': CoreErrorMessages.PERMISSION_DENIED},
                status=status.HTTP_403_FORBIDDEN
            )
            
        logger.error(f"Error in {self.__class__.__name__}: {str(exc)}", exc_info=True)
        return Response(
            {'error': CoreErrorMessages.UNEXPECTED_ERROR},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )