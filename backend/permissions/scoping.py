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

from .ownership import (
    resolve_field,
    get_ownership_type,
    resolve_inheritance_chain,
    is_ownership_none,
)
from .checks import get_scope



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
    
    # Try multiple attributes for flexibility
    if hasattr(user, 'client_account_id'):
        return user.client_account_id
    elif hasattr(user, 'client_account'):
        return user.client_account.id
    elif hasattr(user, 'client_id'):
        return user.client_id
    
    return None


def _build_client_filter(module: str, client_id: int) -> Q:
    """
    Build client filter Q object.
    
    Args:
        module: Module name
        client_id: Client ID
        
    Returns:
        Q object for client filtering
    """
    # Resolve the client field for this module
    client_field = resolve_field(module, 'client_account_fk')
    
    if not client_field:
        # Fallback to common field names
        client_field = 'client_account_id'
    
    # Build Q filter
    return Q(**{client_field: client_id})


def _build_team_filter(module: str, user) -> Q:
    """
    Build team filter Q object.
    
    For team scope: user can see records from their team(s).
    
    Args:
        module: Module name
        user: Django User instance
        
    Returns:
        Q object for team filtering
    """
    # Get user's team IDs
    team_ids = _get_user_team_ids(user)
    if not team_ids:
        # No team = treat as mine
        return _build_mine_filter(module, user)
    
    # Build Q filters for team ownership
    q_filters = Q()
    
    # Check owner_team field
    team_field = resolve_field(module, 'owner_team')
    if team_field:
        q_filters |= Q(**{f"{team_field}__in": team_ids})
    
    # Check owner_user's team
    owner_field = resolve_field(module, 'owner_user')
    if owner_field:
        q_filters |= Q(**{f"{owner_field}__team__in": team_ids})
    
    # Check assigned_to_user's team
    assigned_field = resolve_field(module, 'assigned_to_user')
    if assigned_field:
        q_filters |= Q(**{f"{assigned_field}__team__in": team_ids})
    
    # Include own records (team includes mine)
    q_filters |= _build_mine_filter(module, user)
    
    return q_filters


def _build_mine_filter(module: str, user) -> Q:
    """
    Build mine filter Q object.
    
    For mine scope: user can only see their own records.
    
    Args:
        module: Module name
        user: Django User instance
        
    Returns:
        Q object for mine filtering
    """
    user_id = user.id if user else None
    if not user_id:
        return Q(pk__in=[])
    
    # Build Q filters for user ownership
    q_filters = Q()
    
    # Check owner_user field
    owner_field = resolve_field(module, 'owner_user')
    if owner_field:
        q_filters |= Q(**{owner_field: user_id})
    
    # Check created_by field
    created_field = resolve_field(module, 'created_by')
    if created_field:
        q_filters |= Q(**{created_field: user_id})
    
    # Check assigned_to_user field
    assigned_field = resolve_field(module, 'assigned_to_user')
    if assigned_field:
        q_filters |= Q(**{assigned_field: user_id})
    
    # If no ownership fields found, deny access
    if not q_filters:
        return Q(pk__in=[])
    
    return q_filters


def _get_user_team_ids(user) -> List[int]:
    """
    Get all team IDs for a user.
    
    Args:
        user: Django User instance
        
    Returns:
        List of team IDs
    """
    team_ids = []
    
    # Direct team membership
    if hasattr(user, 'team_id'):
        team_ids.append(user.team_id)
    elif hasattr(user, 'team'):
        team_ids.append(user.team.id)
    
    # Managed teams (for managers)
    if hasattr(user, 'managed_teams'):
        team_ids.extend(user.managed_teams.values_list('id', flat=True))
    
    # Organization teams (if user belongs to org)
    if hasattr(user, 'organization') and user.organization:
        if hasattr(user.organization, 'teams'):
            team_ids.extend(user.organization.teams.values_list('id', flat=True))
    
    return list(set(team_ids))  # Remove duplicates


def apply_scope_filter(queryset, module: str, scope: str, user, action: str = 'read'):
    """
    Apply scope filter to a queryset.
    
    Convenience function that builds and applies the Q filter.
    
    Args:
        queryset: Django QuerySet
        module: Module name
        scope: Permission scope
        user: Django User instance
        action: CRUD action
        
    Returns:
        Filtered QuerySet
        
    Example:
        queryset = Account.objects.all()
        filtered = apply_scope_filter(queryset, 'accounts', 'team', request.user)
    """
    q_filter = build_q(module, scope, user, action)
    return queryset.filter(q_filter)