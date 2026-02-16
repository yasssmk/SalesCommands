"""
Ownership Map for End Users Module

Defines the canonical ownership fields used for scope filtering.
These fields determine how 'mine' and 'team' scopes are applied.

Canonical Keys (exactly 6, no more, no less):
1. client_account_fk: FK to ClientAccount (always required)
2. owner_user: FK to User who owns the resource
3. owner_team: FK to Team that owns the resource
4. created_by: FK to User who created the resource
5. assigned_to_user: FK to User assigned to the resource
6. account_fk: FK to Account (for child entities like Contact)

Special Cases:
- ownership=none: Resources with no ownership (templates, products)
- ownership=account: Resources that inherit from Account (contacts)
- ownership=opportunity: Resources that inherit from Opportunity (pipelines)
"""

from typing import Dict, List, Optional, Literal
import logging

logger = logging.getLogger(__name__)

# Type hints
OwnershipKey = Literal[
    'client_account_fk',
    'owner_user',
    'owner_team',
    'created_by',
    'assigned_to_user',
    'account_fk',
]

# ============================================================================
# OWNERSHIP MAP - 6 Canonical Keys
# ============================================================================

OWNERSHIP_MAP: Dict[str, Dict[OwnershipKey, str]] = {
    
    # ========================================================================
    # END_USERS MODULES
    # ========================================================================
    
    'users': {
        'client_account_fk': 'client_account_id',   # User.client_account_id
        'owner_user': 'id',                         # Self-ownership
        'owner_team': 'team_id',                    # User.team_id
        'created_by': 'created_by_id',              # BaseModelApp.created_by
        'assigned_to_user': '-',                    # Not applicable
        'account_fk': '-',                           # Not applicable
    },
    
    'roles': {
        'client_account_fk': 'client_account_id',   # UserRole.client_account_id
        'owner_user': '-',                          # Roles have no owner
        'owner_team': '-',                          # Roles have no team
        'created_by': 'created_by_id',              # BaseModelApp.created_by
        'assigned_to_user': '-',                    # Not applicable
        'account_fk': '-',                           # Not applicable
    },
    
    'organizations': {
        'client_account_fk': 'client_account_id',   # Organization.client_account_id
        'owner_user': 'manager_id',                 # Organization.manager
        'owner_team': '-',                          # Organizations don't belong to teams
        'created_by': 'created_by_id',              # BaseModelApp.created_by
        'assigned_to_user': 'manager_id',           # Same as owner
        'account_fk': '-',                           # Not applicable
    },
    
    'teams': {
        'client_account_fk': 'organization.client_account_id',  # Via organization
        'owner_user': 'manager_id',                 # Team.manager
        'owner_team': '-',                          # Teams don't belong to other teams
        'created_by': 'created_by_id',              # BaseModelApp.created_by
        'assigned_to_user': 'manager_id',           # Same as owner
        'account_fk': '-',                           # Not applicable
    },
    
    'sales_quotas': {
        'client_account_fk': 'user.client_account_id',  # Via user
        'owner_user': 'user_id',                    # SalesQuota.user
        'owner_team': 'user.team_id',               # Via user's team
        'created_by': 'created_by_id',              # BaseModelApp.created_by
        'assigned_to_user': 'user_id',              # Same as owner
        'account_fk': '-',                           # Not applicable
    },
    
    'sales_plans': {
        'client_account_fk': 'sales_quota.user.client_account_id',  # Via quota->user
        'owner_user': 'sales_quota.user_id',        # Via quota
        'owner_team': 'sales_quota.user.team_id',   # Via quota->user
        'created_by': 'created_by_id',              # BaseModelApp.created_by
        'assigned_to_user': 'sales_quota.user_id',  # Via quota
        'account_fk': '-',                           # Not applicable
    },
    
    'sales_milestones': {
        'client_account_fk': 'plan.sales_quota.user.client_account_id',  # Via plan->quota->user
        'owner_user': 'plan.sales_quota.user_id',   # Via plan->quota
        'owner_team': 'plan.sales_quota.user.team_id',  # Via plan->quota->user
        'created_by': 'created_by_id',              # BaseModelApp.created_by
        'assigned_to_user': 'plan.sales_quota.user_id',  # Via plan->quota
        'account_fk': '-',                           # Not applicable
    },
    
    # ========================================================================
    # SALES & CRM MODULES (existing)
    # ========================================================================
    
    'accounts': {
        'client_account_fk': 'client_id',           # Account.client_id
        'owner_user': 'account_owner_id',                   # Account.owner
        'owner_team': 'account_owner__team_id',     # Via account_owner → team   
        'created_by': '-',              # BaseModelApp.created_by
        'assigned_to_user': '-',                    # Use owner
        'account_fk': '-',                          # Self reference
    },

    'territories': {
        'client_account_fk': 'client_id',           # Territory.client_id
        'owner_user': 'owner_id',                   # Territory.owner
        'owner_team': 'owner__team_id',             # Via owner's team (manager can access team members' territories)
        'created_by': 'created_by_id',              # BaseModel.created_by
        'assigned_to_user': '-',                    # Not applicable
        'account_fk': '-',                          # Not applicable
    },
    
    'contacts': {
        'client_account_fk': 'client_id',           # Direct field from ClientScopeManager.ModelMixin
        'owner_user': 'account__account_owner_id',  # Inherits from account (Django ORM lookup)
        'owner_team': 'account__team_owner_id',     # Inherits from account team
        'created_by': 'created_by_id',              # ModuleBaseModel.created_by
        'assigned_to_user': '-',                    # Not applicable
        'account_fk': 'account_id',                 # Related account
    },
    
    'activities': {
        'client_account_fk': 'client_id',           # UUIDField — name IS 'client_id'
        'owner_user': 'owner',                       # ForeignKey — Python attr name is 'owner' (not 'owner_id')
        'owner_team': 'owner__team_id',             # Traversal — OK (skips field existence check)
        'created_by': 'created_by',                  # ForeignKey — Python attr name is 'created_by' (not 'created_by_id')
        'assigned_to_user': '-',                    # Not applicable (use owner)
        'account_fk': 'account_id',                 # Not used in mine/team scope filtering — kept as-is
    },
    
    'decision_cycles': {
        'client_account_fk': 'client_id',           # DecisionCycle.client_id
        'owner_user': 'owner',                      # DecisionCycle.owner (direct FK)
        'owner_team': 'owner__team_id',             # Via owner → team
        'created_by': 'created_by',                 # ModuleBaseModel.created_by
        'assigned_to_user': '-',                    # Not applicable
        'account_fk': 'account_id',                 # Related account
    },
    
    'campaign': {
        'client_account_fk': 'client_id',           # Campaign.client_id
        'owner_user': 'owner_id',                   # Campaign.owner
        'owner_team': 'team_id',                    # Campaign.team
        'created_by': 'created_by_id',              # BaseModelApp.created_by
        'assigned_to_user': '-',                    # Use owner
        'account_fk': '-',                           # Campaigns are not account-specific
    },
    
    'pipelines': {
        'client_account_fk': 'opportunity.client_id',  # Via opportunity
        'owner_user': 'opportunity.deal_owner_id',  # Via opportunity
        'owner_team': 'opportunity.team_id',        # Via opportunity
        'created_by': 'created_by_id',              # BaseModelApp.created_by
        'assigned_to_user': '-',                    # Use opportunity owner
        'account_fk': 'opportunity_id',             # Points to parent opportunity
    },
    
    'templates': {
        'client_account_fk': 'client_id',           # Template.client_id
        'owner_user': '-',                          # Templates have no owner
        'owner_team': '-',                          # Templates have no team
        'created_by': 'created_by_id',              # BaseModelApp.created_by
        'assigned_to_user': '-',                    # Not applicable
        'account_fk': '-',                           # Not applicable
    },
    
    'products': {
        'client_account_fk': 'client_id',           # Product.client_id
        'owner_user': '-',                          # Products have no owner
        'owner_team': '-',                          # Products have no team
        'created_by': '-',                          # Products may not track creator
        'assigned_to_user': '-',                    # Not applicable
        'account_fk': '-',                           # Not applicable
    },
}

