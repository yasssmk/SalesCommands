"""
Permission Checks Module

Core decision engine for the permissions system.
Determines what scope a user has for a given module/action.

IMPORTANT: No tier inference based on role names.
Decision based ONLY on explicit role flags (is_admin/is_manager/is_individual).
"""

from typing import Optional, Union, TYPE_CHECKING
from django.db.models import Model
from rest_framework.request import Request

from .registry import get_scope as registry_get_scope
from .config import is_enabled, is_module_enabled
from .compat import get_auth_ctx, AuthContext

# Type hints only - avoid circular imports
if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser


def check_permission(
    user_or_request: Union['AbstractBaseUser', Request],
    module: str,
    action: str,
    obj: Optional[Model] = None
) -> Optional[str]:
    """
    Check if a user has permission to perform an action on a module.
    
    NO TIER INFERENCE - Decision based on union of role flags only.
    
    Args:
        user_or_request: Django user object OR DRF request object
        module: Module name (e.g., 'accounts', 'users')
        action: Action name (e.g., 'create', 'read', 'update', 'delete')
        obj: Optional object for object-level permissions
        
    Returns:
        Scope string ('client'|'team'|'mine'|'none'|None)
        None means no permission (same as 'none')
    """
    # Skip if system disabled
    if not is_enabled():
        print(f"[CHECKS] Permissions system disabled - allowing access")
        return 'client'
    
    # Skip if module disabled
    if not is_module_enabled(module):
        print(f"[CHECKS] Module {module} not enabled - allowing access")
        return 'client'
    
    # Normalize PATCH to UPDATE
    if action == 'patch':
        action = 'update'
        print(f"[CHECKS] Normalized PATCH to UPDATE")
    
    # Handle list/retrieve as read
    if action in ['list', 'retrieve']:
        action = 'read'
    elif action == 'partial_update':
        action = 'update'
    elif action == 'destroy':
        action = 'delete'
    
    # Get auth context (no DB queries)
    if isinstance(user_or_request, Request):
        ctx = get_auth_ctx(user_or_request)
        user = user_or_request.user if hasattr(user_or_request, 'user') else None
    else:
        # Create minimal context from user
        user = user_or_request
        ctx = AuthContext()
        ctx.user_id = str(user.id) if user and hasattr(user, 'id') else None
        ctx.is_authenticated = user.is_authenticated if user and hasattr(user, 'is_authenticated') else False
        ctx.is_superuser = getattr(user, 'is_superuser', False) if user else False
        
        # Try to get roles from user (no DB)
        if user and hasattr(user, 'role'):
            role = user.role
            if role:
                ctx.roles = [{
                    'is_admin': getattr(role, 'is_admin', False),
                    'is_manager': getattr(role, 'is_manager', False),
                    'is_individual': getattr(role, 'is_individual', False),
                }]
    
    print(f"[CHECKS] Permission check: module={module}, action={action}, "
          f"user_id={ctx.user_id}, client_id={ctx.client_id}, "
          f"roles={len(ctx.roles)}, is_superuser={ctx.is_superuser}")
    
    # Not authenticated = deny
    if not ctx.is_authenticated:
        print(f"[CHECKS] User not authenticated - DENY")
        return None
    
    # Determine effective tier from UNION of role flags
    has_admin = ctx.is_superuser  # Superuser always admin
    has_manager = False
    has_individual = False
    
    # Check all roles for flags (union/additive)
    for role in ctx.roles:
        if isinstance(role, dict):
            if role.get('is_admin'):
                has_admin = True
            if role.get('is_manager'):
                has_manager = True
            if role.get('is_individual'):
                has_individual = True
    
    print(f"[CHECKS] Role union: admin={has_admin}, manager={has_manager}, "
          f"individual={has_individual}")
    
    # Determine effective tier (highest privilege wins)
    if has_admin:
        effective_tier = 'admin'
    elif has_manager:
        effective_tier = 'manager'
    elif has_individual:
        effective_tier = 'individual'
    else:
        # No valid tier = deny
        print(f"[CHECKS] No valid tier found - DENY")
        return None
    
    print(f"[CHECKS] Effective tier: {effective_tier}")
    
    # Get scope from registry
    scope = registry_get_scope(module, action, effective_tier)
    
    print(f"[CHECKS] Registry returned scope: {scope} for {module}/{action}/{effective_tier}")
    
    # Validate scope
    if scope not in ['client', 'team', 'mine', 'none']:
        print(f"[CHECKS] Invalid scope '{scope}' - DENY")
        return None
    
    if scope == 'none':
        print(f"[CHECKS] Scope is 'none' - DENY")
        return None
    
    # Admin scope limited to tenant (never cross-tenant)
    if effective_tier == 'admin' and scope == 'client':
        print(f"[CHECKS] Admin scope limited to tenant (client)")
    
    print(f"[CHECKS] Final decision: scope={scope}")
    return scope


def has_permission(
    user_or_request: Union['AbstractBaseUser', Request],
    module: str,
    action: str,
    obj: Optional[Model] = None
) -> bool:
    """
    Check if a user has permission (boolean version).
    
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


def get_scope(
    user_or_request: Union['AbstractBaseUser', Request],
    module: str,
    action: str
) -> Optional[str]:
    """
    Get the scope for a user's action on a module.
    
    Alias for check_permission for backward compatibility.
    
    Args:
        user_or_request: Django user object OR DRF request object
        module: Module name
        action: Action name
        
    Returns:
        Scope string or None
    """
    return check_permission(user_or_request, module, action)


def resolve_tier(user: 'AbstractBaseUser') -> str:
    """
    DEPRECATED - DO NOT USE.
    
    This function is kept for backward compatibility only.
    Use get_auth_ctx() and check role flags directly.
    
    Args:
        user: Django user object
        
    Returns:
        'individual' always (least privilege)
    """
    print(f"[CHECKS] WARNING: resolve_tier() is DEPRECATED - use role flags directly")
    
    # Return least privilege always
    return 'individual'


def check_object_permission(
    user_or_request: Union['AbstractBaseUser', Request],
    module: str,
    action: str,
    obj: Model
) -> bool:
    """
    Check object-level permissions.
    
    This extends check_permission to handle specific object instances.
    For now, delegates to check_permission for module-level check.
    
    Args:
        user_or_request: Django user object OR DRF request object
        module: Module name
        action: Action name
        obj: The object to check permissions for
        
    Returns:
        True if permission granted, False otherwise
    """
    # First check module-level permission
    scope = check_permission(user_or_request, module, action, obj)
    
    if scope is None or scope == 'none':
        return False
    
    # TODO: Add object-level checks here based on ownership
    # For now, if they have module permission, they pass
    
    return True


# Backward compatibility exports
__all__ = [
    'check_permission',
    'has_permission',
    'get_scope',
    'resolve_tier',  # DEPRECATED
    'check_object_permission',
]