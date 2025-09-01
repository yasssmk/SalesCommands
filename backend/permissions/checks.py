"""
Permission Checks - Core decision engine for permissions

This module provides the main functions to check permissions:
- resolve_tier: Determine user's tier from their role
- get_scope: Get permission scope from registry
- check_permission: Main function combining tier resolution and scope lookup
- has_permission: Boolean helper for simple allow/deny

CRITICAL: DENY BY DEFAULT
Any missing entry or error returns 'none' scope (denied).
"""

from typing import Optional, Union
from django.contrib.auth import get_user_model
from django.conf import settings

from .registry import get_permission, ACTION_ALIASES
from .ownership import get_ownership_type

# Get User model
User = get_user_model()


def resolve_tier(user) -> str:
    """
    Resolve user's tier from their role.
    
    Strategy (MVP):
    - Check role name for keywords (admin, manager)
    - Default to 'individual' if no match
    
    Future: Use dedicated tier field on UserRole model
    
    Args:
        user: Django User instance
        
    Returns:
        Tier string: 'admin', 'manager', or 'individual'
    """
    if not user or not user.is_authenticated:
        return 'individual'  # Anonymous = lowest tier
    
    # Superuser is always admin
    if hasattr(user, 'is_superuser') and user.is_superuser:
        return 'admin'
    
    # Check role name (case-insensitive)
    if hasattr(user, 'role') and user.role:
        role_name = user.role.name.lower() if user.role.name else ''
        
        # Check for admin keywords
        if any(keyword in role_name for keyword in ['admin', 'administrator']):
            return 'admin'
        
        # Check for manager keywords  
        if any(keyword in role_name for keyword in ['manager', 'supervisor', 'lead']):
            return 'manager'
    
    # Default to individual
    return 'individual'


def get_scope(module: str, action: str, tier: str) -> str:
    """
    Get permission scope for a module/action/tier combination.
    
    Handles special cases:
    - ownership=none modules: mine/team → client for READ only
    - Missing entries: return 'none' (DENY BY DEFAULT)
    
    Args:
        module: Module name (e.g., 'accounts')
        action: CRUD action (e.g., 'update') or DRF action
        tier: User tier ('admin', 'manager', 'individual')
        
    Returns:
        Scope: 'client', 'team', 'mine', or 'none'
    """
    # Normalize DRF action to CRUD
    action = ACTION_ALIASES.get(action, action)
    
    # Get base permission from registry
    scope = get_permission(module, action, tier)
    
    # Special handling for ownership=none modules
    if scope in ['mine', 'team'] and get_ownership_type(module) == 'none':
        # For ownership=none, mine/team → client ONLY for READ
        if action == 'read':
            return 'client'
        # For create/update/delete, keep original scope (likely 'none')
    
    return scope


def check_permission(
    user,
    module: str,
    action: str,
    obj=None
) -> str:
    """
    Main permission check function.
    
    Combines tier resolution and scope lookup to determine
    what scope of data the user can access.
    
    Args:
        user: Django User instance
        module: Module name (e.g., 'accounts')
        action: CRUD or DRF action (e.g., 'update', 'partial_update')
        obj: Optional - specific object being accessed
        
    Returns:
        Scope: 'client', 'team', 'mine', or 'none'
        
    Example:
        scope = check_permission(request.user, 'accounts', 'update')
        if scope == 'none':
            raise PermissionDenied()
    """
    # Resolve user's tier
    tier = resolve_tier(user)
    
    # Get scope from registry
    scope = get_scope(module, action, tier)
    
    # Optional: Add object-level checks here in the future
    # For now, we just return the scope
    
    return scope


def has_permission(
    user,
    module: str,
    action: str,
    obj=None
) -> bool:
    """
    Boolean permission check.
    
    Convenience wrapper around check_permission that returns
    True/False instead of the scope.
    
    Args:
        user: Django User instance
        module: Module name
        action: CRUD or DRF action
        obj: Optional - specific object
        
    Returns:
        True if permission granted (scope != 'none')
        False if permission denied (scope == 'none')
        
    Example:
        if not has_permission(request.user, 'accounts', 'delete'):
            raise PermissionDenied()
    """
    scope = check_permission(user, module, action, obj)
    return scope != 'none'


def get_user_permissions_summary(user) -> dict:
    """
    Get a summary of all permissions for a user.
    
    Useful for debugging and UI display.
    
    Args:
        user: Django User instance
        
    Returns:
        Dict with tier and permissions by module
    """
    tier = resolve_tier(user)
    
    # Get all modules from registry
    from .registry import REGISTRY
    
    summary = {
        'user_id': user.id if user and user.is_authenticated else None,
        'tier': tier,
        'permissions': {}
    }
    
    for module in REGISTRY:
        module_perms = {}
        for action in ['create', 'read', 'update', 'delete']:
            module_perms[action] = get_scope(module, action, tier)
        summary['permissions'][module] = module_perms
    
    return summary


def check_object_permission(
    user,
    module: str,
    action: str,
    obj
) -> bool:
    """
    Check permission for a specific object instance.
    
    This combines scope-based filtering with object-level checks.
    
    Args:
        user: Django User instance
        module: Module name
        action: CRUD or DRF action
        obj: Model instance to check
        
    Returns:
        True if user can access this specific object
        False otherwise
        
    Note:
        This is a placeholder for future object-level permission logic.
        Currently just checks if scope != 'none'.
    """
    scope = check_permission(user, module, action, obj)
    
    if scope == 'none':
        return False
    
    if scope == 'client':
        # User can access any object in their client
        return True
    
    # For team/mine scopes, we need to check ownership
    # This will be implemented with the scoping module
    # For now, return True if scope is not 'none'
    
    return True


# Utility functions for common checks

def is_admin(user) -> bool:
    """Check if user has admin tier."""
    return resolve_tier(user) == 'admin'


def is_manager(user) -> bool:
    """Check if user has manager tier."""
    return resolve_tier(user) == 'manager'


def is_individual(user) -> bool:
    """Check if user has individual tier."""
    return resolve_tier(user) == 'individual'


def can_create(user, module: str) -> bool:
    """Check if user can create in module."""
    return has_permission(user, module, 'create')


def can_read(user, module: str) -> bool:
    """Check if user can read in module."""
    return has_permission(user, module, 'read')


def can_update(user, module: str) -> bool:
    """Check if user can update in module."""
    return has_permission(user, module, 'update')


def can_delete(user, module: str) -> bool:
    """Check if user can delete in module."""
    return has_permission(user, module, 'delete')