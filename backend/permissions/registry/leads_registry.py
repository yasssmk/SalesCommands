from typing import Dict, Literal

Action = Literal['create', 'read', 'update', 'delete']
Tier = Literal['admin', 'manager', 'individual']
Scope = Literal['client', 'team', 'mine', 'none']
ModulePermissions = Dict[Action, Dict[Tier, Scope]]

# ============================================================================
# LEADS MODULES REGISTRY
# ============================================================================

LEADS_REGISTRY: Dict[str, ModulePermissions] = {
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
    }

}