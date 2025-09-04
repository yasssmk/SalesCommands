"""
DRF Mixins for Permission System

This module provides Django REST Framework integration:
- ScopedPermission: DRF permission class for access control
- ScopedQuerysetMixin: Automatic queryset filtering by scope

IMPORTANT: Client filtering FIRST, then scope filtering.
"""

from typing import Optional, Set, Dict, Any
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView
from django.db.models import QuerySet, Q
from django.conf import settings

from .checks import check_permission, has_permission
from .config import is_module_enabled, is_enabled
from .compat import get_auth_ctx
from .policies import (
    resolve_action_policy,
    check_action_policy_permission,
    resolve_scope_profile,
    ScopeProfiles
)


class ScopedPermission(permissions.BasePermission):
    """
    DRF Permission class that checks permissions using our registry.
    
    Uses role flags (is_admin/is_manager/is_individual) for decisions.
    No tier inference from names.
    
    Requires the view to have a 'module' attribute defining which
    module it belongs to.
    
    Example:
        class AccountViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticated, ScopedPermission]
            module = 'accounts'
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
            print(f"[MIXINS] Permissions system disabled - allowing access")
            return True
        
        # Get module from view
        module = getattr(view, 'module', None)
        if not module:
            # No module specified - deny by default
            print(f"[MIXINS] No module specified on view {view.__class__.__name__} - DENY")
            return False
        
        # Skip if module is not enabled
        if not is_module_enabled(module):
            print(f"[MIXINS] Module {module} not enabled - allowing access")
            return True
        
        # Get action
        action = self._get_action(view)
        
        # Normalize PATCH to UPDATE
        if action == 'patch':
            action = 'update'
        
        print(f"[MIXINS] Permission check for {module}/{action}")
        
        # Check if this action has a custom policy
        action_policies = getattr(view, 'action_policies', {})
        if action in action_policies:
            print(f"[MIXINS] Using action policy for {action}")
            # Use action_policies for this specific action
            is_permitted, scope = check_action_policy_permission(
                action_policies, action, request, module
            )
            
            # Store the resolved scope on the request for later use
            if is_permitted:
                request._applied_scope = scope
            
            return is_permitted
        
        # Standard registry check
        result = has_permission(request, module, action)
        
        if not result:
            print(f"[MIXINS] Permission denied for {module}/{action}")
        else:
            print(f"[MIXINS] Permission granted for {module}/{action}")
        
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
                'partial_update': 'update',  # PATCH = UPDATE
                'destroy': 'delete',
            }
            return action_map.get(view.action, view.action)
        
        # For APIView, check request method
        if hasattr(view, 'request'):
            method_map = {
                'GET': 'read',
                'POST': 'create',
                'PUT': 'update',
                'PATCH': 'update',  # PATCH = UPDATE
                'DELETE': 'delete',
            }
            return method_map.get(view.request.method, 'read')
        
        # Default to read (most restrictive for queries)
        return 'read'


class ScopedQuerysetMixin:
    """
    Mixin to automatically filter querysets based on permission scopes.
    
    CRITICAL: Client filtering FIRST, then scope filtering.
    
    IMPORTANT: This mixin should be placed FIRST in the inheritance chain
    before BaseAPIView to ensure proper MRO execution.
    
    The mixin applies scope-based filtering AFTER
    BaseAPIView has already applied client-level filtering.
    
    Add this FIRST in your ViewSet inheritance:
    
        class AccountViewSet(ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
            module = 'accounts'  # Required!
            queryset = Account.objects.all()
    """
    
    # Module name must be set on the view
    module: Optional[str] = None
    
    # Optional action policies
    action_policies: Dict[str, Dict[str, Any]] = {}
    
    def get_queryset(self) -> QuerySet:
        """
        Filter queryset based on user's permission scope.
        
        CRITICAL: Apply client filter FIRST, then scope filter.
        
        Returns:
            Filtered queryset
        """
        print(f"[MIXINS] ========== ScopedQuerysetMixin.get_queryset() START ==========")
        print(f"[MIXINS] View: {self.__class__.__name__}")
        print(f"[MIXINS] Action: {getattr(self, 'action', 'unknown')}")
        print(f"[MIXINS] Module: {getattr(self, 'module', 'unknown')}")
        
        # CRITICAL: Call super() to get the base queryset
        # This ensures BaseAPIView applies client filtering first
        queryset = super().get_queryset()
        
        print(f"[MIXINS] Queryset count after super (should be client-filtered): {queryset.count()}")
        
        # Skip if permissions system is disabled
        if not is_enabled():
            print(f"[MIXINS] Permissions system DISABLED - returning queryset as-is")
            return queryset
        
        # Get module
        module = getattr(self, 'module', None)
        if not module:
            print(f"[MIXINS] No module specified - returning empty for safety")
            return queryset.none()
        
        # Skip if module is not enabled
        if not is_module_enabled(module):
            print(f"[MIXINS] Module {module} DISABLED - returning queryset as-is")
            return queryset
        
        # Get auth context (NO DB)
        ctx = get_auth_ctx(self.request)
        
        print(f"[MIXINS] Auth context: user_id={ctx.user_id}, client_id={ctx.client_id}, "
            f"roles={len(ctx.roles)}, teams={len(ctx.teams)}")
        
        # CRITICAL: Ensure client filtering is applied
        # This should already be done by BaseAPIView, but double-check
        if ctx.client_id and hasattr(queryset.model, 'client_account_id'):
            # Apply client filter FIRST (tenant isolation)
            queryset = queryset.filter(client_account_id=ctx.client_id)
            print(f"[MIXINS] Applied client filter: client_account_id={ctx.client_id}")
            print(f"[MIXINS] Queryset count after client filter: {queryset.count()}")
        elif ctx.client_id:
            # Try alternate client field names
            client_fields = ['client_account', 'client_id', 'client']
            for field in client_fields:
                if hasattr(queryset.model, field):
                    filter_kwargs = {f'{field}_id': ctx.client_id}
                    queryset = queryset.filter(**filter_kwargs)
                    print(f"[MIXINS] Applied client filter: {field}_id={ctx.client_id}")
                    print(f"[MIXINS] Queryset count after client filter: {queryset.count()}")
                    break
        
        # Get user and check authentication
        user = self.request.user if hasattr(self, 'request') else None
        if not user or not user.is_authenticated:
            print(f"[MIXINS] User not authenticated - returning empty")
            return queryset.none()
        
        # Get the action
        action = self._get_action()
        
        # Normalize PATCH to UPDATE
        if action == 'patch':
            action = 'update'
            print(f"[MIXINS] Normalized PATCH to UPDATE")
        
        print(f"[MIXINS] Resolved action: {action}")
        
        # CRITICAL FIX: Check action_policies FIRST for custom actions
        action_policies = getattr(self, 'action_policies', {})
        if action in action_policies:
            print(f"[MIXINS] Found action policy for {action} - using policy scope")
            policy = action_policies[action]
            
            # Check if policy has a scope defined
            if 'scope' in policy:
                scope = policy['scope']
                print(f"[MIXINS] Action policy defines scope: {scope}")
            else:
                # If no scope in policy, use CRUD mapping
                crud_action = policy.get('crud', 'read')
                scope = check_permission(self.request, module, crud_action)
                print(f"[MIXINS] Action policy maps to CRUD: {crud_action}, scope: {scope}")
        else:
            # Standard registry lookup for CRUD actions
            scope = check_permission(self.request, module, action)
            print(f"[MIXINS] Standard permission check returned scope: {scope}")
        
        if not scope or scope == 'none':
            print(f"[MIXINS] No permission for {module}/{action} - returning empty")
            return queryset.none()
        
        print(f"[MIXINS] Permission check returned scope: {scope}")
        
        # Apply scope filtering
        if scope == 'client':
            # Client scope - already filtered by client above
            print(f"[MIXINS] Scope is 'client' - no additional filtering needed")
            
        elif scope == 'team':
            # Team scope - filter by team ownership
            print(f"[MIXINS] Applying 'team' scope filter")
            
            # Build Q filter for team scope
            q_filter = Q()
            
            # Check ownership map for team fields
            if hasattr(queryset.model, 'owner_team_id') and ctx.teams:
                q_filter |= Q(owner_team_id__in=ctx.teams)
                print(f"[MIXINS] Added owner_team filter for teams: {ctx.teams}")
            
            # Also include user's own items
            if hasattr(queryset.model, 'owner_user_id'):
                q_filter |= Q(owner_user_id=ctx.user_id)
                print(f"[MIXINS] Added owner_user filter for user: {ctx.user_id}")
            
            if hasattr(queryset.model, 'created_by_id'):
                q_filter |= Q(created_by_id=ctx.user_id)
                print(f"[MIXINS] Added created_by filter for user: {ctx.user_id}")
            
            if hasattr(queryset.model, 'assigned_to_user_id'):
                q_filter |= Q(assigned_to_user_id=ctx.user_id)
                print(f"[MIXINS] Added assigned_to_user filter for user: {ctx.user_id}")
            
            if q_filter:
                queryset = queryset.filter(q_filter)
                print(f"[MIXINS] Applied team scope filter")
            else:
                print(f"[MIXINS] No team ownership fields found - using client scope")
            
        elif scope == 'mine':
            # Mine scope - filter by user ownership
            print(f"[MIXINS] Applying 'mine' scope filter")
            
            # Build Q filter for mine scope
            q_filter = Q()
            
            # Check ownership map for user fields
            if hasattr(queryset.model, 'owner_user_id'):
                q_filter |= Q(owner_user_id=ctx.user_id)
                print(f"[MIXINS] Added owner_user filter")
            
            if hasattr(queryset.model, 'created_by_id'):
                q_filter |= Q(created_by_id=ctx.user_id)
                print(f"[MIXINS] Added created_by filter")
            
            if hasattr(queryset.model, 'assigned_to_user_id'):
                q_filter |= Q(assigned_to_user_id=ctx.user_id)
                print(f"[MIXINS] Added assigned_to_user filter")
            
            # Special case for User model - can only see themselves
            if queryset.model.__name__ == 'User':
                q_filter = Q(id=ctx.user_id)
                print(f"[MIXINS] User model - filtering to self only")
            
            if q_filter:
                queryset = queryset.filter(q_filter)
                print(f"[MIXINS] Applied mine scope filter")
            else:
                # No ownership fields - fallback to empty for safety
                print(f"[MIXINS] No ownership fields found - returning empty for 'mine' scope")
                return queryset.none()
        
        print(f"[MIXINS] Final queryset count: {queryset.count()}")
        print(f"[MIXINS] ========== ScopedQuerysetMixin.get_queryset() END ==========")
        
        return queryset
    def _get_action(self) -> str:
        """
        Get the current action being performed.
        
        Returns:
            Action name (defaults to CRUD mapping)
        """
        # For ViewSets, use the action attribute
        if hasattr(self, 'action'):
            action_map = {
                'list': 'read',
                'retrieve': 'read',
                'create': 'create',
                'update': 'update',
                'partial_update': 'update',  # PATCH = UPDATE
                'destroy': 'delete',
            }
            return action_map.get(self.action, self.action)
        
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
        
        # Default to read
        return 'read'