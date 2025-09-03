"""
Permission Checks - Core decision engine for permissions

This module contains the logic to determine if a user has permission
to perform an action on a module.
"""

from typing import Optional, Literal
from django.contrib.auth import get_user_model

from .registry import get_scope 
from .config import is_module_enabled, is_enabled, is_debug_enabled


# Action aliases for DRF compatibility
ACTION_ALIASES = {
    'list': 'read',
    'retrieve': 'read',
    'create': 'create',
    'update': 'update',
    'partial_update': 'update',
    'destroy': 'delete',
    'patch': 'update',
}


def resolve_tier(user) -> str:
    """
    Resolve user's permission tier.
    
    Priority order:
    1. Superuser → 'admin'
    2. Role with is_admin flag → 'admin'
    3. Role name contains 'admin' → 'admin'
    4. Role name contains 'manager' → 'manager'
    5. Default → 'individual'
    
    Args:
        user: Django User instance
        
    Returns:
        'admin' | 'manager' | 'individual'
    """
    if not user or not user.is_authenticated:
        return 'individual'
    
    # Superuser is always admin
    if hasattr(user, 'is_superuser') and user.is_superuser:
        return 'admin'
    
    # Check role
    if hasattr(user, 'role') and user.role:
        role = user.role
        
        # Check is_admin flag
        if hasattr(role, 'is_admin') and role.is_admin:
            return 'admin'
        
        # Check role name
        if hasattr(role, 'name'):
            role_name = role.name.lower()
            if 'admin' in role_name:
                return 'admin'
            elif 'manager' in role_name:
                return 'manager'
    
    # Default to individual
    return 'individual'


def check_permission(
    user,
    module: str,
    action: str,
    obj=None
) -> str:
    """
    Check if user has permission to perform action on module.
    
    Args:
        user: Django User instance
        module: Module name (e.g., 'accounts')
        action: CRUD or DRF action
        obj: Optional object instance for object-level checks
        
    Returns:
        Scope: 'client' | 'team' | 'mine' | 'none'
    """
    # Skip if system disabled
    if not is_enabled():
        return 'client'
    
    # Skip if module disabled
    if not is_module_enabled(module):
        return 'client'
    
    # Not authenticated
    if not user or not user.is_authenticated:
        return 'none'
    
    # Map DRF actions to CRUD
    action = ACTION_ALIASES.get(action, action)
    
    # Get user tier
    tier = resolve_tier(user)
    
    # Get scope from registry
    scope = get_scope(module, action, tier)
    
    if is_debug_enabled():
        print(f"Permission check: user={user.id}, module={module}, action={action}, tier={tier}, scope={scope}")
    
    return scope


def has_permission(
    user,
    module: str,
    action: str
) -> bool:
    """
    Simple boolean check for permission.
    
    Args:
        user: Django User instance
        module: Module name
        action: CRUD or DRF action
        
    Returns:
        True if user has any level of permission
    """
    scope = check_permission(user, module, action)
    return scope != 'none'


# Re-export for backward compatibility
__all__ = [
    'resolve_tier',
    'check_permission',
    'has_permission',
    'ACTION_ALIASES',
]