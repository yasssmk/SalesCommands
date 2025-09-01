"""
Permission Registry - Central source of truth for all permissions

This registry defines what each tier (admin/manager/individual) can do
for each module and action, and at what scope (client/team/mine/none).

CRITICAL RULE: DENY BY DEFAULT
If any entry is missing from this registry, the permission is denied (scope = none).

Structure:
    REGISTRY[module][action][tier] = scope

Where:
    - module: Django app name (accounts, contacts, etc.)
    - action: CRUD operation (create, read, update, delete)
    - tier: User tier (admin, manager, individual)
    - scope: Data access level (client, team, mine, none)
"""

from typing import Dict, Literal

# Type hints for better IDE support
Module = Literal[
    'accounts', 'contacts', 'activities', 'leads', 'opportunities',
    'campaign', 'pipelines', 'templates', 'users', 'products',
]
Action = Literal['create', 'read', 'update', 'delete']
Tier = Literal['admin', 'manager', 'individual']
Scope = Literal['client', 'team', 'mine', 'none']

# Main Permission Registry
# IMPORTANT: PATCH = UPDATE (partial_update maps to update)
REGISTRY: Dict[Module, Dict[Action, Dict[Tier, Scope]]] = {
    
    # ========================================================================
    # ACCOUNTS MODULE
    # Ownership: user-based (owner_user, owner_team, created_by)
    # ========================================================================
    'accounts': {
        'create': {
            'admin': 'client',      # Admin can create any account
            'manager': 'team',      # Manager can create for their team
            'individual': 'mine',   # Individual can create their own
        },
        'read': {
            'admin': 'client',      # Admin sees all accounts
            'manager': 'client',      # Manager sees all accounts
            'individual': 'client',   # Individual sees all accounts
        },
        'update': {
            'admin': 'client',      # Admin can update any account
            'manager': 'team',      # Manager can update team accounts
            'individual': 'mine',   # Individual can update own accounts
        },
        'delete': {
            'admin': 'client',      # Admin can delete any account
            'manager': 'none',      # Manager cannot delete accounts
            'individual': 'none',   # Individual cannot delete accounts
        },
    },
    
    # ========================================================================
    # CONTACTS MODULE
    # Ownership: account-based (inherits from parent account)
    # ========================================================================
    'contacts': {
        'create': {
            'admin': 'client',      # Admin can create any contact
            'manager': 'team',      # Manager can create for team accounts
            'individual': 'mine',   # Individual for their accounts
        },
        'read': {
            'admin': 'client',      # Admin sees all contacts
            'manager': 'client',      # Manager sees all contacts
            'individual': 'client',   # Individual sees all contacts
        },
        'update': {
            'admin': 'client',      # Admin can update any contact
            'manager': 'team',      # Manager can update team contacts
            'individual': 'mine',   # Individual updates own account contacts
        },
        'delete': {
            'admin': 'client',      # Admin can delete any contact
            'manager': 'none',      # Manager cannot delete contacts
            'individual': 'none',   # Individual cannot delete contacts
        },
    },
    
    # ========================================================================
    # ACTIVITIES MODULE
    # Ownership: user-based (owner_user, assigned_to_user)
    # ========================================================================
    'activities': {
        'create': {
            'admin': 'client',      # Admin can create any activity
            'manager': 'team',      # Manager can create for team
            'individual': 'mine',   # Individual creates own activities
        },
        'read': {
            'admin': 'client',      # Admin sees all activities
            'manager': 'client',      # Manager sees all activities
            'individual': 'client',   # Individual sees all activities
        },
        'update': {
            'admin': 'client',      # Admin can update any activity
            'manager': 'team',      # Manager can update team activities
            'individual': 'mine',   # Individual updates own activities
        },
        'delete': {
            'admin': 'client',      # Admin can delete any activity
            'manager': 'mine',      # Manager deletes own activities
            'individual': 'mine',   # Individual can delete own activities
        },
    },
    
    # ========================================================================
    # LEADS MODULE
    # Ownership: user-based (assigned_to_user, created_by)
    # ========================================================================
    'leads': {
        'create': {
            'admin': 'client',      # Admin can create any lead
            'manager': 'client',    # Manager can create any lead
            'individual': 'client', # Anyone can create leads
        },
        'read': {
            'admin': 'client',      # Admin sees all leads
            'manager': 'client',      # Manager sees all leads
            'individual': 'client',   # Individual sees all leads
        },
        'update': {
            'admin': 'client',      # Admin can update any lead
            'manager': 'team',      # Manager can update team leads
            'individual': 'mine',   # Individual updates assigned leads
        },
        'delete': {
            'admin': 'client',      # Admin can delete any lead
            'manager': 'team',      # Manager can delete team leads
            'individual': 'none',   # Individual cannot delete leads
        },
    },
    
    # ========================================================================
    # OPPORTUNITIES MODULE
    # Ownership: user-based (deal_owner mapped to owner_user)
    # ========================================================================
    'opportunities': {
        'create': {
            'admin': 'client',      # Admin can create any opportunity
            'manager': 'team',      # Manager can create for team
            'individual': 'mine',   # Individual creates own opportunities
        },
        'read': {
            'admin': 'client',      # Admin sees all opportunities
            'manager': 'client',      # Manager sees all opportunities
            'individual': 'client',   # Individual sees all opportunities
        },
        'update': {
            'admin': 'client',      # Admin can update any opportunity
            'manager': 'team',      # Manager can update team opportunities
            'individual': 'mine',   # Individual updates own opportunities
        },
        'delete': {
            'admin': 'client',      # Admin can delete any opportunity
            'manager': 'team',      # Manager can delete team opportunities
            'individual': 'none',   # Individual cannot delete opportunities
        },
    },
    
    # ========================================================================
    # CAMPAIGN MODULE
    # Ownership: user-based (owner field)
    # ========================================================================
    'campaign': {
        'create': {
            'admin': 'client',      # Admin can create any campaign
            'manager': 'mine',      # Manager creates own campaigns
            'individual': 'mine',   # Individual creates own campaigns
        },
        'read': {
            'admin': 'client',      # Admin sees all campaigns
            'manager': 'team',      # Manager sees team campaigns
            'individual': 'mine',   # Individual sees own campaigns
        },
        'update': {
            'admin': 'client',      # Admin can update any campaign
            'manager': 'team',      # Manager can update team campaigns
            'individual': 'mine',   # Individual updates own campaigns
        },
        'delete': {
            'admin': 'client',      # Admin can delete any campaign
            'manager': 'team',      # Manager deletes own campaigns
            'individual': 'mine',   # Individual deletes own campaigns
        },
    },
    
    # ========================================================================
    # PIPELINES MODULE (Buying Process)
    # Ownership: opportunity-based (inherits from parent opportunity)
    # ========================================================================
    'pipelines': {
        'create': {
            'admin': 'client',      # Admin can create pipelines
            'manager': 'team',      # Manager can create team pipelines
            'individual': 'mine',   # Individual can create for own opportunities
        },
        'read': {
            'admin': 'client',      # Admin sees all pipelines
            'manager': 'client',    # Manager sees all pipelines
            'individual': 'client', # Everyone can read pipelines
        },
        'update': {
            'admin': 'client',      # Admin can update pipelines
            'manager': 'team',      # Manager can update team pipelines
            'individual': 'mine',   # Individual updates own opportunity pipelines
        },
        'delete': {
            'admin': 'client',      # Admin can delete pipelines
            'manager': 'team',      # Manager can delete team pipelines
            'individual': 'none',   # Individual cannot delete pipelines
        },
    },
    
    # ========================================================================
    # TEMPLATES MODULE
    # Ownership: none (global resources)
    # IMPORTANT: For ownership=none, mine/team→client for READ only
    # ========================================================================
    'templates': {
        'create': {
            'admin': 'client',      # Admin can create templates
            'manager': 'client',    # Manager can create templates
            'individual': 'none',   # Individual cannot create templates
        },
        'read': {
            'admin': 'client',      # Admin sees all templates
            'manager': 'client',    # Manager sees all templates
            'individual': 'client', # Everyone can read templates
        },
        'update': {
            'admin': 'client',      # Admin can update templates
            'manager': 'none',      # Manager cannot update templates
            'individual': 'none',   # Individual cannot update templates
        },
        'delete': {
            'admin': 'client',      # Admin can delete templates
            'manager': 'none',      # Manager cannot delete templates
            'individual': 'none',   # Individual cannot delete templates
        },
    },
    
    # ========================================================================
    # USERS MODULE (end_users)
    # Ownership: user-based (self or managed users)
    # ========================================================================
    'users': {
        'create': {
            'admin': 'client',      # Admin can create any user
            'manager': 'none',      # Manager cannot create users
            'individual': 'none',   # Individual cannot create users
        },
        'read': {
            'admin': 'client',      # Admin sees all users
            'manager': 'client',      # Manager sees all users
            'individual': 'client',   # Individual sees all users
        },
        'update': {
            'admin': 'client',      # Admin can update any user
            'manager': 'team',      # Manager can update team users
            'individual': 'none',   # Individual cannot updates own profile
        },
        'delete': {
            'admin': 'client',      # Admin can delete any user
            'manager': 'none',      # Manager cannot delete users
            'individual': 'none',   # Individual cannot delete users
        },
    },

    # ========================================================================
    # Product module 
    # Ownership: none
    # ========================================================================
    'users': {
        'create': {
            'admin': 'client',      # Admin can create any product
            'manager': 'none',      # Manager cannot create product
            'individual': 'none',   # Individual cannot create product
        },
        'read': {
            'admin': 'client',      # Admin sees all product
            'manager': 'client',      # Manager sees all product
            'individual': 'client',   # Individual sees all product
        },
        'update': {
            'admin': 'client',      # Admin can update any product
            'manager': 'none',      # Manager cannot update product
            'individual': 'none',   # Individual cannot updates product
        },
        'delete': {
            'admin': 'client',      # Admin can delete any product
            'manager': 'none',      # Manager cannot delete product
            'individual': 'none',   # Individual cannot delete product
        },
    },
}




