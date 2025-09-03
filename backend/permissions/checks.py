"""
Permission Checks - Core permission verification logic

This module contains the core functions for checking permissions
based on the registry and user context.
"""

from typing import Optional, Dict, Any, Union
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from .registry import get_scope
from .config import is_module_enabled, is_enabled, audit_log


def check_permission(user_or_request, module: str, action: str, obj=None) -> Optional[str]:
    """
    Check permission and return the allowed scope.
    
    This is the main function for checking permissions. It:
    1. Verifies the system is enabled
    2. Checks if the module is enabled
    3. Gets the user's tier
    4. Looks up the permission in registry
    5. Returns the allowed scope or None
    
    Args:
        user_or_request: Django user object OR DRF request object
        module: Module name (e.g., 'accounts')
        action: Action name (e.g., 'read', 'create')
        obj: Optional object for object-level permissions
        
    Returns:
        Scope string ('client'|'team'|'mine'|'none') or None if denied
    """
    # Skip if system disabled
    if not is_enabled():
        return 'client'  # Allow all if system disabled
    
    # Skip if module disabled
    if not is_module_enabled(module):
        return 'client'  # Allow all if module disabled
    
    # Extract user from request if needed
    if hasattr(user_or_request, 'user'):
        # It's a request object
        user = user_or_request.user
    else:
        # It's already a user object
        user = user_or_request
    
    # Check authentication
    if not user or isinstance(user, AnonymousUser):
        return None
    
    # For Django User model compatibility
    if hasattr(user, 'is_authenticated'):
        # Check if it's a property or method
        if callable(user.is_authenticated):
            if not user.is_authenticated():
                return None
        else:
            if not user.is_authenticated:
                return None
    
    # Get user's tier from their role
    tier = resolve_tier(user)
    
    # Get permission from registry - using get_scope (correct function name)
    scope = get_scope(module, action, tier)
    
    # Audit log the permission check with correct signature
    audit_log(
        action='permission_check',
        module=module,
        user=user,
        scope=scope or 'none',
        allowed=(scope is not None and scope != 'none'),
        tier=tier,
        request_action=action
    )
    
    # Handle 'none' scope as denial
    if scope == 'none':
        return None
    
    return scope


def has_permission(user_or_request, module: str, action: str, obj=None) -> bool:
    """
    Check if a user has permission to perform an action.
    
    This is a boolean wrapper around check_permission for simpler checks.
    
    Args:
        user_or_request: Django user object OR DRF request object
        module: Module name
        action: Action name
        obj: Optional object for object-level permissions
        
    Returns:
        True if permission granted, False otherwise
    """
    scope = check_permission(user_or_request, module, action, obj)
    return scope is not None and scope != 'none'


def resolve_tier(user) -> str:
    """
    Resolve a user's permission tier.
    
    The tier determines what level of access they have:
    - admin: Full access to everything in their client
    - manager: Access to their team's data
    - individual: Access to their own data only
    
    Args:
        user: Django user object
        
    Returns:
        Tier string ('admin'|'manager'|'individual')
    """
    # Check superuser status
    if hasattr(user, 'is_superuser') and user.is_superuser:
        return 'admin'
    
    # Check user's role
    if hasattr(user, 'role') and user.role:
        role = user.role
        
        # Check role flags (UserRole model)
        if hasattr(role, 'is_admin') and role.is_admin:
            return 'admin'
        elif hasattr(role, 'is_manager') and role.is_manager:
            return 'manager'
        elif hasattr(role, 'is_individual') and role.is_individual:
            return 'individual'
        
        # Fallback to role name analysis
        if hasattr(role, 'name') and role.name:
            role_name_lower = role.name.lower()
            if 'admin' in role_name_lower:
                return 'admin'
            elif 'manager' in role_name_lower:
                return 'manager'
    
    # Check cached role_name on user
    if hasattr(user, 'role_name') and user.role_name:
        role_name_lower = user.role_name.lower()
        if 'admin' in role_name_lower:
            return 'admin'
        elif 'manager' in role_name_lower:
            return 'manager'
    
    # Default to individual (least privilege)
    return 'individual'


def check_object_permission(user_or_request, module: str, action: str, obj) -> bool:
    """
    Check object-level permissions.
    
    This extends check_permission to handle specific object instances.
    
    Args:
        user_or_request: Django user object OR DRF request object
        module: Module name
        action: Action name  
        obj: The object to check permissions for
        
    Returns:
        True if permission granted, False otherwise
    """
    # Extract user from request if needed
    if hasattr(user_or_request, 'user'):
        user = user_or_request.user
    else:
        user = user_or_request
    
    # First check general permission
    scope = check_permission(user, module, action)
    
    if not scope or scope == 'none':
        return False
    
    # For 'client' scope, user can access any object in their client
    if scope == 'client':
        # TODO: Verify object belongs to user's client
        return True
    
    # For 'team' scope, check team membership
    if scope == 'team':
        # Check if object belongs to user's team
        if hasattr(obj, 'team_id') and hasattr(user, 'team_id'):
            return obj.team_id == user.team_id
        elif hasattr(obj, 'owner') and hasattr(obj.owner, 'team_id'):
            return obj.owner.team_id == user.team_id
    
    # For 'mine' scope, check ownership
    if scope == 'mine':
        # Check various ownership fields
        if hasattr(obj, 'owner_id'):
            return obj.owner_id == user.id
        elif hasattr(obj, 'owner'):
            return obj.owner == user
        elif hasattr(obj, 'created_by_id'):
            return obj.created_by_id == user.id
        elif hasattr(obj, 'created_by'):
            return obj.created_by == user
        elif hasattr(obj, 'user_id'):
            return obj.user_id == user.id
        elif hasattr(obj, 'user'):
            return obj.user == user
            
        # Special case for User model (users can access themselves)
        if obj.__class__.__name__ == 'User':
            return obj.id == user.id
    
    # Default deny
    return False


# Backward compatibility aliases
def get_user_tier(user) -> str:
    """
    Get a user's permission tier.
    
    Alias for resolve_tier for backward compatibility.
    
    Args:
        user: Django user object
        
    Returns:
        Tier string
    """
    return resolve_tier(user)