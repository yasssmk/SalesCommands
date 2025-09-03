"""
Registry Module - Aggregates all module registries

This module combines all individual registries into a single REGISTRY
that can be imported from permissions.registry.
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
    
    return registry


# Build the complete registry
REGISTRY = build_registry()

def get_scope(module: str, action: str, tier: str) -> Scope:
    """
    Get the scope for a specific module/action/tier combination.
    
    Args:
        module: Module name (e.g., 'accounts')
        action: CRUD action ('create', 'read', 'update', 'delete')
        tier: User tier ('admin', 'manager', 'individual')A
        
    Returns:
        Scope ('client', 'team', 'mine', 'none')
        Returns 'none' for any missing entries (deny-by-default)
    """
    # Handle PATCH as UPDATE
    if action == 'patch':
        action = 'update'

    if action == 'list':
        action = 'read'
    elif action == 'retrieve': 
        action = 'read'
    elif action in ['update', 'partial_update']:
        action = 'update'
    elif action == 'destroy':
        action = 'delete'
    
    # Get module permissions
    module_perms = REGISTRY.get(module)
    if not module_perms:
        return 'none'  # Module not found - deny
    
    # Get action permissions
    action_perms = module_perms.get(action)
    if not action_perms:
        return 'none'  # Action not found - deny
    
    # Get tier scope
    scope = action_perms.get(tier, 'none')
    return scope

# Export the combined registry and helpers
__all__ = ['REGISTRY', 'get_scope', 'Action', 'Tier', 'Scope', 'ModulePermissions']
