from rest_framework import views, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework.exceptions import PermissionDenied
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

    def get_objects(self, ids=None):
        """Get one or multiple objects with client scope checking"""
        queryset = self.get_queryset()
        
        if not ids:
            pk = self.kwargs.get('pk') or self.request.query_params.get(f'{self.entity_name}_id')
            if not pk:
                return None
            ids = [pk]

        # Validate UUIDs
        valid_ids = []
        invalid_ids = []
        for id_ in ids:
            try:
                valid_ids.append(uuid.UUID(str(id_)))
            except ValueError:
                invalid_ids.append(id_)

        if invalid_ids:
            raise ValidationError({
                'ids': CoreErrorMessages.INVALID_UUID,
                'invalid_values': invalid_ids
            })

        # Get and validate objects
        objects = queryset.filter(id__in=valid_ids)
        if objects.count() != len(valid_ids):
            missing = set(str(id_) for id_ in valid_ids) - set(str(obj.id) for obj in objects)
            raise ValidationError({
                'error': CoreErrorMessages.OBJECT_NOT_FOUND,
                'missing_ids': list(missing)
            })
            
        return objects

    def get(self, request, *args, **kwargs):
        """Handle GET requests for single or multiple objects"""
        try:
            # Check for specific IDs
            id_param = request.query_params.get(f'{self.entity_name}_ids')
            ids = [id.strip() for id in id_param.split(',')] if id_param else None
            
            # Get objects
            objects = self.get_objects(ids)
            if not objects:
                # No specific IDs requested, return full list
                objects = self.get_queryset()
            
            # Determine if we need pagination
            many = bool(id_param or not self.kwargs.get('pk'))
            if many and self.paginator is not None:
                page = self.paginate_queryset(objects)
                if page is not None:
                    serializer = self.serializer_class(page, many=True)
                    return self.get_paginated_response(serializer.data)

            # If no pagination needed or single object request
            serializer = self.serializer_class(objects, many=many)
            return Response(serializer.data)
            
        except Exception as exc:
            return self.handle_exception(exc)

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

    def _update(self, request, partial):
        """Handle update requests with improved validation"""
        client_id = self.get_client_id()
        
        try:
            with transaction.atomic():
                if isinstance(request.data, list):
                    # Handle batch updates
                    if all(isinstance(item, (str, uuid.UUID)) for item in request.data):
                        # Mass update with filtered fields
                        ids = request.data
                        update_data = self._get_filtered_update_data(request.query_params)
                    else:
                        # Individual updates
                        ids = [item.get('id') for item in request.data]
                        if not all(ids):
                            raise ValidationError({
                                'error': CoreErrorMessages.BATCH_UPDATE_MISSING_ID
                            })
                
                    objects = self.get_objects(ids)
                    updated_objects = []
                    
                    for obj in objects:
                        item_data = next(
                            (item for item in request.data if str(item.get('id')) == str(obj.id)),
                            update_data if 'update_data' in locals() else {}
                        )
                        serializer = self._update_instance(obj, item_data, partial, client_id)
                        updated_objects.append(serializer.instance)
                        
                    serializer = self.serializer_class(updated_objects, many=True)
                    return Response(serializer.data)
                else:
                    # Single update
                    instance = self.get_objects().first()
                    if not instance:
                        raise ValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
                    serializer = self._update_instance(instance, request.data, partial, client_id)
                    return Response(serializer.data)
                    
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
        """Standardized error handling"""
        if isinstance(exc, ValidationError):
            return Response(
                exc.detail if hasattr(exc, 'detail') else {'error': str(exc)},
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