# ========================================================================
# SPECIAL RULES & OVERRIDES
# ========================================================================

# Admin bypass list - actions where admin should be restricted
# Format: {(module, action): reason}
ADMIN_RESTRICTIONS: Dict[tuple, str] = {
    # Example: ('users', 'delete'): 'Cannot delete system users',
    # Currently no restrictions for admin
}

# Action aliases for DRF compatibility
ACTION_ALIASES = {
    'list': 'read',
    'retrieve': 'read',
    'create': 'create',
    'update': 'update',
    'partial_update': 'update',  # PATCH = UPDATE
    'destroy': 'delete',
}

# Default scopes when ownership type is missing
OWNERSHIP_DEFAULTS = {
    'read': 'client',       # Permissive for read
    'create': 'none',       # Restrictive for write
    'update': 'none',       # Restrictive for write
    'delete': 'none',       # Restrictive for delete
}

def get_permission(module: str, action: str, tier: str) -> str:
    """
    Get permission scope from registry with DENY BY DEFAULT.
    
    Args:
        module: Module name (e.g., 'accounts')
        action: CRUD action (e.g., 'update')
        tier: User tier (e.g., 'manager')
        
    Returns:
        Scope string ('client', 'team', 'mine', 'none')
        Returns 'none' if any key is missing (DENY BY DEFAULT)
    """
    # Map DRF action to CRUD if needed
    action = ACTION_ALIASES.get(action, action)
    
    # DENY BY DEFAULT - any missing entry returns 'none'
    if module not in REGISTRY:
        return 'none'
    
    if action not in REGISTRY[module]:
        return 'none'
    
    if tier not in REGISTRY[module][action]:
        return 'none'
    
    # Check for admin restrictions
    if tier == 'admin' and (module, action) in ADMIN_RESTRICTIONS:
        return 'none'
    
    return REGISTRY[module][action][tier]