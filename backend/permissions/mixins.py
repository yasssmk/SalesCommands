"""
DRF Mixins for Permission System

This module provides Django REST Framework integration:
- ScopedPermission: DRF permission class for access control
- ScopedQuerysetMixin: Automatic queryset filtering by scope

Usage in views:
    class AccountViewSet(ScopedQuerysetMixin, viewsets.ModelViewSet):
        permission_classes = [IsAuthenticated, ScopedPermission]
        module = 'accounts'  # Required
        queryset = Account.objects.all()
"""

from typing import Optional
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView
from django.db.models import QuerySet

from .checks import check_permission, has_permission
from .scoping import apply_scope_filter, build_q
from .config import is_module_enabled, is_enabled, is_debug_enabled, audit_log


class ScopedPermission(permissions.BasePermission):
    """
    DRF Permission class that checks permissions using our registry.
    
    Requires the view to have a 'module' attribute defining which
    module it belongs to.
    
    Example:
        class AccountViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticated, ScopedPermission]
            module = 'accounts'  # Required!
    """
    
    def has_permission(self, request: Request, view: APIView) -> bool:
        """
        Check if user has permission to perform the action.
        
        This is called before accessing any specific object.
        
        Args:
            request: DRF Request
            view: View being accessed
            
        Returns:
            True if permission granted, False otherwise
        """
        # Skip if permissions system is disabled
        if not is_enabled():
            return True
        
        # Get module from view
        module = getattr(view, 'module', None)
        if not module:
            # If no module specified, check if we should default to allow or deny
            # For safety, we deny by default if module is not specified
            return False
        
        # Skip if module is not enabled
        if not is_module_enabled(module):
            return True
        
        # Get the DRF action
        action = self._get_action(view)
        if not action:
            return False
        
        # Check permission
        return has_permission(request.user, module, action)
    
    def has_object_permission(self, request: Request, view: APIView, obj) -> bool:
        """
        Check object-level permission.
        
        This is called after has_permission() for retrieve/update/destroy.
        
        Args:
            request: DRF Request
            view: View being accessed
            obj: Model instance being accessed
            
        Returns:
            True if permission granted, False otherwise
        """
        # Skip if permissions system is disabled
        if not is_enabled():
            return True
        
        # Get module from view
        module = getattr(view, 'module', None)
        if not module:
            return False
        
        # Skip if module is not enabled
        if not is_module_enabled(module):
            return True
        
        # Get the DRF action
        action = self._get_action(view)
        if not action:
            return False
        
        # Get user's scope
        scope = check_permission(request.user, module, action)
        
        # Deny if no permission
        if scope == 'none':
            return False
        
        # Allow if client-level access
        if scope == 'client':
            return True
        
        # For team/mine scopes, we need to check ownership
        # This is a simplified check - the real filtering happens in queryset
        # Here we just ensure the object would be in the filtered queryset
        
        # Build the Q filter for this scope
        q_filter = build_q(module, scope, request.user, action)
        
        # Check if this object matches the filter
        # We need to get the model class and check
        model_class = obj.__class__
        matches = model_class.objects.filter(q_filter, pk=obj.pk).exists()
        
        return matches
    
    def _get_action(self, view: APIView) -> Optional[str]:
        """
        Get the current DRF action from the view.
        
        Args:
            view: DRF view
            
        Returns:
            Action name or None
        """
        # For ViewSets, use the action attribute
        if hasattr(view, 'action'):
            return view.action
        
        # For APIView, map HTTP method to action
        if hasattr(view, 'request'):
            method_map = {
                'GET': 'read',
                'POST': 'create',
                'PUT': 'update',
                'PATCH': 'update',  # PATCH = UPDATE
                'DELETE': 'delete',
            }
            return method_map.get(view.request.method)
        
        return None


