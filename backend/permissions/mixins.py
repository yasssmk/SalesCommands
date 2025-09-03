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
from django.conf import settings

from .checks import check_permission, has_permission
from .config import is_module_enabled, is_enabled, is_debug_enabled, audit_log
from .compat import get_auth_ctx, get_client_idA
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
    
    Example:
        class AccountViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticated, ScopedPermission]
            module = 'accounts'
            
            action_policies = {
                'custom_action': {'crud': 'read', 'scope': 'team_only'},
            }
    """
    
    def has_permission(self, request: Request, view: APIView) -> bool:
        """
        Check if the request should be permitted.
        
        Args:
            request: DRF request
            view: The view being accessed
            
        Returns:
            True if permission granted, False otherwise
        """
        # Skip if permissions system is disabled
        if not is_enabled():
            return True
        
        # Get module from view
        module = getattr(view, 'module', None)
        if not module:
            # No module specified - deny by default
            # FIX: Use correct audit_log signature
            user = getattr(request, 'user', None) if hasattr(request, 'user') else None
            audit_log(
                action='permission_denied',
                module='unknown',
                user=user,
                scope='none',
                allowed=False,
                reason='no_module',
                view=view.__class__.__name__
            )
            return False
        
        # Skip if module is not enabled
        if not is_module_enabled(module):
            return True
        
        # Get action
        action = self._get_action(view)
        
        # Check if this action has a custom policy
        action_policies = getattr(view, 'action_policies', {})
        if action in action_policies:
            # Use action_policies for this specific action
            is_permitted, scope = check_action_policy_permission(
                action_policies, action, request, module
            )
            
            # Store the resolved scope on the request for later use
            if is_permitted:
                request._applied_scope = scope
            
            return is_permitted
        
        # Standard registry check
        # The has_permission function in checks.py can handle both request and user
        # It will extract the user from request if needed
        result = has_permission(request, module, action)
        
        if not result:
            # FIX: Use correct audit_log signature
            user = getattr(request, 'user', None) if hasattr(request, 'user') else None
            audit_log(
                action='permission_denied',
                module=module,
                user=user,
                scope='none',
                allowed=False,
                view_action=action
            )
        
        return result
    
    def has_object_permission(self, request: Request, view: APIView, obj) -> bool:
        """
        Check object-level permissions.
        
        For now, we rely on queryset filtering for most cases.
        This can be enhanced later for specific object checks.
        
        Args:
            request: DRF request
            view: The view being accessed
            obj: The object being accessed
            
        Returns:
            True if permission granted, False otherwise
        """
        # For now, if they passed has_permission and the object
        # is in the filtered queryset, they can access it
        return True
    
    def _get_action(self, view: APIView) -> str:
        """
        Get the current action being performed.
        
        Args:
            view: The view being accessed
            
        Returns:
            Action name (defaults to CRUD mapping)
        """
        # For ViewSets, use the action attribute
        if hasattr(view, 'action'):
            # Map certain actions to their CRUD equivalents
            action_map = {
                'list': 'read',
                'retrieve': 'read',
                'create': 'create',
                'update': 'update',
                'partial_update': 'update',
                'destroy': 'delete',
            }
            return action_map.get(view.action, view.action)
        
        # For APIView, check request method
        if hasattr(view, 'request'):
            method_map = {
                'GET': 'read',
                'POST': 'create',
                'PUT': 'update',
                'PATCH': 'update',
                'DELETE': 'delete',
            }
            return method_map.get(view.request.method, 'read')
        
        # Default to read (most restrictive for queries)
        return 'read'


class ScopedQuerysetMixin:
    """
    Mixin to automatically filter querysets based on permission scopes.
    
    IMPORTANT: This mixin should be placed FIRST in the inheritance chain
    before BaseAPIView to ensure proper MRO execution.
    
    The mixin applies scope-based filtering (mine/team/client) AFTER
    BaseAPIView has already applied client-level filtering.
    
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
    
    # Debug flag - can be set per view or globally
    debug_permissions: bool = False
    
    def get_queryset(self) -> QuerySet:
        """
        Filter queryset based on user's permission scope.
        
        IMPORTANT: This method chains with super() to maintain proper MRO.
        It does NOT re-apply client filtering as that's handled by BaseAPIView.
        
        Call chain:
        1. This method is called
        2. Calls super() → BaseAPIView.get_queryset()
        3. BaseAPIView applies client filter and returns
        4. We apply scope filter on top
        5. Return final filtered queryset
        
        Returns:
            Filtered queryset
        """
        # FORCE DEBUG ON to see what's happening
        debug = True  # Always debug for now
        
        if debug:
            print(f"[MIXIN DEBUG] ========== ScopedQuerysetMixin.get_queryset() START ==========")
            print(f"[MIXIN DEBUG] View: {self.__class__.__name__}")
            print(f"[MIXIN DEBUG] Action: {getattr(self, 'action', 'unknown')}")
            print(f"[MIXIN DEBUG] Module: {getattr(self, 'module', 'unknown')}")
        
        # CRITICAL: Call super() to get the base queryset
        # This ensures BaseAPIView applies client filtering first
        queryset = super().get_queryset()
        
        if debug:
            print(f"[MIXIN DEBUG] Queryset count after super (client-filtered): {queryset.count()}")
        
        # Skip if permissions system is disabled
        if not is_enabled():
            if debug:
                print(f"[MIXIN DEBUG] Permissions system DISABLED - returning queryset as-is")
            return queryset
        
        # Get module
        module = getattr(self, 'module', None)
        if not module:
            if debug:
                print(f"[MIXIN DEBUG] No module specified - returning empty for safety")
                print(f"View {self.__class__.__name__} missing 'module' attribute")
            return queryset.none()
        
        # Skip if module is not enabled
        if not is_module_enabled(module):
            if debug:
                print(f"[MIXIN DEBUG] Module {module} DISABLED - returning queryset as-is")
            return queryset
        
        # Get user and context
        user = self.request.user if hasattr(self, 'request') else None
        if not user or not user.is_authenticated:
            if debug:
                print(f"[MIXIN DEBUG] User not authenticated - returning empty")
            return queryset.none()
        
        # Get auth context
        ctx = get_auth_ctx(self.request)
        
        if debug:
            print(f"[MIXIN DEBUG] Auth Context:")
            print(f"[MIXIN DEBUG]   - origin: {ctx.origin}")
            print(f"[MIXIN DEBUG]   - client_id: {ctx.client_id}")
            print(f"[MIXIN DEBUG]   - tier: {ctx.tier}")
            print(f"[MIXIN DEBUG]   - role_name: {ctx.role_name}")
            print(f"[MIXIN DEBUG]   - is_superuser: {ctx.is_superuser}")
        
        # NOTE: Client filtering already applied by BaseAPIView
        # We only apply scope-based filtering here
        
        # Get the action
        action = self._get_action()
        if debug:
            print(f"[MIXIN DEBUG] Resolved action: {action}")
        
        # Check action policies first
        action_policies = getattr(self, 'action_policies', {})
        if action in action_policies:
            if debug:
                print(f"[MIXIN DEBUG] Found action policy for {action}")
            # Resolve the policy
            crud_action, required_tier, scope_spec = resolve_action_policy(
                action_policies, action, self.request, module
            )
            
            # Check tier requirement
            if required_tier:
                user_tier = ctx.tier
                tier_levels = {'admin': 3, 'manager': 2, 'individual': 1}
                
                if tier_levels.get(user_tier, 0) < tier_levels.get(required_tier, 999):
                    if debug:
                        print(f"[MIXIN DEBUG] Tier requirement not met: {user_tier} < {required_tier}")
                    return queryset.none()
            
            # Apply scope from policy
            if scope_spec:
                if scope_spec in [ScopeProfiles.SELF_ONLY, ScopeProfiles.TEAM_ONLY, 
                                   ScopeProfiles.ADMIN_ONLY_CLIENT, ScopeProfiles.OWNER_ONLY]:
                    # Resolve profile to Q filter
                    resolved_scope, q_filter = resolve_scope_profile(
                        scope_spec, self.request, module, crud_action
                    )
                    if q_filter:
                        queryset = queryset.filter(q_filter)
                        if debug:
                            print(f"[MIXIN DEBUG] Applied policy scope: {scope_spec} → {resolved_scope}")
                elif scope_spec in ['client', 'team', 'mine', 'none']:
                    # Standard scope
                    queryset = self._apply_standard_scope(queryset, scope_spec, user, ctx, debug)
        else:
            if debug:
                print(f"[MIXIN DEBUG] No action policy, using registry")
            # Use registry to determine scope
            # check_permission can handle both user and request objects
            scope = check_permission(user, module, action)
            if debug:
                print(f"[MIXIN DEBUG] Registry returned scope: {scope}")
            if scope:
                queryset = self._apply_standard_scope(queryset, scope, user, ctx, debug)
            else:
                if debug:
                    print(f"[MIXIN DEBUG] No permission for {module}/{action} - returning empty")
                return queryset.none()
        
        if debug:
            print(f"[MIXIN DEBUG] Final queryset count: {queryset.count()}")
            print(f"[MIXIN DEBUG] ========== ScopedQuerysetMixin.get_queryset() END ==========")
        
        return queryset
    
    def _apply_standard_scope(self, queryset: QuerySet, scope: str, 
                              user, ctx, debug: bool = False) -> QuerySet:
        """
        Apply standard scope filtering (mine/team/client).
        
        Args:
            queryset: Already client-filtered queryset
            scope: Scope to apply ('mine', 'team', 'client', 'none')
            user: Current user
            ctx: Auth context
            debug: Debug flag
            
        Returns:
            Filtered queryset
        """
        if scope == 'none':
            if debug:
                print(f"[MIXIN DEBUG] Scope is 'none' - returning empty")
            return queryset.none()
        
        if scope == 'client':
            # Client scope - no additional filter needed
            # BaseAPIView already filtered by client
            if debug:
                print(f"[MIXIN DEBUG] Scope is 'client' - no additional filter needed")
            return queryset
        
        if scope == 'mine':
            # Personal scope - filter by ownership
            # For users module, filter by the user's own ID
            if getattr(self, 'module', None) == 'users':
                queryset = queryset.filter(pk=user.pk)
            else:
                # For other modules, try common ownership fields
                model = queryset.model
                if hasattr(model, 'owner'):
                    queryset = queryset.filter(owner=user)
                elif hasattr(model, 'created_by'):
                    queryset = queryset.filter(created_by=user)
                elif hasattr(model, 'user'):
                    queryset = queryset.filter(user=user)
                elif hasattr(model, 'assigned_to'):
                    queryset = queryset.filter(assigned_to=user)
            if debug:
                print(f"[MIXIN DEBUG] Applied 'mine' scope filter")
        
        elif scope == 'team':
            # Team scope - filter by team membership
            if ctx.teams:
                # For users module, filter by team membership
                if getattr(self, 'module', None) == 'users':
                    queryset = queryset.filter(team_id__in=ctx.teams)
                else:
                    # For other modules, try common team fields
                    model = queryset.model
                    if hasattr(model, 'team'):
                        queryset = queryset.filter(team_id__in=ctx.teams)
                    elif hasattr(model, 'owner__team'):
                        queryset = queryset.filter(owner__team_id__in=ctx.teams)
                    elif hasattr(model, 'created_by__team'):
                        queryset = queryset.filter(created_by__team_id__in=ctx.teams)
            else:
                # No teams, return empty for team scope
                if debug:
                    print(f"[MIXIN DEBUG] User has no teams - returning empty for team scope")
                return queryset.none()
            if debug:
                print(f"[MIXIN DEBUG] Applied 'team' scope filter")
        
        return queryset
    
    def _get_action(self) -> str:
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
    
        class AccountViewSet(PermissionDebugMixin, ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
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