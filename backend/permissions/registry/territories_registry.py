# backend/permissions/registry/territories_registry.py
"""
Permissions registry for Territories module.

Territories are sales segmentation tools - accessible to all users
but only admins can create/modify/delete them.
"""

from typing import Dict, Literal

Action = Literal['create', 'read', 'update', 'delete']
Tier = Literal['admin', 'manager', 'individual']
Scope = Literal['client', 'team', 'mine', 'none']
ModulePermissions = Dict[Action, Dict[Tier, Scope]]

# ============================================================================
# TERRITORIES MODULES REGISTRY
# ============================================================================

TERRITORIES_REGISTRY: Dict[str, ModulePermissions] = {
    # ========================================================================
    # TERRITORIES MODULE
    # Ownership: user-based (owner)
    # Note: Read access for all, write/delete admin only
    # ========================================================================
    'territories': {
        'create': {
            'admin': 'client',    
            'manager': 'mine',    
            'individual': 'mine', 
        },
        'read': {
            'admin': 'client',    
            'manager': 'client',  
            'individual': 'client'
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