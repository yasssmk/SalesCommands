from typing import Dict, Literal

Action = Literal['create', 'read', 'update', 'delete']
Tier = Literal['admin', 'manager', 'individual']
Scope = Literal['client', 'team', 'mine', 'none']
ModulePermissions = Dict[Action, Dict[Tier, Scope]]

# ============================================================================
# OPPORTUNITIES MODULES REGISTRY
# ============================================================================

OPPORTUNITIES_REGISTRY: Dict[str, ModulePermissions] = {
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

}