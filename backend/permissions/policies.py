"""
Permission Policies - Reusable scope profiles and action policy resolution

This module defines reusable permission patterns for common scenarios
like "self_only" (users can only modify themselves) or "admin_only_client"
(admins can access everything in their tenant).

These policies replace the old "bypassed_actions" pattern with declarative
configuration that still goes through the central permission system.
"""

from typing import Dict, Any, Optional, Tuple, List
from django.db.models import Q
from django.contrib.auth import get_user_model
from .constants import ACTION_TO_CRUD
from .compat import get_auth_ctx, AuthContext

import logging

logger = logging.getLogger(__name__)


# Type definitions
ActionPolicy = Dict[str, Any]  # {"crud": "update", "scope": "self_only", "tier": "admin"}
ScopeProfile = str  # "self_only", "admin_only_client", etc.


# =============================================================================
# SCOPE PROFILES - Reusable permission patterns
# =============================================================================

class ScopeProfiles:
    """
    Registry of reusable scope profiles.
    
    Each profile defines a specific permission pattern that can be
    referenced by name in action_policies.
    """
    
    SELF_ONLY = 'self_only'
    ADMIN_ONLY_CLIENT = 'admin_only_client'
    TEAM_ONLY = 'team_only'
    OWNER_ONLY = 'owner_only'
    PUBLIC_READ = 'public_read'
    DENY_ALL = 'deny_all'


def resolve_scope_profile(
    profile: str,
    request,
    module: str,
    action: str
) -> Tuple[Optional[str], Optional[Q]]:
    """
    Resolve a named scope profile to actual scope and Q filter.
    
    Args:
        profile: Profile name (e.g., 'self_only')
        request: Django/DRF request
        module: Module name being accessed
        action: CRUD action being performed
        
    Returns:
        Tuple of (scope_name, q_filter)
        - scope_name: 'client'|'team'|'mine'|'none'
        - q_filter: Q object for queryset filtering
    """
    ctx = get_auth_ctx(request)
    user = request.user if hasattr(request, 'user') else None
    
    # =========================================================================
    # SELF_ONLY - User can only access their own object
    # =========================================================================
    if profile == ScopeProfiles.SELF_ONLY:
        if not user or not user.is_authenticated:
            return ('none', Q(pk__in=[]))
        
        # For user module, filter by user's own ID
        if module == 'users':
            return ('mine', Q(pk=user.pk))
        
        # For other modules, filter by owner/created_by
        return ('mine', Q(owner=user) | Q(created_by=user))
    
    # =========================================================================
    # ADMIN_ONLY_CLIENT - Admin tier required, client-wide scope
    # =========================================================================
    elif profile == ScopeProfiles.ADMIN_ONLY_CLIENT:
        if ctx.tier != 'admin':
            return ('none', Q(pk__in=[]))
        
        # Admin can access everything in their client
        if ctx.client_id:
            return ('client', Q(client_account_id=ctx.client_id))
        
        return ('none', Q(pk__in=[]))
    
    # =========================================================================
    # TEAM_ONLY - Team-level access only
    # =========================================================================
    elif profile == ScopeProfiles.TEAM_ONLY:
        if not ctx.teams:
            return ('none', Q(pk__in=[]))
        
        # Build team filter
        team_q = Q()
        for team_id in ctx.teams:
            team_q |= Q(team_id=team_id) | Q(owner__team_id=team_id)
        
        return ('team', team_q)
    
    # =========================================================================
    # OWNER_ONLY - Must be the direct owner
    # =========================================================================
    elif profile == ScopeProfiles.OWNER_ONLY:
        if not user or not user.is_authenticated:
            return ('none', Q(pk__in=[]))
        
        return ('mine', Q(owner=user))
    
    # =========================================================================
    # PUBLIC_READ - Anyone authenticated can read
    # =========================================================================
    elif profile == ScopeProfiles.PUBLIC_READ:
        if action == 'read' and ctx.is_authenticated:
            if ctx.client_id:
                return ('client', Q(client_account_id=ctx.client_id))
        
        return ('none', Q(pk__in=[]))
    
    # =========================================================================
    # DENY_ALL - Always deny
    # =========================================================================
    elif profile == ScopeProfiles.DENY_ALL:
        return ('none', Q(pk__in=[]))
    
    # Unknown profile - deny by default
    logger.warning(f"Unknown scope profile: {profile}")
    return ('none', Q(pk__in=[]))


def resolve_action_policy(
    action_policies: Dict[str, ActionPolicy],
    action: str,
    request,
    module: str
) -> Tuple[str, str, Optional[str]]:
    """
    Resolve action policy for a specific action.
    
    This function checks if there's a custom policy for the action
    and returns the appropriate CRUD mapping, tier requirement, and scope.
    
    Args:
        action_policies: Dictionary of action policies from ViewSet
        action: DRF action name (e.g., 'change_password')
        request: Django/DRF request
        module: Module name
        
    Returns:
        Tuple of (crud_action, required_tier, scope)
        - crud_action: 'create'|'read'|'update'|'delete'
        - required_tier: 'admin'|'manager'|'individual'|None
        - scope: 'client'|'team'|'mine'|'none'|profile_name
        
    Example:
        action_policies = {
            "change_password": {"crud": "update", "scope": "self_only"},
            "grant_superuser": {"crud": "update", "tier": "admin"},
        }
    """
    
    # Check if there's a custom policy for this action
    if action_policies and action in action_policies:
        policy = action_policies[action]
        
        # Extract CRUD action (required)
        crud_action = policy.get('crud')
        if not crud_action:
            logger.error(f"Action policy for '{action}' missing 'crud' key")
            crud_action = ACTION_TO_CRUD.get(action, 'read')
        
        # Extract required tier (optional)
        required_tier = policy.get('tier')
        
        # Extract scope (optional, can be profile name or standard scope)
        scope = policy.get('scope')
        
        return (crud_action, required_tier, scope)
    
    # No custom policy - use defaults
    crud_action = ACTION_TO_CRUD.get(action, 'read')
    return (crud_action, None, None)


