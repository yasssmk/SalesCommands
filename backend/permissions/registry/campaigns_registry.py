from typing import Dict, Literal

Action = Literal['create', 'read', 'update', 'delete']
Tier = Literal['admin', 'manager', 'individual']
Scope = Literal['client', 'team', 'mine', 'none']
ModulePermissions = Dict[Action, Dict[Tier, Scope]]

# ============================================================================
# CAMPAIGNS MODULES REGISTRY
# ============================================================================

CAMPAIGNS_REGISTRY: Dict[str, ModulePermissions] = {
    # ========================================================================
    # CAMPAIGN MODULE
    # Ownership: user-based (owner field)
    # ========================================================================
    'campaigns': {
        'create': {
            'admin': 'client',      # Admin can create any campaign
            'manager': 'mine',      # Manager creates own campaigns
            'individual': 'mine',   # Individual creates own campaigns
        },
        'read': {
            'admin': 'client',      # Admin sees all campaigns
            'manager': 'client',      # Manager sees team campaigns
            'individual': 'client',   # Individual sees own campaigns
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

    'campaign_contacts': {
        'create': {
            'admin': 'client',
            'manager': 'mine',
            'individual': 'mine',
        },
        'read': {
            'admin': 'client',
            'manager': 'client',
            'individual': 'client',
        },
        'update': {
            'admin': 'client',
            'manager': 'mine',
            'individual': 'mine',
        },
        'delete': {
            'admin': 'client',
            'manager': 'mine',
            'individual': 'mine',
        },
    },
    

}