# Ownership Types by Module
OWNERSHIP_TYPES = {
    'users': 'user',              # Self or team based
    'roles': 'none',              # No ownership (admin only)
    'organizations': 'user',       # Manager owns
    'teams': 'user',              # Manager owns
    'sales_quotas': 'user',       # User owns their quotas
    'sales_plans': 'user',        # User owns their plans
    'sales_milestones': 'user',   # User owns their milestones
    'accounts': 'user',           # owner_user, owner_team, created_by
    'territories': 'user',
    'contacts': 'account',        # Inherits from account
    'activities': 'user',         # owner_user, assigned_to_user
    'decision_cycles': 'user',    # Inherits from account
    'leads': 'user',             # assigned_to_user, created_by
    'opportunities': 'user',      # deal_owner (mapped to owner_user)
    'campaign': 'user',           # owner_user
    'pipelines': 'opportunity',   # Inherits from opportunity (buying process)
    'templates': 'none',          # No ownership
    'products': 'none',          # No ownership
}


def resolve_field(module: str, key: str) -> Optional[str]:
    """
    Resolve a canonical key to the actual field name for a module.
    
    Args:
        module: Module name (e.g., 'accounts')
        key: Canonical key (e.g., 'owner_user')
        
    Returns:
        Field name or None if not applicable
        Returns None for '-' entries
    """
    if module not in OWNERSHIP_MAP:
        logger.debug(f"Module '{module}' not found in ownership map")
        return None
    
    field = OWNERSHIP_MAP[module].get(key, '-')
    return field if field != '-' else None


