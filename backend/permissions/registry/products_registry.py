from typing import Dict, Literal

Action = Literal['create', 'read', 'update', 'delete']
Tier = Literal['admin', 'manager', 'individual']
Scope = Literal['client', 'team', 'mine', 'none']
ModulePermissions = Dict[Action, Dict[Tier, Scope]]

# ============================================================================
# PRODUCTS MODULES REGISTRY
# ============================================================================

PRODUCTS_REGISTRY: Dict[str, ModulePermissions] = {
    # ========================================================================
    # Product module 
    # Ownership: none
    # ========================================================================
    'products' : {
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
    }
}