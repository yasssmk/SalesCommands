"""
Centralized CRUD Action Mapping Constants

This module provides a single source of truth for mapping DRF actions and HTTP methods
to standardized CRUD actions (create, read, update, delete).

CRITICAL: This file eliminates 8 duplications across the codebase:
- permissions/mixins.py (2 duplications)
- permissions/policies.py
- permissions/registry/__init__.py
- permissions/checks.py
- end_users/custom_permissions.py
- core/apps_shared_methods.py

Usage:
    from permissions.constants import normalize_action, ACTION_TO_CRUD, HTTP_METHOD_TO_CRUD
    
    # Normalize a DRF action
    crud_action = normalize_action('partial_update')  # Returns: 'update'
    
    # Normalize an HTTP method
    crud_action = normalize_action('PATCH')  # Returns: 'update'
    
    # Use dictionary directly
    crud_action = ACTION_TO_CRUD.get('list', 'read')  # Returns: 'read'
"""

from typing import Literal

# Type definitions for clarity
CrudAction = Literal['create', 'read', 'update', 'delete']
DRFAction = Literal['list', 'retrieve', 'create', 'update', 'partial_update', 'destroy']
HTTPMethod = Literal['GET', 'POST', 'PUT', 'PATCH', 'DELETE']


# ============================================================================
# DJANGO REST FRAMEWORK ACTION MAPPING
# ============================================================================

ACTION_TO_CRUD: dict[str, CrudAction] = {
    # Read operations
    'list': 'read',             # GET /resources/
    'retrieve': 'read',         # GET /resources/{id}/
    
    # Write operations
    'create': 'create',         # POST /resources/
    'update': 'update',         # PUT /resources/{id}/
    'partial_update': 'update', # PATCH /resources/{id}/
    'destroy': 'delete',        # DELETE /resources/{id}/

    # Bulk operations (CRITICAL for permission checks)
    'bulk_create': 'create',
    'bulk_update': 'update',
    'bulk_delete': 'delete',
    
    # Edge cases - normalized forms
    'patch': 'update',          # Lowercase PATCH (rare but supported)
    'delete': 'delete',         # Already CRUD action (passthrough)
    'read': 'read',             # Already CRUD action (passthrough)

    # Activity module - custom status transition actions
    # Maps to 'update' so registry activities.update scope applies per tier
    'complete': 'update',       # POST /activities/{id}/complete/
    'reopen': 'update',         # POST /activities/{id}/reopen/
    'cancel': 'update',         # POST /activities/{id}/cancel/
}


# ============================================================================
# HTTP METHOD MAPPING
# ============================================================================

HTTP_METHOD_TO_CRUD: dict[str, CrudAction] = {
    'GET': 'read',
    'POST': 'create',
    'PUT': 'update',
    'PATCH': 'update',
    'DELETE': 'delete',
    
    # Lowercase variants (for robustness)
    'get': 'read',
    'post': 'create',
    'put': 'update',
    'patch': 'update',
    'delete': 'delete',
}


# ============================================================================
# NORMALIZATION FUNCTION
# ============================================================================

def normalize_action(action: str) -> CrudAction:
    """
    Normalize a DRF action or HTTP method to a standard CRUD action.
    
    This function provides a single source of truth for action normalization,
    eliminating 8 duplications across the codebase.
    
    Handles:
    - DRF ViewSet actions (list, retrieve, create, update, partial_update, destroy)
    - HTTP methods (GET, POST, PUT, PATCH, DELETE)
    - Case variations (lowercase, uppercase, mixed)
    - Edge cases (PATCH vs partial_update)
    
    Args:
        action: DRF action name or HTTP method
        
    Returns:
        Normalized CRUD action: 'create', 'read', 'update', or 'delete'
        Defaults to 'read' if action is unknown (most restrictive)
        
    Examples:
        >>> normalize_action('list')
        'read'
        
        >>> normalize_action('partial_update')
        'update'
        
        >>> normalize_action('PATCH')
        'update'
        
        >>> normalize_action('destroy')
        'delete'
        
        >>> normalize_action('GET')
        'read'
        
        >>> normalize_action('unknown_action')
        'read'  # Defaults to read (most restrictive)
        
    Notes:
        - PATCH and partial_update both map to 'update'
        - Unknown actions default to 'read' (deny-by-default principle)
        - Case-insensitive for robustness
    """
    if not action:
        return 'read'  # Default to most restrictive
    
    # Normalize to lowercase for lookup
    action_lower = action.lower()
    
    # Try DRF action mapping first (most common)
    if action_lower in ACTION_TO_CRUD:
        return ACTION_TO_CRUD[action_lower]
    
    # Try HTTP method mapping (uppercase and lowercase)
    action_upper = action.upper()
    if action_upper in HTTP_METHOD_TO_CRUD:
        return HTTP_METHOD_TO_CRUD[action_upper]
    
    # Unknown action - default to 'read' (most restrictive)
    # This implements deny-by-default security principle
    return 'read'


