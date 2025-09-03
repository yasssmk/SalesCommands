from typing import Dict, Literal

Action = Literal['create', 'read', 'update', 'delete']
Tier = Literal['admin', 'manager', 'individual']
Scope = Literal['client', 'team', 'mine', 'none']
ModulePermissions = Dict[Action, Dict[Tier, Scope]]

# ============================================================================
# CONTACTS MODULES REGISTRY
# ============================================================================

CONTACTS_REGISTRY: Dict[str, ModulePermissions] = {
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
    }

}