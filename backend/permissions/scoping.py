"""
Permission Scoping - Query builders for data filtering

This module builds Django Q objects to filter querysets based on
permission scopes (client/team/mine/none).

CRITICAL RULES:
1. client_account_fk is ALWAYS the first filter (security)
2. mine = owner_user OR created_by OR assigned_to_user
3. team = owner_team OR assigned_to_user.team
4. ownership=none: mine/team → client for READ only
"""

from typing import Optional, List, Union
from django.db.models import Q
from django.contrib.auth import get_user_model

from .ownership import (
    resolve_field,
    get_ownership_type,
    resolve_inheritance_chain,
    is_ownership_none,
)
from .checks import get_scope

# Get User model
User = get_user_model()


def build_q(
    module: str,
    scope: str,
    user,
    action: str = 'read'
) -> Q:
    """
    Build a Django Q object for filtering based on scope.
    
    Args:
        module: Module name (e.g., 'accounts')
        scope: Permission scope ('client', 'team', 'mine', 'none')
        user: Django User instance
        action: CRUD action (needed for ownership=none handling)
        
    Returns:
        Django Q object for queryset filtering
        
    Example:
        q = build_q('accounts', 'team', request.user)
        queryset = Account.objects.filter(q)
    """
    # Handle 'none' scope - return impossible filter
    if scope == 'none':
        return Q(pk__in=[])  # Empty queryset
    
    # Get client_id from user (CRITICAL: always filter by client first)
    client_id = _get_user_client_id(user)
    if not client_id:
        return Q(pk__in=[])  # No client = no access
    
    # Start with client filter (ALWAYS FIRST)
    client_filter = _build_client_filter(module, client_id)
    
    # For 'client' scope, that's all we need
    if scope == 'client':
        return client_filter
    
    # Handle ownership=none modules
    if is_ownership_none(module):
        # For ownership=none, mine/team → client for READ only
        if action == 'read':
            return client_filter
        else:
            # For write operations, strict scope applies
            return Q(pk__in=[]) if scope in ['mine', 'team'] else client_filter
    
    # Build additional filters for team/mine
    if scope == 'team':
        team_filter = _build_team_filter(module, user)
        return client_filter & team_filter
    
    elif scope == 'mine':
        mine_filter = _build_mine_filter(module, user)
        return client_filter & mine_filter
    
    # Default deny
    return Q(pk__in=[])


def _get_user_client_id(user) -> Optional[int]:
    """
    Get client_id from user.
    
    Args:
        user: Django User instance
        
    Returns:
        Client ID or None
    """
    if not user or not user.is_authenticated:
        return None
    
    # Try to get from user's client_account
    if hasattr(user, 'client_account_id'):
        return user.client_account_id
    
    # Try to get from user's client_account relation
    if hasattr(user, 'client_account'):
        return user.client_account.id
    
    return None


def _get_user_team_ids(user) -> List[int]:
    """
    Get all team IDs for a user.
    
    Args:
        user: Django User instance
        
    Returns:
        List of team IDs
    """
    if not user or not user.is_authenticated:
        return []
    
    team_ids = []
    
    # Direct team membership
    if hasattr(user, 'team_id') and user.team_id:
        team_ids.append(user.team_id)
    
    # Multiple teams (if supported)
    if hasattr(user, 'teams'):
        team_ids.extend(user.teams.values_list('id', flat=True))
    
    return list(set(team_ids))  # Remove duplicates


def _build_client_filter(module: str, client_id: int) -> Q:
    """
    Build client-level filter.
    
    CRITICAL: This is always the first filter applied.
    
    Args:
        module: Module name
        client_id: Client ID
        
    Returns:
        Q object for client filtering
    """
    # Get the client_account field for this module
    client_field = resolve_field(module, 'client_account_fk')
    
    if not client_field:
        # Module doesn't have client field? Deny all
        return Q(pk__in=[])
    
    # Build filter with proper field name
    filter_dict = {client_field: client_id}
    return Q(**filter_dict)


def _build_team_filter(module: str, user) -> Q:
    """
    Build team-level filter.
    
    Team scope includes:
    - Resources owned by team (owner_team)
    - Resources assigned to team members (assigned_to_user.team)
    - For inheritance modules, check parent's team
    
    Args:
        module: Module name
        user: Django User instance
        
    Returns:
        Q object for team filtering
    """
    team_ids = _get_user_team_ids(user)
    if not team_ids:
        return Q(pk__in=[])  # No team = no team access
    
    filters = []
    
    # Check owner_team
    owner_team_field = resolve_field(module, 'owner_team')
    if owner_team_field and owner_team_field != '-':
        filters.append(Q(**{f"{owner_team_field}__in": team_ids}))
    
    # Check assigned_to_user's team
    assigned_field = resolve_field(module, 'assigned_to_user')
    if assigned_field and assigned_field != '-':
        filters.append(Q(**{f"{assigned_field}__team_id__in": team_ids}))
    
    # Handle inheritance cases
    ownership_type = get_ownership_type(module)
    
    if ownership_type == 'account':
        # For contacts, check account's team
        account_field = resolve_field(module, 'account_fk')
        if account_field:
            filters.append(Q(**{f"{account_field}__team_id__in": team_ids}))
    
    elif ownership_type == 'opportunity':
        # For pipelines/buying process, check opportunity's team
        account_field = resolve_field(module, 'account_fk')  # Points to opportunity
        if account_field:
            filters.append(Q(**{f"{account_field}__team_id__in": team_ids}))
    
    # Combine all filters with OR
    if filters:
        combined = filters[0]
        for f in filters[1:]:
            combined |= f
        return combined
    
    return Q(pk__in=[])


