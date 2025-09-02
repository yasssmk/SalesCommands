# backend/end_users/custom_permissions.py

"""
Custom permission mappings for the end_users module.

Note: Les actions bypassed (change_password, grant_superuser) sont gérées
directement dans UserViewSet via l'attribut bypassed_actions.
"""

# Mapping des actions custom vers actions CRUD standard
# Les actions bypassed ne sont PAS dans ce mapping car elles
# gèrent leur propre logique
ACTION_MAPPINGS = {
    # ===== ACTIONS BULK =====
    'bulk_create': 'create',      # Bulk create = create
    'bulk_update': 'update',      # Bulk update = update  
    'bulk_delete': 'delete',      # Bulk delete = delete
    
    # ===== ACTIONS READ-ONLY =====
    'superusers': 'read',         # Listing superusers = read
    'managers': 'read',           # Listing managers = read
    'stats': 'read',              # Viewing stats = read
    'performance': 'read',        # Viewing performance = read
    'team_performance': 'read',   # Team performance = read
    'managed_users_performance': 'read',
    
    # ===== ORGANIZATION/TEAM ACTIONS =====
    'hierarchy': 'read',                    # Viewing hierarchy = read
    'members_performance_summary': 'read',  # Team members summary = read
}


def get_action_mapping(action: str) -> str:
    """
    Get the CRUD mapping for a custom action.
    
    Args:
        action: Custom action name
        
    Returns:
        Mapped CRUD action or original action if no mapping
        
    Note:
        Actions not in ACTION_MAPPINGS are either:
        - Standard CRUD actions (list, retrieve, create, update, destroy)
        - Bypassed actions (handled by ViewSet.bypassed_actions)
        - Unknown actions (will use default permissions)
    """
    return ACTION_MAPPINGS.get(action, action)