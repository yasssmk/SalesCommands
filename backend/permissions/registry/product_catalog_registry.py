# permissions/registry/product_catalog_registry.py
"""
Permissions registry for the ProductCatalog module.

Same matrix as TechCatalog: admin-only writes, tenant-wide reads.
"""

from typing import Dict, Literal


Action = Literal['create', 'read', 'update', 'delete']
Tier = Literal['admin', 'manager', 'individual']
Scope = Literal['client', 'team', 'mine', 'none']
ModulePermissions = Dict[Action, Dict[Tier, Scope]]


PRODUCT_CATALOG_REGISTRY: Dict[str, ModulePermissions] = {
    'product_catalog': {
        'create': {
            'admin':      'client',
            'manager':    'none',
            'individual': 'none',
        },
        'read': {
            'admin':      'client',
            'manager':    'client',
            'individual': 'client',
        },
        'update': {
            'admin':      'client',
            'manager':    'none',
            'individual': 'none',
        },
        'delete': {
            'admin':      'client',
            'manager':    'none',
            'individual': 'none',
        },
    },
}