def _build_mine_filter(module: str, user) -> Q:
    """
    Build mine-level filter.
    
    Mine scope includes:
    - Resources I own (owner_user)
    - Resources I created (created_by)
    - Resources assigned to me (assigned_to_user)
    
    Args:
        module: Module name
        user: Django User instance
        
    Returns:
        Q object for mine filtering
    """
    if not user or not user.is_authenticated:
        return Q(pk__in=[])
    
    filters = []
    
    # Check owner_user
    owner_field = resolve_field(module, 'owner_user')
    if owner_field and owner_field != '-':
        # Handle special case for users module (self-ownership)
        if module == 'users' and owner_field == 'id':
            filters.append(Q(id=user.id))
        else:
            filters.append(Q(**{owner_field: user.id}))
    
    # Check created_by
    created_by_field = resolve_field(module, 'created_by')
    if created_by_field and created_by_field != '-':
        filters.append(Q(**{created_by_field: user.id}))
    
    # Check assigned_to_user
    assigned_field = resolve_field(module, 'assigned_to_user')
    if assigned_field and assigned_field != '-':
        filters.append(Q(**{assigned_field: user.id}))
    
    # Handle inheritance cases
    ownership_type = get_ownership_type(module)
    
    if ownership_type == 'account':
        # For contacts, check if I own the account
        account_field = resolve_field(module, 'account_fk')
        if account_field:
            filters.append(Q(**{f"{account_field}__owner_id": user.id}))
            filters.append(Q(**{f"{account_field}__created_by_id": user.id}))
    
    elif ownership_type == 'opportunity':
        # For pipelines/buying process, check if I own the opportunity
        account_field = resolve_field(module, 'account_fk')  # Points to opportunity
        if account_field:
            filters.append(Q(**{f"{account_field}__deal_owner_id": user.id}))
            filters.append(Q(**{f"{account_field}__created_by_id": user.id}))
    
    # Combine all filters with OR
    if filters:
        combined = filters[0]
        for f in filters[1:]:
            combined |= f
        return combined
    
    return Q(pk__in=[])


def apply_scope_filter(
    queryset,
    module: str,
    action: str,
    user,
    scope: Optional[str] = None
):
    """
    Apply scope filtering to a queryset.
    
    This is a convenience function that combines permission checking
    and query building.
    
    Args:
        queryset: Django QuerySet to filter
        module: Module name
        action: CRUD action
        user: Django User instance
        scope: Optional - override scope (for testing)
        
    Returns:
        Filtered QuerySet
        
    Example:
        queryset = Account.objects.all()
        filtered = apply_scope_filter(queryset, 'accounts', 'read', request.user)
    """
    # Get scope if not provided
    if scope is None:
        from .checks import check_permission
        scope = check_permission(user, module, action)
    
    # Build Q filter
    q_filter = build_q(module, scope, user, action)
    
    # Apply filter
    return queryset.filter(q_filter)


def get_accessible_ids(
    model_class,
    module: str,
    action: str,
    user,
    limit: Optional[int] = None
) -> List[int]:
    """
    Get list of accessible object IDs for a user.
    
    Useful for prefetching or validation.
    
    Args:
        model_class: Django Model class
        module: Module name
        action: CRUD action
        user: Django User instance
        limit: Optional - limit number of IDs returned
        
    Returns:
        List of accessible object IDs
    """
    queryset = model_class.objects.all()
    filtered = apply_scope_filter(queryset, module, action, user)
    
    if limit:
        filtered = filtered[:limit]
    
    return list(filtered.values_list('id', flat=True))


def explain_scope_filter(
    module: str,
    scope: str,
    user,
    action: str = 'read'
) -> str:
    """
    Explain what a scope filter will do in human-readable format.
    
    Useful for debugging and UI display.
    
    Args:
        module: Module name
        scope: Permission scope
        user: Django User instance
        action: CRUD action
        
    Returns:
        Human-readable explanation
    """
    if scope == 'none':
        return "No access - all records filtered out"
    
    if scope == 'client':
        return f"Access to all {module} in your client organization"
    
    if is_ownership_none(module) and action == 'read':
        return f"Access to all {module} (global resources)"
    
    if scope == 'team':
        team_ids = _get_user_team_ids(user)
        return f"Access to {module} owned by or assigned to your team(s): {team_ids}"
    
    if scope == 'mine':
        return f"Access to {module} you own, created, or are assigned to"
    
    return "Unknown scope"