class ScopedQuerysetMixin:
    """
    Mixin that automatically filters querysets based on permissions.
    
    Add this to your ViewSet before the base class:
    
        class AccountViewSet(ScopedQuerysetMixin, viewsets.ModelViewSet):
            module = 'accounts'  # Required!
            queryset = Account.objects.all()
    
    This mixin will automatically filter the queryset in get_queryset()
    based on the user's permission scope.
    """
    
    # Module name must be set on the view
    module: Optional[str] = None
    
    def get_queryset(self) -> QuerySet:
        """
        Filter queryset based on user's permission scope.
        
        This method is called by DRF to get the base queryset.
        We filter it based on the user's permissions.
        
        Returns:
            Filtered queryset
        """
        # Get base queryset from parent
        queryset = super().get_queryset()
        
        # Skip if permissions system is disabled
        if not is_enabled():
            return queryset
        
        # Get module
        module = getattr(self, 'module', None)
        if not module:
            # No module specified - return empty queryset for safety
            return queryset.none()
        
        # Skip if module is not enabled
        if not is_module_enabled(module):
            return queryset
        
        # Get action for this request
        action = self._get_current_action()
        
        # Get user from request
        user = self.request.user if hasattr(self, 'request') else None
        if not user:
            return queryset.none()
        
        # Apply scope filter
        filtered_queryset = apply_scope_filter(
            queryset,
            module,
            action,
            user
        )
        
        return filtered_queryset
    
    def _get_current_action(self) -> str:
        """
        Get the current action being performed.
        
        Returns:
            Action name (defaults to 'read' for safety)
        """
        # For ViewSets, use the action attribute
        if hasattr(self, 'action'):
            return self.action
        
        # For APIView, check request method
        if hasattr(self, 'request'):
            method_map = {
                'GET': 'read',
                'POST': 'create',
                'PUT': 'update',
                'PATCH': 'update',  # PATCH = UPDATE
                'DELETE': 'delete',
            }
            return method_map.get(self.request.method, 'read')
        
        # Default to read (most restrictive for queries)
        return 'read'


class PermissionDebugMixin:
    """
    Debug mixin to help understand permission decisions.
    
    Add this to your view to get detailed permission info in responses:
    
        class AccountViewSet(PermissionDebugMixin, ScopedQuerysetMixin, viewsets.ModelViewSet):
            module = 'accounts'
            debug_permissions = True  # Enable debug info
    """
    
    # Set to True to include debug info in responses
    debug_permissions: bool = False
    
    def finalize_response(self, request, response, *args, **kwargs):
        """
        Add permission debug info to response headers.
        
        Args:
            request: DRF Request
            response: DRF Response
            
        Returns:
            Response with debug headers
        """
        response = super().finalize_response(request, response, *args, **kwargs)
        
        # Only add debug info if enabled and in DEBUG mode
        if self.debug_permissions and hasattr(request, 'user'):
            from django.conf import settings
            if settings.DEBUG:
                from .checks import resolve_tier, get_scope
                
                module = getattr(self, 'module', 'unknown')
                action = getattr(self, 'action', 'unknown')
                
                # Add debug headers
                response['X-Permission-Module'] = module
                response['X-Permission-Action'] = action
                response['X-Permission-Tier'] = resolve_tier(request.user)
                response['X-Permission-Scope'] = get_scope(module, action, resolve_tier(request.user))
                response['X-Permission-User'] = str(request.user.id) if request.user.is_authenticated else 'anonymous'
        
        return response


class BulkPermissionMixin:
    """
    Mixin for handling bulk operations with permissions.
    
    Ensures that bulk operations respect permissions for each object.
    
    Example:
        class AccountViewSet(BulkPermissionMixin, viewsets.ModelViewSet):
            module = 'accounts'
    """
    
    def get_serializer(self, *args, **kwargs):
        """
        Override to handle bulk operations with permission checks.
        
        Returns:
            Serializer instance
        """
        # Check if this is a bulk operation
        if isinstance(kwargs.get('data', {}), list):
            # For bulk operations, we need to check each item
            # This is handled in the perform_bulk_create/update methods
            pass
        
        return super().get_serializer(*args, **kwargs)
    
    def perform_bulk_create(self, serializer):
        """
        Perform bulk creation with permission checks.
        
        Args:
            serializer: Serializer with validated data
        """
        # Check create permission
        module = getattr(self, 'module', None)
        if module and not has_permission(self.request.user, module, 'create'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You don't have permission to create in this module")
        
        # Perform creation
        serializer.save()
    
    def perform_bulk_update(self, serializer):
        """
        Perform bulk update with permission checks.
        
        Args:
            serializer: Serializer with validated data
        """
        # For bulk updates, we need to check each object
        module = getattr(self, 'module', None)
        if not module:
            return super().perform_update(serializer)
        
        # Get the scope for updates
        scope = check_permission(self.request.user, module, 'update')
        if scope == 'none':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You don't have permission to update in this module")
        
        # For team/mine scopes, verify each object
        if scope in ['team', 'mine']:
            # Build filter for accessible objects
            q_filter = build_q(module, scope, self.request.user, 'update')
            
            # Check each instance
            for instance in serializer.instance:
                if not instance.__class__.objects.filter(q_filter, pk=instance.pk).exists():
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied(f"You don't have permission to update object {instance.pk}")
        
        # Perform update
        serializer.save()


# Compatibility aliases for easier migration
ScopePermission = ScopedPermission  # Alias
QuerysetScopeMixin = ScopedQuerysetMixin  # Alias