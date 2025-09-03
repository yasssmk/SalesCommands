from typing import Dict, Literal

Action = Literal['create', 'read', 'update', 'delete']
Tier = Literal['admin', 'manager', 'individual']
Scope = Literal['client', 'team', 'mine', 'none']
ModulePermissions = Dict[Action, Dict[Tier, Scope]]



# ============================================================================
# ACCOUNTS MODULES REGISTRY
# ============================================================================

ACCOUNTS_REGISTRY: Dict[str, ModulePermissions] = {

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
    }
}