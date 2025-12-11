# backend/permissions/owner_scope.py
"""
Owner Scope Filtering Mixin

Provides reusable owner_scope query param filtering for ViewSets.
Reuses OWNERSHIP_MAP for field resolution.

Supports: mine, team (with sub-teams), all
"""

from django.db.models import Q
from core.logging import get_logger
from .ownership import get_owner_field

logger = get_logger(__name__)


def get_all_descendant_team_ids(team_ids, client_id):
    """
    Get all descendant team IDs recursively for given team IDs.
    
    Args:
        team_ids: List/set of team UUIDs
        client_id: Client account UUID for scoping
        
    Returns:
        Set of all team IDs (input + all descendants)
    """
    from end_users.models import Team
    
    if not team_ids:
        return set()
    
    # Convert to set of strings
    all_team_ids = set(str(tid) for tid in team_ids)
    
    # Load all teams for this client (single query)
    teams = list(
        Team.objects.filter(client_account_id=client_id)
        .values('id', 'parent_team_id')
    )
    
    # Build parent -> children mapping
    children_map = {}
    for team in teams:
        team_id = str(team['id'])
        parent_id = str(team['parent_team_id']) if team['parent_team_id'] else None
        
        if parent_id:
            if parent_id not in children_map:
                children_map[parent_id] = []
            children_map[parent_id].append(team_id)
    
    # Recursively collect all descendants
    def collect_descendants(team_id):
        descendants = set()
        if team_id in children_map:
            for child_id in children_map[team_id]:
                descendants.add(child_id)
                descendants.update(collect_descendants(child_id))
        return descendants
    
    # Collect descendants for all input teams
    result = set(all_team_ids)
    for team_id in list(all_team_ids):
        result.update(collect_descendants(team_id))
    
    return result


def get_team_member_ids(team_ids, client_id):
    """
    Get all user IDs who are members of the given teams.
    
    Args:
        team_ids: Set of team UUIDs
        client_id: Client account UUID
        
    Returns:
        Set of user IDs (as strings)
    """
    from end_users.models import User
    
    if not team_ids:
        return set()
    
    user_ids = User.objects.filter(
        client_account_id=client_id,
        team_id__in=team_ids
    ).values_list('id', flat=True)
    
    return set(str(uid) for uid in user_ids)


class OwnerScopeMixin:
    """
    Mixin to add owner_scope filtering to ViewSets.
    
    Query param: owner_scope=mine|team|all
    
    Uses OWNERSHIP_MAP to resolve the owner field for the module.
    Requires 'module' attribute to be set on the ViewSet.
    """
    
    def apply_owner_scope_filter(self, queryset):
        """
        Apply owner_scope filtering based on query param.
        
        Args:
            queryset: The queryset to filter
            
        Returns:
            Filtered queryset
        """
        owner_scope = self.request.query_params.get('owner_scope')
        
        # No filter if not specified or 'all'
        if not owner_scope or owner_scope == 'all':
            return queryset
        
        # Get module name from ViewSet
        module = getattr(self, 'module', None)
        if not module:
            logger.warning("owner_scope_no_module", extra={
                'view': self.__class__.__name__
            })
            return queryset
        
        # Get owner field from OWNERSHIP_MAP
        owner_field = get_owner_field(module)
        if not owner_field:
            logger.warning("owner_scope_no_owner_field", extra={
                'view': self.__class__.__name__,
                'biz_module': module
            })
            return queryset
        
        # Get user info
        user = self.request.user
        if not user or not user.is_authenticated:
            return queryset
        
        user_id = str(user.id)
        client_id = getattr(user, 'client_account_id', None)
        
        if not client_id:
            return queryset
        
        logger.debug("apply_owner_scope", extra={
            'scope': owner_scope,
            'field': owner_field,
            'user_id': user_id,
            'biz_module': module
        })
        
        # Normalize field name (remove _id suffix if present for filter)
        filter_field = owner_field.rstrip('_id') + '_id' if not owner_field.endswith('_id') else owner_field
        
        if owner_scope == 'mine':
            # Filter by current user only
            return queryset.filter(**{filter_field: user_id})
        
        elif owner_scope == 'team':
            # Filter by all users in user's teams + sub-teams
            
            # Get user's direct team
            user_team_ids = set()
            if hasattr(user, 'team_id') and user.team_id:
                user_team_ids.add(str(user.team_id))
            
            if not user_team_ids:
                # User has no team, fallback to 'mine'
                logger.debug("owner_scope_team_fallback_to_mine", extra={
                    'user_id': user_id,
                    'reason': 'no_team'
                })
                return queryset.filter(**{filter_field: user_id})
            
            # Get all descendant teams
            all_team_ids = get_all_descendant_team_ids(user_team_ids, client_id)
            
            # Get all members of those teams
            member_ids = get_team_member_ids(all_team_ids, client_id)
            
            # Include the current user even if not counted
            member_ids.add(user_id)
            
            # Filter queryset
            return queryset.filter(**{f"{filter_field}__in": member_ids})
        
        # Unknown scope, return unfiltered
        return queryset