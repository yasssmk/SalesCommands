"""
DRF Mixins for Permission System

This module provides Django REST Framework integration:
- ScopedPermission: DRF permission class for access control
- ScopedQuerysetMixin: Automatic queryset filtering by scope
"""

from typing import Optional, Set, Dict, Any
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView
from django.db.models import QuerySet, Q

from .checks import check_permission, has_permission as check_has_permission, resolve_tier
from .scoping import apply_scope_filter, build_q
from .config import is_module_enabled, is_enabled, is_debug_enabled, audit_log
from .compat import get_auth_ctx, get_client_id
from .policies import (
    resolve_action_policy,
    check_action_policy_permission,
    resolve_scope_profile,
    ScopeProfiles
)


class ScopedPermission(permissions.BasePermission):
    """
    DRF Permission class that checks permissions using our registry.
    
    Enhanced to support action_policies for declarative custom actions.
    
    Requires the view to have a 'module' attribute defining which
    module it belongs to.
    
    Supports action_policies for declarative permission configuration:
        action_policies = {
            'change_password': {'crud': 'update', 'scope': 'self_only'},
            'grant_superuser': {'crud': 'update', 'tier': 'admin', 'scope': 'client'},
        }
    
    Example:
        class AccountViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticated, ScopedPermission]
            module = 'accounts'
            
            action_policies = {
                'custom_action': {'crud': 'read', 'scope': 'team_only'},
            }
    """
    def get_queryset(self) -> QuerySet:
        """
        Filter queryset based on user's permission scope.
        """
        # Get base queryset from parent
        queryset = super().get_queryset()
        
        # DEBUG: Tracer le contexte d'authentification
        print(f"[MIXIN DEBUG] ========== ScopedQuerysetMixin ==========")
        print(f"[MIXIN DEBUG] View: {self.__class__.__name__}")
        print(f"[MIXIN DEBUG] Action: {getattr(self, 'action', 'unknown')}")
        print(f"[MIXIN DEBUG] Module: {getattr(self, 'module', 'unknown')}")
        
        # Skip if permissions system is disabled
        if not is_enabled():
            print(f"[MIXIN DEBUG] Permissions system DISABLED")
            return queryset
        
        # Get module
        module = getattr(self, 'module', None)
        if not module:
            print(f"[MIXIN DEBUG] No module specified - returning empty")
            print(f"View {self.__class__.__name__} missing 'module' attribute")
            return queryset.none()
        
        # Skip if module is not enabled
        if not is_module_enabled(module):
            print(f"[MIXIN DEBUG] Module {module} is DISABLED")
            return queryset
        
        # Get user and context
        user = self.request.user if hasattr(self, 'request') else None
        if not user or not user.is_authenticated:
            print(f"[MIXIN DEBUG] User not authenticated")
            return queryset.none()
        
        print(f"[MIXIN DEBUG] User: {user.email if user else 'None'}")
        print(f"[MIXIN DEBUG] User.is_superuser: {getattr(user, 'is_superuser', False)}")
        print(f"[MIXIN DEBUG] User.role: {getattr(user, 'role', 'None')}")
        
        # Get auth context
        from .compat import get_auth_ctx
        ctx = get_auth_ctx(self.request)
        
        print(f"[MIXIN DEBUG] Auth Context:")
        print(f"[MIXIN DEBUG]   - origin: {ctx.origin}")
        print(f"[MIXIN DEBUG]   - client_id: {ctx.client_id}")
        print(f"[MIXIN DEBUG]   - tier: {ctx.tier}")
        print(f"[MIXIN DEBUG]   - role_name: {ctx.role_name}")
        print(f"[MIXIN DEBUG]   - is_superuser: {ctx.is_superuser}")
        
        client_id = ctx.client_id
        
        if client_id:
            # Apply client filter
            model = queryset.model
            
            print(f"[MIXIN DEBUG] Applying client filter for model: {model.__name__}")
            
            if hasattr(model, 'client_account_id'):
                queryset = queryset.filter(client_account_id=client_id)
                print(f"[MIXIN DEBUG] Filtered by client_account_id={client_id}")
            elif hasattr(model, 'client_account'):
                queryset = queryset.filter(client_account__id=client_id)
                print(f"[MIXIN DEBUG] Filtered by client_account__id={client_id}")
            else:
                print(f"[MIXIN DEBUG] ERROR: Model has no client field!")
                return queryset.none()
                
            print(f"[MIXIN DEBUG] After client filter: {queryset.count()} records")
        else:
            print(f"[MIXIN DEBUG] ERROR: No client_id in context")
            return queryset.none()
        
        # Get current action
        action = self._get_current_action()
        print(f"[MIXIN DEBUG] Current action: {action}")
        
        # Apply scope-based filtering
        from .checks import check_permission
        scope = check_permission(user, module, action)
        print(f"[MIXIN DEBUG] Permission scope: {scope}")
        
        if scope == 'none':
            print(f"[MIXIN DEBUG] Scope is 'none' - returning empty")
            return queryset.none()
        elif scope == 'client':
            print(f"[MIXIN DEBUG] Scope is 'client' - returning all in tenant")
            # Already filtered by client above
            pass
        elif scope == 'team':
            print(f"[MIXIN DEBUG] Scope is 'team' - filtering by team")
            if hasattr(user, 'team_id') and user.team_id:
                queryset = queryset.filter(team_id=user.team_id)
                print(f"[MIXIN DEBUG] After team filter: {queryset.count()} records")
        elif scope == 'mine':
            print(f"[MIXIN DEBUG] Scope is 'mine' - filtering by user")
            queryset = queryset.filter(id=user.id)
            print(f"[MIXIN DEBUG] After mine filter: {queryset.count()} records")
        
        print(f"[MIXIN DEBUG] Final count: {queryset.count()} records")
        print(f"[MIXIN DEBUG] ========================================")
        
        return queryset
    
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
        if not module:
            if is_debug_enabled():
                print(f"View {view.__class__.__name__} missing 'module' attribute")
            return False
        
        # Skip if permissions system is disabled
        if not is_enabled():
            return True
        
        # Skip if module is not enabled
        if not is_module_enabled(module):
            return True
        
        # Get the DRF action
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

        # Check for action_policies first
        action_policies = getattr(view, 'action_policies', {})
        if action_policies and action in action_policies:
            # Use action policy
            is_permitted, scope = check_action_policy_permission(
                action_policies, action, request, module
            )
            
            if is_debug_enabled():
                print(f"[PERMISSION] Action policy for '{action}': permitted={is_permitted}, scope={scope}")
            
            return is_permitted
        
        # Fall back to registry-based check
        scope = check_permission(user, module, action)

        # Debug output
        if is_debug_enabled():
            print(f"[PERMISSION] Registry check: module={module}, action={action}, scope={scope}")
        
        # Deny if no permission
        return scope != 'none'
    
    def has_object_permission(self, request: Request, view: APIView, obj) -> bool:
        """
        Check object-level permissions.
        
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
        action = view.action if hasattr(view, 'action') else None
        if not action:
            method_map = {
                'GET': 'read',
                'POST': 'create',
                'PUT': 'update',
                'PATCH': 'update',
                'DELETE': 'delete',
            }
            action = method_map.get(request.method, 'read')
        
        # Check action_policies for special scopes
        action_policies = getattr(view, 'action_policies', {})
        if action_policies and action in action_policies:
            policy = action_policies[action]
            scope_spec = policy.get('scope')
            
            # Handle self_only specially for object permissions
            if scope_spec == ScopeProfiles.SELF_ONLY:
                user = request.user
                
                # For users module, check if accessing own record
                if module == 'users':
                    return obj.pk == user.pk
                
                # For other modules, check ownership
                if hasattr(obj, 'owner_id'):
                    return obj.owner_id == user.pk
                if hasattr(obj, 'created_by_id'):
                    return obj.created_by_id == user.pk
                
                return False
        
        # Standard permission check
        user = request.user
        scope = check_permission(user, module, action)
        
        # Deny if no permission
        if scope == 'none':
            return False
        
        # Allow if client-level access
        if scope == 'client':
            return True
        
        # For team/mine scopes, check if object matches the filter
        q_filter = build_q(module, scope, user, action)
        model_class = obj.__class__
        matches = model_class.objects.filter(q_filter, pk=obj.pk).exists()
        
        return matches


class ScopedQuerysetMixin:
    """
    Mixin that automatically filters querysets based on permissions.
    
    CRITICAL: Always applies client_account filtering FIRST for security.
    Then applies scope-based filtering (mine/team/client).
    
    Add this FIRST in your ViewSet inheritance:
    
        class AccountViewSet(ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
            module = 'accounts'  # Required!
            queryset = Account.objects.all()
            
            # Optional: custom actions with policies
            action_policies = {
                'my_items': {'crud': 'read', 'scope': 'self_only'}
            }
    """
    
    # Module name must be set on the view
    module: Optional[str] = None
    
    # Optional action policies
    action_policies: Dict[str, Dict[str, Any]] = {}
    
    def get_queryset(self) -> QuerySet:
        """
        Filter queryset based on user's permission scope.
        
        SECURITY: Always applies client_account filter FIRST, then scope filter.
        
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
            print(f"View {self.__class__.__name__} missing 'module' attribute")
            return queryset.none()
        
        # Skip if module is not enabled
        if not is_module_enabled(module):
            return queryset
        
        # Get user and context
        user = self.request.user if hasattr(self, 'request') else None
        if not user or not user.is_authenticated:
            return queryset.none()
        
        # ====================================================================
        # CRITICAL: Apply client_account filter FIRST for tenant isolation
        # ====================================================================
        ctx = get_auth_ctx(self.request)
        client_id = ctx.client_id
        
        if client_id:
            # Determine the client field name for this model
            model = queryset.model
            
            # Try common field names
            if hasattr(model, 'client_account_id'):
                queryset = queryset.filter(client_account_id=client_id)
            elif hasattr(model, 'client_account'):
                queryset = queryset.filter(client_account__id=client_id)
            elif hasattr(model, 'client_id'):
                queryset = queryset.filter(client_id=client_id)
            elif hasattr(model, 'client'):
                queryset = queryset.filter(client__id=client_id)
            else:
                # Model doesn't have client field - this is a security risk
                print(f"Model {model.__name__} has no client field for tenant isolation!")
                # Return empty queryset for safety
                return queryset.none()
        else:
            # No client_id in context - deny all for safety
            print("No client_id in auth context - denying access")
            return queryset.none()
        
        # ====================================================================
        # Apply scope-based filtering (after client filtering)
        # ====================================================================
        
        # Get current action
        action = self._get_current_action()
        
        # Check for action_policies with custom scopes
        action_policies = getattr(self, 'action_policies', {})
        if action_policies and action in action_policies:
            policy = action_policies[action]
            scope_spec = policy.get('scope')
            
            # If it's a scope profile, resolve and apply it
            if scope_spec in [
                ScopeProfiles.SELF_ONLY,
                ScopeProfiles.ADMIN_ONLY_CLIENT,
                ScopeProfiles.TEAM_ONLY,
                ScopeProfiles.OWNER_ONLY,
                ScopeProfiles.PUBLIC_READ,
            ]:
                crud_action = policy.get('crud', 'read')
                _, q_filter = resolve_scope_profile(
                    scope_spec, self.request, module, crud_action
                )
                if q_filter:
                    queryset = queryset.filter(q_filter)
                else:
                    return queryset.none()
            
            # Standard scope
            elif scope_spec in ['client', 'team', 'mine', 'none']:
                if scope_spec == 'none':
                    return queryset.none()
                
                # Build and apply filter for standard scope
                q_filter = build_q(module, scope_spec, user, action)
                if q_filter:
                    queryset = queryset.filter(q_filter)
        else:
            # Use registry-based filtering
            filtered_queryset = apply_scope_filter(
                queryset,
                module,
                action,
                user
            )
            queryset = filtered_queryset
        
        return queryset
    
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
        
        Only adds headers if debug_permissions is True and DEBUG mode is on.
        """
        # Call parent
        response = super().finalize_response(request, response, *args, **kwargs)
        
        # Add debug headers if enabled
        if self.debug_permissions and is_debug_enabled():
            from .compat import debug_auth_context
            
            # Add auth context info
            auth_debug = debug_auth_context(request)
            response['X-Auth-Origin'] = auth_debug.get('origin', 'unknown')
            response['X-Auth-Tier'] = auth_debug.get('tier', 'unknown')
            response['X-Auth-ClientId'] = auth_debug.get('client_id', 'none')
            
            # Add module and action info
            if hasattr(self, 'module'):
                response['X-Perm-Module'] = self.module
            if hasattr(self, 'action'):
                response['X-Perm-Action'] = self.action
            
            # Add applied scope
            if hasattr(request, '_applied_scope'):
                response['X-Perm-Scope'] = request._applied_scope
        
        return response