def get_ownership_type(module: str) -> str:
    """
    Get the ownership type for a module.
    
    Args:
        module: Module name
        
    Returns:
        Ownership type ('user', 'account', 'opportunity', 'none')
    """
    return OWNERSHIP_TYPES.get(module, 'none')


def get_parent_module(module: str) -> Optional[str]:
    """
    Get the parent module for inheritance-based ownership.
    
    Args:
        module: Module name
        
    Returns:
        Parent module name or None
    """
    ownership_type = get_ownership_type(module)
    
    if ownership_type == 'account':
        return 'accounts'
    elif ownership_type == 'opportunity':
        return 'opportunities'
    
    return None


def resolve_inheritance_chain(module: str, key: str) -> List[str]:
    """
    Resolve the full inheritance chain for a field.
    
    For modules that inherit ownership (like contacts from accounts),
    this returns the chain of fields to traverse.
    
    Args:
        module: Module name
        key: Canonical key
        
    Returns:
        List of field names to traverse
        
    Example:
        resolve_inheritance_chain('contacts', 'owner_user')
        => ['account', 'owner_id']
    """
    field = resolve_field(module, key)
    if not field or '.' not in field:
        return [field] if field else []
    
    # Split dotted notation
    return field.split('.')


def get_client_field(module: str) -> Optional[str]:
    """
    Get the client account field for a module.
    
    This is a convenience function to quickly get the client field.
    
    Args:
        module: Module name
        
    Returns:
        Client field name or None
    """
    return resolve_field(module, 'client_account_fk')


def get_owner_field(module: str) -> Optional[str]:
    """
    Get the owner user field for a module.
    
    Args:
        module: Module name
        
    Returns:
        Owner field name or None
    """
    return resolve_field(module, 'owner_user')


def get_team_field(module: str) -> Optional[str]:
    """
    Get the team field for a module.
    
    Args:
        module: Module name
        
    Returns:
        Team field name or None
    """
    return resolve_field(module, 'owner_team')


