from rest_framework import views, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
import logging
from .client_scope import ClientScopeManager
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from uuid import UUID

logger = logging.getLogger(__name__)

class BaseAPIView(ClientScopeManager.ViewMixin, views.APIView):
    """
    Base API View with common CRUD operations and utility methods.
    Handles client scoping and permissions.
    """
    queryset = None
    serializer_class = None
    entity_name = None
    # max_batch_size = 100  # Maximum number of items in batch operations

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert self.entity_name is not None, (
            f"{self.__class__.__name__} should include an entity_name attribute "
            "or override get_entity_name()"
        )

    def get_queryset(self):
        """
        Get the base queryset with entity-specific ID filtering and client filtering.
        """
        assert self.queryset is not None, "Define queryset in your view"
        
        # Start with base queryset
        queryset = self.queryset.all()
        
        # Apply client filtering first - this is crucial for security
        queryset = self.filter_queryset_by_client(queryset)
        
        id_param = f"{self.entity_name}_ids"
        raw_ids = self.request.query_params.get(id_param, [])

        if raw_ids:
            try:
                # Convert to a list of integers
                ids = [int(id) for id in raw_ids if id.isdigit()]
                queryset = queryset.filter(id__in=ids)
            except ValueError:
                raise ValidationError(_("Invalid ID format. Must be a valid integer list."))
        
        # Handle related entity filtering if present
        related_filters = self.get_related_filters()
        if related_filters:
            queryset = queryset.filter(**related_filters)
        
        return queryset
    
    def get_related_filters(self):
        """
        Get filters for related entities.
        Override in child classes to add specific relation filtering.
        """
        return {}
    
    def get_object(self):
        """
        Get single object based on ID with proper client scope checking.
        """
        queryset = self.get_queryset()
        obj = get_object_or_404(queryset, pk=self.kwargs.get('pk'))
        return obj
    
    def get_objects_by_ids(self, ids):
        """Get multiple objects with client scope checking."""
        queryset = self.get_queryset()
        # # Ensure ids list isn't too large to prevent performance issues
        # if len(ids) > 100:  # You can adjust this limit
        #     raise ValidationError(_("Too many items requested. Maximum is 100."))
            
        objects = queryset.filter(id__in=ids)
        print(f"Batch operation - Found {objects.count()} objects for client {self.get_client_id()}")
        
        # Verify we found all requested objects
        if objects.count() != len(ids):
            raise ValidationError(_("Some requested items were not found."))
            
        return objects

    def handle_exception(self, exc):
        """Enhanced error handling with detailed messages"""
        print(f"Exception in {self.__class__.__name__}: {str(exc)}")
        
        if settings.DEBUG:
            error_detail = str(exc)
        else:
            error_detail = "An unexpected error occurred"
            
        return Response({
            "status": "error",
            "message": error_detail
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

    def get(self, request, pk=None, *args, **kwargs):
        """
        Handle GET requests - list or detail.
        """
        try:
            if pk:
                instance = self.get_object()
                serializer = self.serializer_class(instance)
                return Response(serializer.data)
            
            queryset = self.get_queryset()
        
            # Handle ID filtering
            id_param = request.query_params.get(f'{self.entity_name}_ids')
            if id_param:
                # Split comma-separated string and convert to list
                ids = [id.strip() for id in id_param.split(',')]
                try:
                    queryset = self.get_objects_by_ids(ids)
                except ValidationError as e:
                    return Response(
                        {"error": str(e)},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            serializer = self.serializer_class(queryset, many=True)
            return Response(serializer.data)
        except Exception as exc:
            return self.handle_exception(exc)

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests:
        - Single item creation
        - Batch creation for list of items
        """
        is_batch = isinstance(request.data, list)
        
        if is_batch:
            # if len(request.data) > self.max_batch_size:
            #     raise ValidationError(_(f"Too many items. Maximum is {self.max_batch_size}."))
                
            created_instances = []
            with transaction.atomic():
                for item in request.data:
                    serializer = self.serializer_class(
                        data=item,
                        context={'request': request}
                    )
                    if serializer.is_valid():
                        instance = self.perform_create(serializer)
                        created_instances.append(instance)
                    else:
                        raise ValidationError(serializer.errors)
                        
            return Response(
                self.serializer_class(created_instances, many=True).data,
                status=status.HTTP_201_CREATED
            )
        else:
            serializer = self.serializer_class(
                data=request.data,
                context={'request': request}
            )
            if serializer.is_valid():
                instance = self.perform_create(serializer)
                return Response(
                    self.serializer_class(instance).data,
                    status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk=None, *args, **kwargs):
        """
        Handle PUT requests:
        - Single item update if pk provided
        - Batch update if data is list of items with IDs
        """
        is_batch = isinstance(request.data, list)
        
        if is_batch:
            # if len(request.data) > self.max_batch_size:
            #     raise ValidationError(_(f"Too many items. Maximum is {self.max_batch_size}."))
                
            ids = [item.get('id') for item in request.data]
            if not all(ids):
                raise ValidationError(_("All items must have an ID"))
                
            objects = self.get_objects_by_ids(ids)
            updated_instances = []
            
            with transaction.atomic():
                for item in request.data:
                    instance = next(
                        (obj for obj in objects if str(obj.id) == str(item.get('id'))),
                        None
                    )
                    serializer = self.serializer_class(
                        instance,
                        data=item,
                        context={'request': request}
                    )
                    if serializer.is_valid():
                        updated = self.perform_update(serializer)
                        updated_instances.append(updated)
                    else:
                        raise ValidationError(serializer.errors)
                        
            return Response(self.serializer_class(updated_instances, many=True).data)
        else:
            instance = self.get_object(pk)
            serializer = self.serializer_class(
                instance,
                data=request.data,
                context={'request': request}
            )
            if serializer.is_valid():
                updated = self.perform_update(serializer)
                return Response(self.serializer_class(updated).data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk=None, *args, **kwargs):
        """
        Handle PATCH requests:
        - Single item partial update if pk provided
        - Batch partial update if data is list of items with IDs
        """
        is_batch = isinstance(request.data, list)
        
        if is_batch:
            # if len(request.data) > self.max_batch_size:
            #     raise ValidationError(_(f"Too many items. Maximum is {self.max_batch_size}."))
                
            ids = [item.get('id') for item in request.data]
            if not all(ids):
                raise ValidationError(_("All items must have an ID"))
                
            objects = self.get_objects_by_ids(ids)
            updated_instances = []
            
            with transaction.atomic():
                for item in request.data:
                    instance = next(
                        (obj for obj in objects if str(obj.id) == str(item.get('id'))),
                        None
                    )
                    serializer = self.serializer_class(
                        instance,
                        data=item,
                        partial=True,
                        context={'request': request}
                    )
                    if serializer.is_valid():
                        updated = self.perform_update(serializer)
                        updated_instances.append(updated)
                    else:
                        raise ValidationError(serializer.errors)
                        
            return Response(self.serializer_class(updated_instances, many=True).data)
        else:
            instance = self.get_object(pk)
            serializer = self.serializer_class(
                instance,
                data=request.data,
                partial=True,
                context={'request': request}
            )
            if serializer.is_valid():
                updated = self.perform_update(serializer)
                return Response(self.serializer_class(updated).data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None, *args, **kwargs):
        """
        Handle DELETE requests:
        - Single item deletion if pk provided
        - Batch deletion if list of IDs provided in request data
        """
        is_batch = isinstance(request.data, list)
        
        if is_batch:
            # if len(request.data) > self.max_batch_size:
            #     raise ValidationError(_(f"Too many items. Maximum is {self.max_batch_size}."))
                
            objects = self.get_objects_by_ids(request.data)
            
            with transaction.atomic():
                deleted_count = 0
                for obj in objects:
                    self.perform_delete(obj)
                    deleted_count += 1
                    
            return Response({
                "message": f"Successfully deleted {deleted_count} items",
                "count": deleted_count
            }, status=status.HTTP_200_OK)
        else:
            instance = self.get_object(pk)
            self.perform_delete(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_update(self, serializer):
        """
        Perform object update with client scope check.
        """
        client_id = self.get_client_id()
        print(f"Updating with client_id: {client_id}")
        
        instance = serializer.save(client_id=client_id)  # Add client_id here
        return instance 

    def perform_delete(self, instance):
        """
        Perform object deletion with client scope check.
        """
        instance.delete()