def check_action_policy_permission(
    action_policies: Dict[str, ActionPolicy],
    action: str,
    request,
    module: str
) -> Tuple[bool, Optional[str]]:
    """
    Check if an action is permitted based on action policies.
    
    Args:
        action_policies: Dictionary of action policies
        action: DRF action name
        request: Django/DRF request
        module: Module name
        
    Returns:
        Tuple of (is_permitted, scope)
        - is_permitted: True if action is allowed
        - scope: Effective scope if permitted
    """
    # Resolve the policy
    crud_action, required_tier, scope_spec = resolve_action_policy(
        action_policies, action, request, module
    )
    
    ctx = get_auth_ctx(request)
    
    # Check tier requirement first
    if required_tier:
        # CRITICAL: Calculate effective tier from role flags (NOT from ctx.tier which is legacy)
        # Same logic as check_permission() in checks.py
        has_admin = ctx.is_superuser  # Superuser always admin
        has_manager = False
        has_individual = False
        
        # Check all roles for flags (union/additive)
        for role in ctx.roles:
            if isinstance(role, dict):
                if role.get('is_admin'):
                    has_admin = True
                if role.get('is_manager'):
                    has_manager = True
                if role.get('is_individual'):
                    has_individual = True
        
        # Determine effective tier (highest privilege wins)
        if has_admin:
            effective_tier = 'admin'
        elif has_manager:
            effective_tier = 'manager'
        elif has_individual:
            effective_tier = 'individual'
        else:
            # No valid tier = deny
            logger.warning(f"Action '{action}' requires tier '{required_tier}', but user has no valid tier")
            return (False, 'none')
        
        logger.debug(f"[TIER CHECK] Action '{action}' requires tier '{required_tier}', user has effective tier '{effective_tier}'")
    
        # Tier hierarchy: admin > manager > individual
        tier_levels = {'admin': 3, 'manager': 2, 'individual': 1}
        
        if tier_levels.get(effective_tier, 0) < tier_levels.get(required_tier, 999):
            logger.debug(f"Action '{action}' DENIED: requires tier '{required_tier}', user has '{effective_tier}'")
            return (False, 'none')
    
    # If scope is a profile name, resolve it
    if scope_spec in [
        ScopeProfiles.SELF_ONLY,
        ScopeProfiles.ADMIN_ONLY_CLIENT,
        ScopeProfiles.TEAM_ONLY,
        ScopeProfiles.OWNER_ONLY,
        ScopeProfiles.PUBLIC_READ,
        ScopeProfiles.DENY_ALL,
    ]:
        resolved_scope, _ = resolve_scope_profile(
            scope_spec, request, module, crud_action
        )
        return (resolved_scope != 'none', resolved_scope)
    
    # Standard scope or None (fall back to registry)
    if scope_spec in ['client', 'team', 'mine', 'none']:
        return (scope_spec != 'none', scope_spec)
    
    # No scope specified - will fall back to registry
    return (True, None)


def build_policy_q_filter(
    profile: str,
    request,
    module: str,
    action: str
) -> Q:
    """
    Build a Q filter for a scope profile.
    
    This is a convenience function that extracts just the Q filter
    from resolve_scope_profile.
    
    Args:
        profile: Profile name
        request: Django/DRF request
        module: Module name
        action: CRUD action
        
    Returns:
        Q object for filtering
    """
    _, q_filter = resolve_scope_profile(profile, request, module, action)
    return q_filter or Q(pk__in=[])


def validate_action_policies(action_policies: Dict[str, ActionPolicy]) -> List[str]:
    """
    Validate action policies configuration.
    
    Args:
        action_policies: Dictionary to validate
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    if not isinstance(action_policies, dict):
        return ["action_policies must be a dictionary"]
    
    valid_crud = {'create', 'read', 'update', 'delete'}
    valid_tiers = {'admin', 'manager', 'individual'}
    valid_scopes = {
        'client', 'team', 'mine', 'none',
        ScopeProfiles.SELF_ONLY,
        ScopeProfiles.ADMIN_ONLY_CLIENT,
        ScopeProfiles.TEAM_ONLY,
        ScopeProfiles.OWNER_ONLY,
        ScopeProfiles.PUBLIC_READ,
        ScopeProfiles.DENY_ALL,
    }
    
    for action_name, policy in action_policies.items():
        if not isinstance(policy, dict):
            errors.append(f"Policy for '{action_name}' must be a dictionary")
            continue
        
        # Check CRUD (required)
        if 'crud' not in policy:
            errors.append(f"Policy for '{action_name}' missing required 'crud' key")
        elif policy['crud'] not in valid_crud:
            errors.append(f"Invalid crud value for '{action_name}': {policy['crud']}")
        
        # Check tier (optional)
        if 'tier' in policy and policy['tier'] not in valid_tiers:
            errors.append(f"Invalid tier value for '{action_name}': {policy['tier']}")
        
        # Check scope (optional)
        if 'scope' in policy and policy['scope'] not in valid_scopes:
            errors.append(f"Invalid scope value for '{action_name}': {policy['scope']}")
    
    return errors