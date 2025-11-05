# # backend/end_users/custom_permissions.py

# """
# Custom permission mappings for the end_users module.

# Note: Les actions bypassed (change_password, grant_superuser) sont gérées
# directement dans UserViewSet via l'attribut bypassed_actions.
# """

# from permissions.constants import normalize_action

# # Mapping des actions custom vers actions CRUD standard
# # Les actions bypassed ne sont PAS dans ce mapping car elles
# # gèrent leur propre logique
# ACTION_MAPPINGS = {
#     # ===== ACTIONS BULK =====
#     'bulk_create': 'create',      # Bulk create = create
#     'bulk_update': 'update',      # Bulk update = update  
#     'bulk_delete': 'delete',      # Bulk delete = delete
    
#     # ===== ACTIONS READ-ONLY =====
#     'superusers': 'read',         # Listing superusers = read
#     'managers': 'read',           # Listing managers = read
#     'stats': 'read',              # Viewing stats = read
#     'performance': 'read',        # Viewing performance = read
#     'team_performance': 'read',   # Team performance = read
#     'managed_users_performance': 'read',
    
#     # ===== ORGANIZATION/TEAM ACTIONS =====
#     'hierarchy': 'read',                    # Viewing hierarchy = read
#     'members_performance_summary': 'read',  # Team members summary = read
# }


# def get_action_mapping(action: str) -> str:
#     """
#     Get the CRUD mapping for an action.
    
#     Priority order:
#     1. Custom actions (bulk_*, stats, performance, etc) → ACTION_MAPPINGS
#     2. Standard CRUD actions (list, retrieve, patch, etc) → normalize_action()
    
#     Args:
#         action: Action name (custom or standard)
        
#     Returns:
#         Mapped CRUD action ('create'|'read'|'update'|'delete')
#     """
#     # Check custom mappings first
#     if action in ACTION_MAPPINGS:
#         return ACTION_MAPPINGS[action]
    
#     # Fallback to centralized normalization for standard CRUD actions
#     return normalize_action(action)