# ============================================================================
# REVERSE MAPPING (for documentation/debugging)
# ============================================================================

def get_drf_actions_for_crud(crud_action: CrudAction) -> list[str]:
    """
    Get all DRF actions that map to a given CRUD action.
    
    Useful for documentation and debugging.
    
    Args:
        crud_action: CRUD action ('create', 'read', 'update', 'delete')
        
    Returns:
        List of DRF actions that map to this CRUD action
        
    Examples:
        >>> get_drf_actions_for_crud('read')
        ['list', 'retrieve']
        
        >>> get_drf_actions_for_crud('update')
        ['update', 'partial_update', 'patch']
    """
    return [
        drf_action 
        for drf_action, mapped_crud in ACTION_TO_CRUD.items() 
        if mapped_crud == crud_action
    ]


def get_http_methods_for_crud(crud_action: CrudAction) -> list[str]:
    """
    Get all HTTP methods that map to a given CRUD action.
    
    Useful for documentation and debugging.
    
    Args:
        crud_action: CRUD action ('create', 'read', 'update', 'delete')
        
    Returns:
        List of HTTP methods that map to this CRUD action (uppercase only)
        
    Examples:
        >>> get_http_methods_for_crud('read')
        ['GET']
        
        >>> get_http_methods_for_crud('update')
        ['PUT', 'PATCH']
    """
    # Only return uppercase variants
    return [
        method 
        for method, mapped_crud in HTTP_METHOD_TO_CRUD.items() 
        if mapped_crud == crud_action and method.isupper()
    ]


# ============================================================================
# VALIDATION
# ============================================================================

def is_valid_crud_action(action: str) -> bool:
    """
    Check if a string is a valid CRUD action.
    
    Args:
        action: String to check
        
    Returns:
        True if action is one of: 'create', 'read', 'update', 'delete'
        
    Examples:
        >>> is_valid_crud_action('read')
        True
        
        >>> is_valid_crud_action('list')
        False
    """
    return action in ('create', 'read', 'update', 'delete')


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Primary function
    'normalize_action',
    
    # Mappings
    'ACTION_TO_CRUD',
    'HTTP_METHOD_TO_CRUD',
    
    # Helper functions
    'get_drf_actions_for_crud',
    'get_http_methods_for_crud',
    'is_valid_crud_action',
    
    # Type hints
    'CrudAction',
    'DRFAction',
    'HTTPMethod',
]


# ============================================================================
# USAGE EXAMPLES (for documentation)
# ============================================================================

"""
USAGE EXAMPLES:

1. In DRF Permission Classes:
   -----------------------------
   from permissions.constants import normalize_action
   
   class ScopedPermission(BasePermission):
       def has_permission(self, request, view):
           action = normalize_action(view.action)
           # Now action is guaranteed to be 'create'|'read'|'update'|'delete'


2. In ViewSet Methods:
   --------------------
   from permissions.constants import normalize_action
   
   def _get_action(self, view):
       if hasattr(view, 'action'):
           return normalize_action(view.action)
       elif hasattr(view, 'request'):
           return normalize_action(view.request.method)
       return 'read'


3. In Permission Policies:
   ------------------------
   from permissions.constants import ACTION_TO_CRUD
   
   DEFAULT_CRUD_MAP = ACTION_TO_CRUD  # Single source of truth
   crud_action = DEFAULT_CRUD_MAP.get(action, 'read')


4. In Registry Lookups:
   ---------------------
   from permissions.constants import normalize_action
   
   def get_scope(module, action, tier):
       # Normalize action before registry lookup
       normalized = normalize_action(action)
       return REGISTRY[module][normalized][tier]


5. Custom Action Mappings:
   ------------------------
   from permissions.constants import normalize_action, ACTION_TO_CRUD
   
   # Extend with custom actions
   CUSTOM_ACTIONS = {
       'bulk_create': 'create',
       'bulk_update': 'update',
       **ACTION_TO_CRUD  # Include standard mappings
   }
   
   def get_action_mapping(action):
       return CUSTOM_ACTIONS.get(action, normalize_action(action))
"""