from typing import Dict, Literal

Action = Literal['create', 'read', 'update', 'delete']
Tier = Literal['admin', 'manager', 'individual']
Scope = Literal['client', 'team', 'mine', 'none']
ModulePermissions = Dict[Action, Dict[Tier, Scope]]
# ============================================================================
# ACTIVITIES MODULES REGISTRY
# ============================================================================

ACTIVITIES_REGISTRY: Dict[str, ModulePermissions] = {
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
    }

}