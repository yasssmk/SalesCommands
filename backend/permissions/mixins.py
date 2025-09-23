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

import logging

# Import robuste de get_correlation_id
try:
    from backend.core.logging.context import get_correlation_id
except ImportError:
    try:
        from core.logging.context import get_correlation_id
    except ImportError:
        def get_correlation_id():
            return '-'

logger = logging.getLogger(__name__)


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
            logger.debug("permissions_system_disabled", extra={
                'correlation_id': get_correlation_id(),
                'view': view.__class__.__name__,
                'event': 'permissions_check'
            })
            return True
        
        # Get module from view
        module = getattr(view, 'module', None)
        if not module:
            # No module specified - deny by default
            logger.warning("permission_denied_no_module", extra={
                'correlation_id': get_correlation_id(),
                'view': view.__class__.__name__,
                'user_id': str(request.user.id) if hasattr(request, 'user') and hasattr(request.user, 'id') else '-',
                'event': 'permission_denied'
            })
            return False
        
        # Skip if module is not enabled
        if not is_module_enabled(module):
            logger.debug("module_not_enabled", extra={
                'correlation_id': get_correlation_id(),
                'module': module,
                'view': view.__class__.__name__,
                'event': 'permissions_check'
            })
            return True
        
        # Get action
        action = self._get_action(view)
        
        # Normalize PATCH to UPDATE
        if action == 'patch':
            action = 'update'
        
        logger.debug("permission_check_start", extra={
            'correlation_id': get_correlation_id(),
            'biz_module': module,
            'action': action,
            'user_id': str(request.user.id) if hasattr(request, 'user') and hasattr(request.user, 'id') else '-',
            'method': request.method,
            'path': request.path if hasattr(request, 'path') else '-',
            'event': 'permission_check'
        })
        
        # Check if this action has a custom policy
        action_policies = getattr(view, 'action_policies', {})
        if action in action_policies:
            logger.debug("using_action_policy", extra={
                'correlation_id': get_correlation_id(),
                'biz_module': module,
                'action': action,
                'event': 'permission_check'
            })
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
            logger.info("permission_denied", extra={
                'correlation_id': get_correlation_id(),
                'biz_module': module,
                'action': action,
                'user_id': str(request.user.id) if hasattr(request, 'user') and hasattr(request.user, 'id') else '-',
                'client_id': getattr(request, 'client_id', '-'),
                'method': request.method,
                'path': request.path if hasattr(request, 'path') else '-',
                'event': 'permission_denied'
            })
        else:
            logger.debug("permission_granted", extra={
                'correlation_id': get_correlation_id(),
                'biz_module': module,
                'action': action,
                'user_id': str(request.user.id) if hasattr(request, 'user') and hasattr(request.user, 'id') else '-',
                'event': 'permission_granted'
            })
        
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
        logger.debug("scoped_queryset_start", extra={
            'correlation_id': get_correlation_id(),
            'view': self.__class__.__name__,
            'action': getattr(self, 'action', 'unknown'),
            'biz_module': getattr(self, 'module', 'unknown'),
            'user_id': str(self.request.user.id) if hasattr(self.request, 'user') and hasattr(self.request.user, 'id') else '-',
            'event': 'queryset_filter'
        })
        
        # CRITICAL: Call super() to get the base queryset
        # This ensures BaseAPIView applies client filtering first
        queryset = super().get_queryset()
        
        logger.debug("queryset_after_super", extra={
            'correlation_id': get_correlation_id(),
            'count': queryset.count(),
            'event': 'queryset_filter'
        })
        
        # Skip if permissions system is disabled
        if not is_enabled():
            logger.debug("permissions_disabled_in_queryset", extra={
                'correlation_id': get_correlation_id(),
                'event': 'queryset_filter'
            })
            return queryset
        
        # Get module
        module = getattr(self, 'module', None)
        if not module:
            logger.warning("no_module_in_queryset", extra={
                'correlation_id': get_correlation_id(),
                'view': self.__class__.__name__,
                'event': 'queryset_filter'
            })
            return queryset.none()
        
        # Skip if module is not enabled
        if not is_module_enabled(module):
            logger.debug("module_disabled_in_queryset", extra={
                'correlation_id': get_correlation_id(),
                'biz_module': module,
                'event': 'queryset_filter'
            })
            return queryset
        
        # Get auth context (NO DB)
        ctx = get_auth_ctx(self.request)
        
        logger.debug("auth_context", extra={
            'correlation_id': get_correlation_id(),
            'user_id': ctx.user_id,
            'client_id': ctx.client_id,
            'roles_count': len(ctx.roles),
            'teams_count': len(ctx.teams),
            'event': 'queryset_filter'
        })
        
        # CRITICAL: Ensure client filtering is applied
        # This should already be done by BaseAPIView, but double-check
        if ctx.client_id and hasattr(queryset.model, 'client_account_id'):
            # Apply client filter FIRST (tenant isolation)
            queryset = queryset.filter(client_account_id=ctx.client_id)
            logger.debug("client_filter_applied", extra={
                'correlation_id': get_correlation_id(),
                'client_id': ctx.client_id,
                'count_after': queryset.count(),
                'event': 'queryset_filter'
            })
        elif ctx.client_id:
            # Try alternate client field names
            client_fields = ['client_account', 'client_id', 'client']
            for field in client_fields:
                if hasattr(queryset.model, field):
                    filter_kwargs = {f'{field}_id': ctx.client_id}
                    queryset = queryset.filter(**filter_kwargs)
                    logger.debug("client_filter_applied", extra={
                        'correlation_id': get_correlation_id(),
                        'client_id': ctx.client_id,
                        'count_after': queryset.count(),
                        'event': 'queryset_filter'
                    })
                    break
        
        # Get user and check authentication
        user = self.request.user if hasattr(self, 'request') else None
        if not user or not user.is_authenticated:
            logger.warning("unauthenticated_queryset", extra={
                'correlation_id': get_correlation_id(),
                'event': 'queryset_filter'
            })
            return queryset.none()
        
        # Get the action
        action = self._get_action()
        
        # Normalize PATCH to UPDATE
        if action == 'patch':
            action = 'update'
            logger.debug("normalized_patch_to_update", extra={
                'correlation_id': get_correlation_id(),
                'event': 'queryset_filter'
            })
        
        # Check action_policies FIRST for custom actions
        action_policies = getattr(self, 'action_policies', {})
        if action in action_policies:
            logger.debug("action_policy_found", extra={
                'correlation_id': get_correlation_id(),
                'action': action,
                'biz_module': module,
                'event': 'queryset_filter'
            })
            policy = action_policies[action]
            
            # Check if policy has a scope defined
            if 'scope' in policy:
                scope = policy['scope']
                logger.debug("action_policy_scope", extra={
                    'correlation_id': get_correlation_id(),
                    'action': action,
                    'scope': scope,
                    'event': 'queryset_filter'
                })
            else:
                # If no scope in policy, use CRUD mapping
                crud_action = policy.get('crud', 'read')
                scope = check_permission(self.request, module, crud_action)
                logger.debug("action_policy_crud_mapping", extra={
                    'correlation_id': get_correlation_id(),
                    'action': action,
                    'crud_action': crud_action,
                    'scope': scope,
                    'event': 'queryset_filter'
                })
        else:
            # Standard registry lookup for CRUD actions
            scope = check_permission(self.request, module, action)
            logger.debug("permission_scope_resolved", extra={
                'correlation_id': get_correlation_id(),
                'biz_module': module,
                'action': action,
                'scope': scope,
                'event': 'queryset_filter'
            })
        
        if not scope or scope == 'none':
            logger.info("no_permission_empty_queryset", extra={
                'correlation_id': get_correlation_id(),
                'biz_module': module,
                'action': action,
                'user_id': str(self.request.user.id) if hasattr(self.request, 'user') and hasattr(self.request.user, 'id') else '-',
                'event': 'permission_denied'
            })
            return queryset.none()
        
        logger.debug("permission_check_returned_scope", extra={
            'correlation_id': get_correlation_id(),
            'scope': scope,
            'event': 'queryset_filter'
        })
        
        # Apply scope filtering
        if scope == 'client':
            # Client scope - already filtered by client above
            logger.debug("scope_client", extra={
                'correlation_id': get_correlation_id(),
                'scope': 'client',
                'event': 'queryset_filter'
            })
            
        elif scope == 'team':
            # Team scope - filter by team ownership
            logger.debug("scope_team", extra={
                'correlation_id': get_correlation_id(),
                'scope': 'team',
                'teams': ctx.teams,
                'event': 'queryset_filter'
            })
            
            # Build Q filter for team scope
            q_filter = Q()
            
            # Check ownership map for team fields
            if hasattr(queryset.model, 'owner_team_id') and ctx.teams:
                q_filter |= Q(owner_team_id__in=ctx.teams)
                logger.debug("added_owner_team_filter", extra={
                    'correlation_id': get_correlation_id(),
                    'teams': ctx.teams,
                    'event': 'queryset_filter'
                })
            
            # Also include user's own items
            if hasattr(queryset.model, 'owner_user_id'):
                q_filter |= Q(owner_user_id=ctx.user_id)
                logger.debug("added_owner_user_filter", extra={
                    'correlation_id': get_correlation_id(),
                    'user_id': ctx.user_id,
                    'event': 'queryset_filter'
                })
            
            if hasattr(queryset.model, 'created_by_id'):
                q_filter |= Q(created_by_id=ctx.user_id)
                logger.debug("added_created_by_filter", extra={
                    'correlation_id': get_correlation_id(),
                    'user_id': ctx.user_id,
                    'event': 'queryset_filter'
                })
            
            if hasattr(queryset.model, 'assigned_to_user_id'):
                q_filter |= Q(assigned_to_user_id=ctx.user_id)
                logger.debug("added_assigned_to_filter", extra={
                    'correlation_id': get_correlation_id(),
                    'user_id': ctx.user_id,
                    'event': 'queryset_filter'
                })
            
            if q_filter:
                queryset = queryset.filter(q_filter)
                logger.debug("applied_team_scope_filter", extra={
                    'correlation_id': get_correlation_id(),
                    'event': 'queryset_filter'
                })
            else:
                logger.debug("no_team_ownership_fields", extra={
                    'correlation_id': get_correlation_id(),
                    'event': 'queryset_filter'
                })
            
        elif scope == 'mine':
            # Mine scope - filter by user ownership
            logger.debug("scope_mine", extra={
                'correlation_id': get_correlation_id(),
                'scope': 'mine',
                'user_id': ctx.user_id,
                'event': 'queryset_filter'
            })
            
            # Build Q filter for mine scope
            q_filter = Q()
            
            # Check ownership map for user fields
            if hasattr(queryset.model, 'owner_user_id'):
                q_filter |= Q(owner_user_id=ctx.user_id)
                logger.debug("added_owner_user_filter_mine", extra={
                    'correlation_id': get_correlation_id(),
                    'user_id': ctx.user_id,
                    'event': 'queryset_filter'
                })
            
            if hasattr(queryset.model, 'created_by_id'):
                q_filter |= Q(created_by_id=ctx.user_id)
                logger.debug("added_created_by_filter_mine", extra={
                    'correlation_id': get_correlation_id(),
                    'user_id': ctx.user_id,
                    'event': 'queryset_filter'
                })
            
            if hasattr(queryset.model, 'assigned_to_user_id'):
                q_filter |= Q(assigned_to_user_id=ctx.user_id)
                logger.debug("added_assigned_to_filter_mine", extra={
                    'correlation_id': get_correlation_id(),
                    'user_id': ctx.user_id,
                    'event': 'queryset_filter'
                })
            
            # Special case for User model - can only see themselves
            if queryset.model.__name__ == 'User':
                q_filter = Q(id=ctx.user_id)
                logger.debug("user_model_self_only", extra={
                    'correlation_id': get_correlation_id(),
                    'user_id': ctx.user_id,
                    'event': 'queryset_filter'
                })
            
            if q_filter:
                queryset = queryset.filter(q_filter)
                logger.debug("applied_mine_scope_filter", extra={
                    'correlation_id': get_correlation_id(),
                    'event': 'queryset_filter'
                })
            else:
                # No ownership fields - fallback to empty for safety
                logger.debug("no_ownership_fields_mine_scope", extra={
                    'correlation_id': get_correlation_id(),
                    'event': 'queryset_filter'
                })
                return queryset.none()
        
        logger.debug("queryset_final", extra={
            'correlation_id': get_correlation_id(),
            'biz_module': module,
            'action': action,
            'scope': scope if 'scope' in locals() else '-',
            'final_count': queryset.count(),
            'event': 'queryset_filter'
        })
        
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