def is_ownership_none(module: str) -> bool:
    """
    Check if a module has no ownership concept.
    
    Modules with no ownership (like roles, templates, products) should
    use client-level scoping for read operations and admin-only for write.
    
    Args:
        module: Module name
        
    Returns:
        True if module has no ownership concept
    """
    return get_ownership_type(module) == 'none'


def is_ownership_inherited(module: str) -> bool:
    """
    Check if a module inherits ownership from another entity.
    
    Args:
        module: Module name
        
    Returns:
        True if ownership is inherited (account or opportunity type)
    """
    ownership_type = get_ownership_type(module)
    return ownership_type in ['account', 'opportunity']


def get_all_owner_fields(module: str) -> List[str]:
    """
    Get all possible owner-related fields for a module.
    
    This includes owner_user, owner_team, created_by, and assigned_to_user.
    
    Args:
        module: Module name
        
    Returns:
        List of field names (excluding None and '-')
    """
    fields = []
    for key in ['owner_user', 'owner_team', 'created_by', 'assigned_to_user']:
        field = resolve_field(module, key)
        if field and field != '-':
            fields.append(field)
    return fields


def has_team_ownership(module: str) -> bool:
    """
    Check if a module supports team-based ownership.
    
    Args:
        module: Module name
        
    Returns:
        True if module has team ownership field
    """
    team_field = get_team_field(module)
    return bool(team_field and team_field != '-')


def has_user_ownership(module: str) -> bool:
    """
    Check if a module supports user-based ownership.
    
    Args:
        module: Module name
        
    Returns:
        True if module has user ownership field
    """
    owner_field = get_owner_field(module)
    return bool(owner_field and owner_field != '-')


def get_fallback_scope(module: str, action: str) -> str:
    """
    Get the fallback scope when ownership fields are missing.
    
    IMPORTANT: For safety, we only fallback to 'client' for READ operations.
    For write operations without ownership, we deny access ('none').
    
    Args:
        module: Module name
        action: CRUD action being performed
        
    Returns:
        Fallback scope ('client' for read, 'none' for write)
    """
    if action in ['read', 'list', 'retrieve']:
        # READ-only fallback to client scope
        logger.debug(f"No ownership fields for {module} - fallback to 'client' for READ")
        return 'client'
    else:
        # Write operations without ownership = deny
        logger.debug(f"No ownership fields for {module} - DENY for {action}")
        return 'none'


# ============================================================================
# DOCUMENTATION
# ============================================================================

"""
OWNERSHIP MAP USAGE:

The ownership map defines how different models relate to users and teams
for the purpose of permission scoping.

The 6 canonical keys are:

1. client_account_fk: The foreign key to ClientAccount (tenant isolation)
2. owner_user: The user who owns this record
3. owner_team: The team that owns this record  
4. created_by: The user who created this record
5. assigned_to_user: The user this record is assigned to
6. account_fk: Foreign key to Account model (for CRM entities)

SCOPE APPLICATION:

- 'mine' scope: Filters by owner_user, created_by, and assigned_to_user
- 'team' scope: Filters by owner_team AND includes 'mine' items
- 'client' scope: No additional filtering beyond tenant

FALLBACK BEHAVIOR:

If a model has no ownership fields defined:
- READ operations: Fallback to 'client' scope (safe default)
- WRITE operations: Deny access ('none' scope)

This ensures we fail safely when ownership is unclear.

SPECIAL CASES:

- Roles/Templates/Products: No ownership ('none' type)
- Contacts: Inherit from Account ('account' type)  
- Pipelines: Inherit from Opportunity ('opportunity' type)
- Teams: Use organization.client_account_id for client filtering
"""

# Export everything
__all__ = [
    'OWNERSHIP_MAP',
    'OWNERSHIP_TYPES',
    'resolve_field',
    'get_ownership_type',
    'get_parent_module',
    'resolve_inheritance_chain',
    'get_client_field',
    'get_owner_field',
    'get_team_field',
    'is_ownership_none',
    'is_ownership_inherited',
    'get_all_owner_fields',
    'has_team_ownership',
    'has_user_ownership',
    'get_fallback_scope',
]