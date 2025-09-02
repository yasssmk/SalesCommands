"""
DRF Mixins for Permission System

This module provides Django REST Framework integration:
- ScopedPermission: DRF permission class for access control
- ScopedQuerysetMixin: Automatic queryset filtering by scope
"""

from typing import Optional, Set
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView
from django.db.models import QuerySet

from .checks import check_permission, has_permission as check_has_permission, resolve_tier
from .scoping import apply_scope_filter, build_q
from .config import is_module_enabled, is_enabled, is_debug_enabled, audit_log


class ScopedPermission(permissions.BasePermission):
    """
    DRF Permission class that checks permissions using our registry.
    
    Requires the view to have a 'module' attribute defining which
    module it belongs to.
    
    Supports bypassed actions via 'bypassed_actions' attribute on the view.
    Actions listed in bypassed_actions will skip permission checks and
    must implement their own permission logic.
    
    Example:
        class AccountViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticated, ScopedPermission]
            module = 'accounts'  # Required!
            
            # Optional: actions that bypass the permission system
            bypassed_actions = {'custom_action', 'special_operation'}
            
            @action(detail=True, methods=['post'])
            def custom_action(self, request, pk=None):
                # This action handles its own permissions
                if not request.user.is_staff:
                    raise PermissionDenied("Staff only")
                # ... action logic ...
    """
    
    def has_permission(self, request: Request, view: APIView) -> bool:
        """
        Check if the user has permission to perform the action.
        
        Args:
            request: DRF Request
            view: View being accessed
            
        Returns:
            True if permission granted, False otherwise
        """
        # Get user
        user = request.user
        if not user or not user.is_authenticated:
            if is_debug_enabled():
                print("[PERMISSION] Not authenticated - DENYING")
            return False
        
        # Get module from view
        module = getattr(view, 'module', None)
        
        # Get action
        action = view.action if hasattr(view, 'action') else None
        if not action:
            # Map HTTP method to action for non-viewset views
            method_map = {
                'GET': 'read',
                'POST': 'create',
                'PUT': 'update',
                'PATCH': 'update',
                'DELETE': 'delete',
            }
            action = method_map.get(request.method, 'read')
        
        # Debug output
        if is_debug_enabled():
            tier = resolve_tier(user)
            print(f"\n[PERMISSION CHECK]")
            print(f"User: {user.email if hasattr(user, 'email') else user}")
            print(f"Role: {user.role.name if hasattr(user, 'role') and user.role else 'NO_ROLE'}")
            print(f"Tier: {tier}")
            print(f"Module: {module}")
            print(f"Action: {action}")
        
        # ===== CHECK FOR BYPASSED ACTIONS =====
        # If the view declares bypassed actions, let them through
        bypassed_actions = getattr(view, 'bypassed_actions', set())
        if action in bypassed_actions:
            if is_debug_enabled():
                print(f"[PERMISSION] Action '{action}' is BYPASSED - ALLOWING")
                print("[END CHECK]\n")
            return True  # The action method will handle its own permissions
        
        # ===== STANDARD PERMISSION CHECKS =====
        
        # Skip if permissions system is disabled
        if not is_enabled():
            if is_debug_enabled():
                print("[PERMISSION] System disabled - ALLOWING")
            return True
        
        # Module is required for permission checks
        if not module:
            if is_debug_enabled():
                print("[PERMISSION] No module on view - DENYING for safety")
            return False  # Deny for safety if no module specified
        
        # Skip if module is not enabled
        if not is_module_enabled(module):
            if is_debug_enabled():
                print(f"[PERMISSION] Module {module} not enabled - ALLOWING")
            return True
        
        # Check permission using the registry
        allowed = check_has_permission(user, module, action)
        
        if is_debug_enabled():
            print(f"Result: {'ALLOWED' if allowed else 'DENIED'}")
            print("[END CHECK]\n")
        
        return allowed
    
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
        # Check for bypassed actions
        action = view.action if hasattr(view, 'action') else None
        bypassed_actions = getattr(view, 'bypassed_actions', set())
        if action in bypassed_actions:
            if is_debug_enabled():
                print(f"[OBJECT PERMISSION] Action '{action}' is BYPASSED - ALLOWING")
            return True  # The action handles its own object permissions
        
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
        if not action:
            method_map = {
                'GET': 'read',
                'POST': 'create',
                'PUT': 'update',
                'PATCH': 'update',
                'DELETE': 'delete',
            }
            action = method_map.get(request.method, 'read')
        
        # Get user's scope
        scope = check_permission(request.user, module, action)
        
        # Deny if no permission
        if scope == 'none':
            return False
        
        # Allow if client-level access
        if scope == 'client':
            return True
        
        # For team/mine scopes, check if object matches the filter
        q_filter = build_q(module, scope, request.user, action)
        model_class = obj.__class__
        matches = model_class.objects.filter(q_filter, pk=obj.pk).exists()
        
        return matches


class ScopedQuerysetMixin:
    """
    Mixin that automatically filters querysets based on permissions.
    
    Supports bypassed actions that handle their own filtering.
    
    Add this to your ViewSet before the base class:
    
        class AccountViewSet(ScopedQuerysetMixin, viewsets.ModelViewSet):
            module = 'accounts'  # Required!
            queryset = Account.objects.all()
            
            # Optional: actions that handle their own queryset filtering
            bypassed_actions = {'special_list'}
    """
    
    # Module name must be set on the view
    module: Optional[str] = None
    
    # Actions that bypass permission filtering (optional)
    bypassed_actions: Set[str] = set()
    
    def get_queryset(self) -> QuerySet:
        """
        Filter queryset based on user's permission scope.
        
        This method is called by DRF to get the base queryset.
        We filter it based on the user's permissions unless the
        action is bypassed.
        
        Returns:
            Filtered queryset
        """
        # Get base queryset from parent
        queryset = super().get_queryset()
        
        # Check if this action is bypassed
        action = self._get_current_action()
        if action in getattr(self, 'bypassed_actions', set()):
            # Bypassed actions handle their own filtering
            return queryset
        
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
                'PATCH': 'update',
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
        if module and not check_has_permission(self.request.user, module, 'create'):
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