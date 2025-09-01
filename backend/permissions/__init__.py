"""
Centralized Permissions System for Django Backend

This module provides a unified permission system that replaces scattered
role-based logic throughout the application.

Main Components:
- Registry: Permission matrices by module/action/tier
- Checks: Decision engine for permission validation
- Scoping: Query builders for data filtering
- Mixins: DRF integration for views

Usage:
    from permissions import check_permission, ScopedPermission
    
    # Check if user can perform action
    scope = check_permission(user, 'accounts', 'update')
    
    # Use in DRF views
    class AccountViewSet(ScopedQuerysetMixin, viewsets.ModelViewSet):
        permission_classes = [ScopedPermission]
        module = 'accounts'
"""

from .checks import (
    check_permission,
    resolve_tier,
    get_scope,
    has_permission,
)

from .scoping import (
    build_q,
    apply_scope_filter,
)

from .mixins import (
    ScopedPermission,
    ScopedQuerysetMixin,
)

from .config import (
    is_enabled,
    is_module_enabled,
    get_config,
)

from .registry import REGISTRY
from .ownership import OWNERSHIP_MAP

__version__ = '1.0.0'

__all__ = [
    # Core functions
    'check_permission',
    'resolve_tier',
    'get_scope',
    'has_permission',
    
    # Query building
    'build_q',
    'apply_scope_filter',
    
    # DRF integration
    'ScopedPermission',
    'ScopedQuerysetMixin',
    
    # Configuration
    'is_enabled',
    'is_module_enabled',
    'get_config',
    
    # Data structures
    'REGISTRY',
    'OWNERSHIP_MAP',
]

# Module metadata
MODULE_NAME = 'permissions'
SUPPORTED_MODULES = [
    'accounts',
    'contacts', 
    'activities',
    'leads',
    'opportunities',
    'campaign',
    'pipelines',
    'templates',
    'users',
    'products',
]

SUPPORTED_ACTIONS = [
    'create',
    'read',
    'update',
    'delete',
]

SUPPORTED_TIERS = [
    'admin',
    'manager',
    'individual',
]

SUPPORTED_SCOPES = [
    'client',
    'team',
    'mine',
    'none',
]