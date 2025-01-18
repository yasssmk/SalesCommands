# core/views.py
from rest_framework import views, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
import logging
from .apps_auth_mixins import ClientAuthMixin

logger = logging.getLogger(__name__)

class BaseAPIView(ClientAuthMixin, views.APIView):
    """
    Base API View with common CRUD operations and utility methods.
    """
    queryset = None
    serializer_class = None
    entity_name = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert self.entity_name is not None, (
            f"{self.__class__.__name__} should include an entity_name attribute "
            "or override get_entity_name()"
        )

    def get_queryset(self):
        """
        Get the base queryset with entity-specific ID filtering.
        """
        assert self.queryset is not None, "Define queryset in your view"
        
        # Start with a fresh queryset
        queryset = self.queryset.all()
        
        # Get IDs using entity-specific parameter name
        id_param = f"{self.entity_name}_ids"
        entity_ids = self.request.query_params.getlist(id_param, [])
        
        if entity_ids:
            queryset = queryset.filter(id__in=entity_ids)
        
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
        Get single object based on ID.
        """
        queryset = self.get_queryset()
        obj = get_object_or_404(queryset, pk=self.kwargs.get('pk'))
        self.check_object_permissions(self.request, obj)
        return obj
    
    def handle_exception(self, exc):
        """
        Global exception handler with logging.
        """
        logger.error(f"Exception in {self.__class__.__name__}: {str(exc)}", exc_info=True)
        return Response({
            "status": "error",
            "message": "An unexpected error occurred",
            "error": str(exc)
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
            serializer = self.serializer_class(queryset, many=True)
            return Response(serializer.data)
        except Exception as exc:
            return self.handle_exception(exc)

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests for creating new objects.
        """
        try:
            serializer = self.serializer_class(data=request.data)
            if serializer.is_valid():
                with transaction.atomic():
                    instance = self.perform_create(serializer)
                return Response(
                    self.serializer_class(instance).data,
                    status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return self.handle_exception(exc)

    def put(self, request, pk=None, *args, **kwargs):
        """
        Handle PUT requests for full updates.
        """
        try:
            instance = self.get_object()
            serializer = self.serializer_class(instance, data=request.data)
            if serializer.is_valid():
                with transaction.atomic():
                    updated_instance = self.perform_update(serializer)
                return Response(self.serializer_class(updated_instance).data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return self.handle_exception(exc)

    def patch(self, request, pk=None, *args, **kwargs):
        """
        Handle PATCH requests for partial updates.
        """
        try:
            instance = self.get_object()
            serializer = self.serializer_class(
                instance, data=request.data, partial=True
            )
            if serializer.is_valid():
                with transaction.atomic():
                    updated_instance = self.perform_update(serializer)
                return Response(self.serializer_class(updated_instance).data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return self.handle_exception(exc)

    def delete(self, request, pk=None, *args, **kwargs):
        """
        Handle DELETE requests.
        """
        try:
            instance = self.get_object()
            with transaction.atomic():
                self.perform_delete(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as exc:
            return self.handle_exception(exc)

    def perform_create(self, serializer):
        """
        Perform object creation. Override for custom behavior.
        """
        client_id = self.get_client_id()
        return serializer.save(client_id=client_id)

    def perform_update(self, serializer):
        """
        Perform object update. Override for custom behavior.
        """
        instance = serializer.save()
        self.check_object_permissions(self.request, instance)
        return instance

    def perform_delete(self, instance):
        """
        Perform object deletion. Override for custom behavior.
        """
        self.check_object_permissions(self.request, instance)
        instance.delete()