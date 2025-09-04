"""
Registry Module - Aggregates all module registries

This module combines all individual registries into a single REGISTRY
that can be imported from permissions.registry.

IMPORTANT: PATCH is always mapped to UPDATE.
Missing entries return 'none' (deny-by-default).
"""

from typing import Dict, Literal

# Import individual registries
from .end_users_registry import END_USERS_REGISTRY
from .accounts_registry import ACCOUNTS_REGISTRY
from .contacts_registry import CONTACTS_REGISTRY
from .activities_registry import ACTIVITIES_REGISTRY
from .leads_registry import LEADS_REGISTRY
from .opportunities_registry import OPPORTUNITIES_REGISTRY
from .products_registry import PRODUCTS_REGISTRY
from .campaigns_registry import CAMPAIGNS_REGISTRY

Action = Literal['create', 'read', 'update', 'delete']
Tier = Literal['admin', 'manager', 'individual']
Scope = Literal['client', 'team', 'mine', 'none']
ModulePermissions = Dict[Action, Dict[Tier, Scope]]

# ============================================================================
# COMBINED REGISTRY
# ============================================================================

def build_registry() -> Dict:
    """
    Build the complete registry by merging all module registries.
    
    Returns:
        Combined registry dictionary
    """
    registry = {}
    
    # Merge all registries
    registry.update(END_USERS_REGISTRY)
    registry.update(ACCOUNTS_REGISTRY)
    registry.update(CONTACTS_REGISTRY)
    registry.update(CAMPAIGNS_REGISTRY)
    registry.update(PRODUCTS_REGISTRY)
    registry.update(ACTIVITIES_REGISTRY)
    registry.update(LEADS_REGISTRY)
    registry.update(OPPORTUNITIES_REGISTRY)
    
    print(f"[REGISTRY] Built registry with {len(registry)} modules")
    for module in registry.keys():
        print(f"[REGISTRY]   - {module}")
    
    return registry


# Build the complete registry
REGISTRY = build_registry()


def get_scope(module: str, action: str, tier: str) -> Scope:
    """
    Get the scope for a specific module/action/tier combination.
    
    CRITICAL: PATCH is ALWAYS mapped to UPDATE.
    Missing entries return 'none' (deny-by-default).
    
    Args:
        module: Module name (e.g., 'accounts', 'users')
        action: CRUD action ('create', 'read', 'update', 'delete', 'patch')
        tier: User tier ('admin', 'manager', 'individual')
        
    Returns:
        Scope ('client', 'team', 'mine', 'none')
        Returns 'none' for any missing entries (deny-by-default)
    """
    # CRITICAL: Always map PATCH to UPDATE
    if action == 'patch':
        action = 'update'
        print(f"[REGISTRY] Mapped PATCH to UPDATE")
    
    # Also handle common action aliases
    if action == 'list':
        action = 'read'
    elif action == 'retrieve': 
        action = 'read'
    elif action in ['update', 'partial_update']:
        action = 'update'
    elif action == 'destroy':
        action = 'delete'
    
    print(f"[REGISTRY] Looking up: module={module}, action={action}, tier={tier}")
    
    # Get module permissions
    module_perms = REGISTRY.get(module)
    if not module_perms:
        print(f"[REGISTRY] Module '{module}' not found - DENY")
        return 'none'  # Module not found - deny
    
    # Get action permissions
    action_perms = module_perms.get(action)
    if not action_perms:
        print(f"[REGISTRY] Action '{action}' not found in module '{module}' - DENY")
        return 'none'  # Action not found - deny
    
    # Get tier scope
    scope = action_perms.get(tier, 'none')
    
    print(f"[REGISTRY] Found scope: {scope} for {module}/{action}/{tier}")
    
    # Validate scope value
    if scope not in ['client', 'team', 'mine', 'none']:
        print(f"[REGISTRY] Invalid scope '{scope}' - returning 'none'")
        return 'none'
    
    return scope


# Export the combined registry and helpers
__all__ = ['REGISTRY', 'get_scope', 'Action', 'Tier', 'Scope', 'ModulePermissions']