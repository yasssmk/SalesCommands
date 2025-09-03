from rest_framework import views, status
from rest_framework.response import Response
from django.db import transaction
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ValidationError as DRFValidationError, PermissionDenied, AuthenticationFailed, NotAuthenticated
from django.core.exceptions import ValidationError as DjangoValidationError, FieldError
from django.shortcuts import get_object_or_404
from django.conf import settings
from core.client_scope import ClientScopeManager
from core.exceptions import (
    StandardizedValidationError,
    StandardizedPermissionDenied,
    StandardizedAuthenticationFailed,
)
from core.error_messages import CoreErrorMessages, AuthErrorMessages
from rest_framework.exceptions import ParseError
import logging

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
    
    # def get_queryset(self):
    #     """Get base queryset with client filtering"""
    #     assert self.queryset is not None, "Define queryset in your view"
    #     queryset = self.queryset.all()
    #     return self.filter_queryset_by_client(queryset)

    def get_queryset(self):
        """
        Get base queryset with client filtering.
        
        IMPORTANT: This method now properly chains with super() to maintain MRO compatibility.
        This allows mixins like ScopedQuerysetMixin to be called in the proper order.
        
        Call chain:
        1. Mixin (e.g., ScopedQuerysetMixin) calls super() → here
        2. We call super() → ModelViewSet.get_queryset() 
        3. ModelViewSet returns self.queryset.all()
        4. We apply client filter via filter_queryset_by_client()
        5. Return filtered queryset back up the chain
        
        This ensures:
        - Client filtering is always applied (security)
        - Mixins can add their own filtering (permissions)
        - No double filtering or broken chains
        """
        # CRITICAL: Call super() to maintain MRO chain
        # This allows ModelViewSet to provide the base queryset
        # and other mixins in the chain to execute properly
        if hasattr(super(), 'get_queryset'):
            queryset = super().get_queryset()
        else:
            # Fallback if no parent provides get_queryset
            assert self.queryset is not None, "Define queryset in your view"
            queryset = self.queryset.all()
        
        # Apply client-scoped filtering (tenant isolation)
        # This is the FIRST security filter that must always be applied
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
                pk = kwargs.get("pk")
                if pk:
                    objects = self.get_objects([pk]).first()
                    if not objects:
                        raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
                else:
                    objects = self.get_queryset()
            
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
            
        except (DjangoValidationError, DRFValidationError) as exc:
            return self.handle_exception(exc)
        except Exception as exc:
            return self.handle_exception(exc)

    def get_objects(self, ids=None):
        """Get one or multiple objects with client scope checking"""
        queryset = self.get_queryset()  # This already applies client filtering
        
        if not ids:
            pk = self.kwargs.get('pk') or self.request.query_params.get(f'{self.entity_name}_id')
            if not pk:
                return queryset.none()
            ids = [pk]

        # Convert all IDs to strings for consistent comparison
        ids = [str(id_).strip() for id_ in ids]
        
        # Get objects - queryset is already client-scoped from get_queryset()
        objects = queryset.filter(id__in=ids)
        
        # If we can't find all requested objects in the client-scoped queryset
        if objects.count() != len(ids):
            raise StandardizedPermissionDenied(CoreErrorMessages.OBJECT_NOT_FOUND)
            
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
                        instance = serializer.save(client_id=client_id, user=request.user)
                        created_objects.append(instance)
                    else:
                        raise StandardizedValidationError(serializer.errors)

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
            raise StandardizedValidationError({
            CoreErrorMessages.MASS_UPDATE_INVALID: list(self.mass_update_allowed_fields)
        })
                
        return allowed_data
    
    def _batch_validate_client_scope(self, objects):
        """Validate client scope for multiple objects"""
        client_id = self.get_client_id()
        invalid_ids = []
        
        for obj in objects:
            try:
                if not hasattr(obj, 'client_id'):
                    raise StandardizedValidationError(CoreErrorMessages.CLIENT_SCOPE_UNSUPPORTED)
                if str(obj.client_id) != str(client_id):
                    invalid_ids.append(str(obj.id))
            except AttributeError:
                invalid_ids.append(str(obj.id))
                
        if invalid_ids:
            raise StandardizedPermissionDenied({
            CoreErrorMessages.CLIENT_MISMATCH: invalid_ids
        })

    def _update(self, request, partial):
        """Enhanced update with better client scope validation."""
        client_id = self.get_client_id()

        try:
            with transaction.atomic():
                # Handle multiple objects update
                id_param = request.query_params.get(f'{self.entity_name}_ids')
                if id_param:
                    ids = [id_.strip() for id_ in id_param.split(',') if id_.strip()]
                    if not ids:
                         raise StandardizedValidationError(CoreErrorMessages.NO_OBJECTS_FOUND)

                    objects = self.get_objects(ids)
                    self._batch_validate_client_scope(objects)

                    updated_objects = []
                    for obj in objects:
                        try:
                            filtered_data = {key: value for key, value in request.data.items()}

                            serializer = self.serializer_class(
                                obj,
                                data=filtered_data,
                                partial=partial,
                                context={'request': request, 'client_id': client_id}
                            )

                            if not serializer.is_valid():
                                raise StandardizedValidationError(serializer.errors)

                            updated = serializer.save(user=request.user)
                            updated_objects.append(updated)
                        
                        except Exception as e:
                            if hasattr(serializer, "errors"):
                                raise StandardizedValidationError(serializer.errors)
                            raise StandardizedValidationError(str(e))

                    serializer = self.serializer_class(updated_objects, many=True)
                    return Response(serializer.data)

                else:
                    # Single object update
                    objects = self.get_objects()
                    if not objects.exists():
                        raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

                    instance = objects.first()
                    self.validate_client_id(instance)

                    filtered_data = {key: value for key, value in request.data.items()}

                    serializer = self.serializer_class(
                        instance,
                        data=filtered_data,
                        partial=partial,
                        context={'request': request, 'client_id': client_id}
                    )

                    if not serializer.is_valid():
                        raise StandardizedValidationError(serializer.errors)

                    updated = serializer.save(user=request.user)
                    return Response(self.serializer_class(updated).data)

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
                    raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
                
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

    # def handle_exception(self, exc):
    #     """Centralized error handling for all API views"""
        
    #     print('MAMA')
    #     if isinstance(exc, ParseError):
    #         formatted_detail = StandardizedValidationError._format_detail(
    #             CoreErrorMessages.INVALID_DATA.format(detail="Malformed JSON in request body")
    #         )
    #         return Response(
    #             formatted_detail,
    #             status=status.HTTP_400_BAD_REQUEST
    #         )
        
    #     if isinstance(exc, AuthenticationFailed):
    #         return Response(
    #             StandardizedValidationError._format_detail(AuthErrorMessages.AUTH_REQUIRED),
    #             status=status.HTTP_401_UNAUTHORIZED
    #         )

    #     if isinstance(exc, PermissionDenied):
    #         return Response(
    #             StandardizedValidationError._format_detail(CoreErrorMessages.PERMISSION_DENIED),
    #             status=status.HTTP_403_FORBIDDEN
    #         )

    #     if isinstance(exc, (DRFValidationError, DjangoValidationError)):
    #         detail = exc.detail if hasattr(exc, 'detail') else exc.message_dict
    #         return Response(
    #             StandardizedValidationError._format_detail(detail),
    #             status=status.HTTP_400_BAD_REQUEST
    #         )

    #     # Log unexpected errors
    #     return Response(
    #         StandardizedValidationError._format_detail(CoreErrorMessages.UNEXPECTED_ERROR),
    #         status=status.HTTP_500_INTERNAL_SERVER_ERROR
    #     )

    def handle_exception(self, exc):
        """Centralized error handling for all API views"""
        
        import traceback
        import sys
        
        # Print a visible header to make the error stand out
        print("\n" + "="*50)
        print("ERROR DETAILS:")
        print("="*50)
        
        # Print the exception type and message
        print(f"Exception Type: {type(exc).__name__}")
        print(f"Exception Message: {str(exc)}")
        
        # Print the full traceback
        print("\nTraceback:")
        traceback.print_exception(type(exc), exc, exc.__traceback__)
        
        # If the exception has a 'detail' attribute, print it
        if hasattr(exc, 'detail'):
            print(f"\nException Details: {exc.detail}")
        
        # Additional debugging for certain types of errors
        if isinstance(exc, StandardizedValidationError):
            print(f"\nStandardizedValidationError Details: {exc.detail}")
        
        print("="*50 + "\n")

        from django.http import Http404
        if isinstance(exc, Http404):
            return Response(
                StandardizedValidationError._format_detail(CoreErrorMessages.OBJECT_NOT_FOUND),
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Regular exception handling
        if isinstance(exc, ParseError):
            formatted_detail = StandardizedValidationError._format_detail(
                CoreErrorMessages.INVALID_DATA.format(detail="Malformed JSON in request body")
            )
            return Response(
                formatted_detail,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if isinstance(exc, AuthenticationFailed):
            return Response(
                StandardizedValidationError._format_detail(AuthErrorMessages.INVALID_CREDENTIALS),
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if isinstance(exc, NotAuthenticated):
            return Response(
                StandardizedValidationError._format_detail(AuthErrorMessages.AUTH_REQUIRED),
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if isinstance(exc, FieldError):
            detail = str(exc)  # FieldError n'a qu'un message string
            return Response(
                StandardizedValidationError._format_detail(
                    CoreErrorMessages.INVALID_FIELD.format(field=detail)
                ),
                status=status.HTTP_400_BAD_REQUEST
            )


        if isinstance(exc, PermissionDenied):
            return Response(
                StandardizedValidationError._format_detail(CoreErrorMessages.PERMISSION_DENIED),
                status=status.HTTP_403_FORBIDDEN
            )

        if isinstance(exc, (DRFValidationError, DjangoValidationError)):
            detail = exc.detail if hasattr(exc, 'detail') else exc.message_dict
            return Response(
                StandardizedValidationError._format_detail(detail),
                status=status.HTTP_400_BAD_REQUEST
            )

        # Log unexpected errors with formatted traceback
        error_traceback = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        formatted_error = f"{type(exc).__name__}: {str(exc)}\n{error_traceback}"
        
        return Response(
            StandardizedValidationError._format_detail(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=str(exc))
            ),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )