# backend/permissions/registry/decision_cycles_registry.py
"""
Permissions registry for Decision Cycles module.

Decision Cycles are sales execution tools linked to accounts.
Read access for all users, write access scoped by ownership.
"""

from typing import Dict, Literal

Action = Literal['create', 'read', 'update', 'delete']
Tier = Literal['admin', 'manager', 'individual']
Scope = Literal['client', 'team', 'mine', 'none']
ModulePermissions = Dict[Action, Dict[Tier, Scope]]

# ============================================================================
# DECISION CYCLES MODULES REGISTRY
# ============================================================================

DECISION_CYCLES_REGISTRY: Dict[str, ModulePermissions] = {
    # ========================================================================
    # DECISION CYCLES MODULE
    # Ownership: linked to account ownership
    # Read: all users can read (client scope) for collaboration
    # Create/Update/Delete: follows account ownership pattern
    # ========================================================================
    'decision_cycles': {
        'create': {
            'admin': 'client',
            'manager': 'team',
            'individual': 'mine',
        },
        'read': {
            'admin': 'client',
            'manager': 'client',
            'individual': 'client',
        },
        'update': {
            'admin': 'client',
            'manager': 'team',
            'individual': 'mine',
        },
        'delete': {
            'admin': 'client',
            'manager': 'team',
            'individual': 'mine',
        },
    }
}