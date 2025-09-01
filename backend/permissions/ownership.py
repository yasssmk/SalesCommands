"""
Ownership Mapping - Maps canonical keys to actual model fields

This module defines the mapping between the 6 canonical ownership keys
and the actual field names in each Django model.

Canonical Keys (exactly 6, no more, no less):
1. client_account_fk: FK to ClientAccount (always required)
2. owner_user: FK to User who owns the resource
3. owner_team: FK to Team that owns the resource
4. created_by: FK to User who created the resource
5. assigned_to_user: FK to User assigned to the resource
6. account_fk: FK to Account (for child entities like Contact)

Special Cases:
- ownership=none: Resources with no ownership (templates, products)
- ownership=account: Resources that inherit from Account (contacts)
- ownership=opportunity: Resources that inherit from Opportunity (pipelines/buying process)
  For opportunity inheritance, we use account_fk to point to the opportunity
"""

from typing import Dict, Optional, Literal

# Type hints
OwnershipKey = Literal[
    'client_account_fk',
    'owner_user',
    'owner_team',
    'created_by',
    'assigned_to_user',
    'account_fk',
]

# Ownership Map - Module to Field Mappings
# Use '-' for fields that don't exist
# Use dot notation for related fields (e.g., 'account.owner')
OWNERSHIP_MAP: Dict[str, Dict[OwnershipKey, str]] = {
    
    # ========================================================================
    # ACCOUNTS MODULE
    # ========================================================================
    'accounts': {
        'client_account_fk': 'client_account_id',
        'owner_user': 'owner_id',
        'owner_team': 'team_id',
        'created_by': 'created_by_id',
        'assigned_to_user': '-',
        'account_fk': '-',
    },
    
    # ========================================================================
    # CONTACTS MODULE (inherits from Account)
    # ========================================================================
    'contacts': {
        'client_account_fk': 'account.client_account_id',
        'owner_user': 'account.owner_id',  # Via account
        'owner_team': 'account.team_id',    # Via account
        'created_by': 'created_by_id',
        'assigned_to_user': '-',
        'account_fk': 'account_id',  # Parent account
    },
    
    # ========================================================================
    # ACTIVITIES MODULE
    # ========================================================================
    'activities': {
        'client_account_fk': 'client_account_id',
        'owner_user': 'owner_id',
        'owner_team': 'team_id',
        'created_by': 'created_by_id',
        'assigned_to_user': 'assigned_to_id',
        'account_fk': '-',
    },
    
    # ========================================================================
    # LEADS MODULE
    # ========================================================================
    'leads': {
        'client_account_fk': 'client_account_id',
        'owner_user': '-',  # Leads use assigned_to instead
        'owner_team': 'team_id',
        'created_by': 'created_by_id',
        'assigned_to_user': 'assigned_to_id',
        'account_fk': '-',
    },
    
    # ========================================================================
    # OPPORTUNITIES MODULE
    # ========================================================================
    'opportunities': {
        'client_account_fk': 'client_account_id',
        'owner_user': 'deal_owner_id',  # Mapped from deal_owner
        'owner_team': 'team_id',
        'created_by': 'created_by_id',
        'assigned_to_user': '-',
        'account_fk': 'account_id',  # Related account
    },
    
    # ========================================================================
    # CAMPAIGN MODULE
    # ========================================================================
    'campaign': {
        'client_account_fk': 'client_account_id',
        'owner_user': 'owner_id',
        'owner_team': 'team_id',
        'created_by': 'created_by_id',
        'assigned_to_user': '-',
        'account_fk': '-',
    },
    
    # ========================================================================
    # PIPELINES MODULE (Buying Process - inherits from Opportunity)
    # Note: account_fk is repurposed to point to opportunity
    # ========================================================================
    'pipelines': {
        'client_account_fk': 'opportunity.client_account_id',
        'owner_user': 'opportunity.deal_owner_id',  # Via opportunity
        'owner_team': 'opportunity.team_id',        # Via opportunity
        'created_by': 'created_by_id',
        'assigned_to_user': '-',
        'account_fk': 'opportunity_id',  # Points to parent opportunity
    },
    
    # ========================================================================
    # TEMPLATES MODULE (no ownership)
    # ========================================================================
    'templates': {
        'client_account_fk': 'client_account_id',
        'owner_user': '-',
        'owner_team': '-',
        'created_by': '-',
        'assigned_to_user': '-',
        'account_fk': '-',
    },
    
    # ========================================================================
    # USERS MODULE
    # ========================================================================
    'users': {
        'client_account_fk': 'client_account_id',
        'owner_user': 'id',  # Self-ownership
        'owner_team': 'team_id',
        'created_by': 'created_by_id',
        'assigned_to_user': '-',
        'account_fk': '-',
    },
    
    # ========================================================================
    # PRODUCTS MODULE (no ownership)
    # ========================================================================
    'products': {
        'client_account_fk': 'client_account_id',
        'owner_user': '-',
        'owner_team': '-',
        'created_by': '-',
        'assigned_to_user': '-',
        'account_fk': '-',
    },
}

# Ownership Types by Module
OWNERSHIP_TYPES = {
    'accounts': 'user',        # owner_user, owner_team, created_by
    'contacts': 'account',     # Inherits from account
    'activities': 'user',      # owner_user, assigned_to_user
    'leads': 'user',          # assigned_to_user, created_by
    'opportunities': 'user',   # deal_owner (mapped to owner_user)
    'campaign': 'user',        # owner_user
    'pipelines': 'opportunity', # Inherits from opportunity (buying process)
    'templates': 'none',       # No ownership
    'users': 'user',          # Self or team
    'products': 'none',       # No ownership
}

def resolve_field(module: str, key: str) -> Optional[str]:
    """
    Resolve a canonical key to the actual field name for a module.
    
    Args:
        module: Module name (e.g., 'accounts')
        key: Canonical key (e.g., 'owner_user')
        
    Returns:
        Field name or None if not applicable
        Returns None for '-' entries
    """
    if module not in OWNERSHIP_MAP:
        return None
    
    field = OWNERSHIP_MAP[module].get(key, '-')
    return field if field != '-' else None

def get_ownership_type(module: str) -> str:
    """
    Get the ownership type for a module.
    
    Args:
        module: Module name
        
    Returns:
        Ownership type ('user', 'account', 'opportunity', 'none')
    """
    return OWNERSHIP_TYPES.get(module, 'none')

def get_parent_module(module: str) -> Optional[str]:
    """
    Get the parent module for inheritance-based ownership.
    
    Args:
        module: Module name
        
    Returns:
        Parent module name or None
    """
    ownership_type = get_ownership_type(module)
    
    if ownership_type == 'account':
        return 'accounts'
    elif ownership_type == 'opportunity':
        return 'opportunities'
    
    return None

def resolve_inheritance_chain(module: str, key: str) -> list:
    """
    Resolve the full inheritance chain for a field.
    
    For example, contacts.owner_user -> account.owner_id
    
    Args:
        module: Module name
        key: Canonical key
        
    Returns:
        List of field lookups in order
    """
    field = resolve_field(module, key)
    if not field:
        return []
    
    # If field contains dot notation, it's already a chain
    if '.' in field:
        return field.split('.')
    
    return [field]

def is_ownership_none(module: str) -> bool:
    """
    Check if a module has no ownership (global resources).
    
    Args:
        module: Module name
        
    Returns:
        True if module has ownership=none
    """
    return get_ownership_type(module) == 'none'