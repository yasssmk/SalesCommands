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
        """
        Get one or multiple objects with client scope checking.
        If ids is None, tries to get single object from URL or query params.
        """
        queryset = self.get_queryset()
        
        if not ids:
            # Try to get single ID from URL or query params
            pk = self.kwargs.get('pk') or self.request.query_params.get(f'{self.entity_name}_id')
            if not pk:
                return None
            ids = [pk]

        # Get and validate objects
        objects = queryset.filter(id__in=ids)
        if objects.count() != len(ids):
            missing = set(str(id) for id in ids) - set(str(obj.id) for obj in objects)
            raise ValidationError(f"Items not found: {', '.join(missing)}")
            
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

    def _update(self, request, partial):
        """Handle update requests for single or multiple objects"""
        client_id = self.get_client_id()
        
        try:
            with transaction.atomic():
                # Handle different update request formats
                if isinstance(request.data, list):
                    if all(isinstance(item, (str, uuid.UUID)) for item in request.data):
                        # Handle list of IDs with shared update data
                        ids = request.data
                        update_data = request.query_params.dict()
                    else:
                        # Handle list of objects with individual updates
                        ids = [item.get('id') for item in request.data]
                        if not all(ids):
                            raise ValidationError("All items must have an ID")
                
                    objects = self.get_objects(ids)
                    updated_objects = []
                    
                    for obj in objects:
                        # Get individual update data or use shared data
                        item_data = next(
                            (item for item in request.data if str(item.get('id')) == str(obj.id)),
                            update_data if 'update_data' in locals() else {}
                        )
                        serializer = self._update_instance(obj, item_data, partial, client_id)
                        updated_objects.append(serializer.instance)
                    
                    # Return paginated response if needed
                    if len(updated_objects) > 1 and self.paginator is not None:
                        page = self.paginate_queryset(updated_objects)
                        if page is not None:
                            serializer = self.serializer_class(page, many=True)
                            return self.get_paginated_response(serializer.data)

                    serializer = self.serializer_class(updated_objects, many=True)
                    return Response(serializer.data)
                else:
                    # Single update
                    instance = self.get_objects().first()
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
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        logger.error(f"Error in {self.__class__.__name__}: {str(exc)}", exc_info=True)
            
        return Response(
            {"error": "An unexpected error occurred" if not settings.DEBUG else str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )