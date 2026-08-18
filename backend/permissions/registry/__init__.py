"""
Registry Module - Aggregates all module registries

This module combines all individual registries into a single REGISTRY
that can be imported from permissions.registry.

IMPORTANT: PATCH is always mapped to UPDATE.
Missing entries return 'none' (deny-by-default).
"""

from typing import Dict, Literal
import logging

# Import individual registries
from .end_users_registry import END_USERS_REGISTRY
from .accounts_registry import ACCOUNTS_REGISTRY
from .contacts_registry import CONTACTS_REGISTRY
from .activities_registry import ACTIVITIES_REGISTRY
from .leads_registry import LEADS_REGISTRY
from .opportunities_registry import OPPORTUNITIES_REGISTRY
from .products_registry import PRODUCTS_REGISTRY
from .campaigns_registry import CAMPAIGNS_REGISTRY
from .territories_registry import TERRITORIES_REGISTRY
from .decision_cycles_registry import DECISION_CYCLES_REGISTRY
from .product_catalog_registry import PRODUCT_CATALOG_REGISTRY
from .signals_registry import SIGNALS_REGISTRY
from .ai_pipelines_registry import AI_PIPELINES_REGISTRY
from .quotas_registry import QUOTAS_REGISTRY

from ..constants import normalize_action
logger = logging.getLogger(__name__)

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
    registry.update(TERRITORIES_REGISTRY)
    registry.update(DECISION_CYCLES_REGISTRY)
    registry.update(PRODUCT_CATALOG_REGISTRY)
    registry.update(SIGNALS_REGISTRY)
    registry.update(AI_PIPELINES_REGISTRY)
    registry.update(QUOTAS_REGISTRY)
    
    logger.debug(f"Built registry with {len(registry)} modules")
    for module in registry.keys():
        logger.debug(f"  - {module}")
    
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
    action = normalize_action(action)
    
    # ✅ REFACTORED: logger.debug() instead of print()
    logger.debug(f"Looking up permission: module={module}, action={action}, tier={tier}")


    # Get module permissions
    module_perms = REGISTRY.get(module)
    if not module_perms:
        logger.debug(f"Module '{module}' not found in registry - returning 'none'")
        return 'none'  # Module not found - deny
    
    # Get action permissions
    action_perms = module_perms.get(action)
    if not action_perms:
        logger.debug(f"Action '{action}' not found in module '{module}' - returning 'none'")
        return 'none'  # Action not found - deny
    
    # Get tier scope
    scope = action_perms.get(tier, 'none')
    
    logger.debug(f"Found scope: {scope} for {module}/{action}/{tier}")
    
    # Validate scope value
    if scope not in ['client', 'team', 'mine', 'none']:
        logger.warning(f"Invalid scope '{scope}' in registry for {module}/{action}/{tier} - returning 'none'")
        return 'none'
    
    return scope


# Export the combined registry and helpers
__all__ = ['REGISTRY', 'get_scope', 'Action', 'Tier', 'Scope', 'ModulePermissions']