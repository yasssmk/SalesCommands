from typing import Dict, Literal

Action = Literal['create', 'read', 'update', 'delete']
Tier = Literal['admin', 'manager', 'individual']
Scope = Literal['client', 'team', 'mine', 'none']
ModulePermissions = Dict[Action, Dict[Tier, Scope]]
# ============================================================================
# END USERS MODULES REGISTRY
# ============================================================================

END_USERS_REGISTRY: Dict[str, ModulePermissions] = {
 # ========================================================================
    # USERS MODULE (end_users)
    # Ownership: user-based (self or managed users)
    # ========================================================================
    'users': {
        'create': {
            'admin': 'client',      # Admin can create any user
            'manager': 'none',      # Manager cannot create users
            'individual': 'none',   # Individual cannot create users
        },
        'read': {
            'admin': 'client',      # Admin sees all users
            'manager': 'client',      # Manager sees all users
            'individual': 'client',   # Individual sees all users
        },
        'update': {
            'admin': 'client',      # Admin can update any user
            'manager': 'mine',      # Manager can update team users
            'individual': 'mine',   # Individual can update own profile
        },
        'delete': {
            'admin': 'client',      # Admin can delete any user
            'manager': 'none',      # Manager cannot delete users
            'individual': 'none',   # Individual cannot delete users
        },
    },

    # ========================================================================
    # ROLES MODULE - Role and permission management
    # ========================================================================
    'roles': {
        'create': {
            'admin': 'client',      # Only admin can create roles
            'manager': 'none',       # Managers cannot create roles
            'individual': 'none',    # Individuals cannot create roles
        },
        'read': {
            'admin': 'client',      # Admin sees all roles
            'manager': 'client',     # Managers can view all roles
            'individual': 'client',  # Everyone can see available roles
        },
        'update': {
            'admin': 'client',      # Only admin can modify roles
            'manager': 'none',       # Managers cannot modify roles
            'individual': 'none',    # Individuals cannot modify roles
        },
        'delete': {
            'admin': 'client',      # Only admin can delete roles
            'manager': 'none',       # Managers cannot delete roles
            'individual': 'none',    # Individuals cannot delete roles
        },
    },

    # ========================================================================
    # ORGANIZATIONS MODULE - Organizational units within tenant
    # ========================================================================
    'organizations': {
        'create': {
            'admin': 'client',      # Admin can create organizations
            'manager': 'none',       # Managers cannot create organizations
            'individual': 'none',    # Individuals cannot create organizations
        },
        'read': {
            'admin': 'client',      # Admin sees all organizations
            'manager': 'client',     # Managers see all organizations
            'individual': 'client',  # Everyone can see organizations
        },
        'update': {
            'admin': 'client',      # Admin can update any organization
            'manager': 'none',       # Manager cannot update  organization
            'individual': 'none',    # Individuals cannot update organizations
        },
        'delete': {
            'admin': 'client',      # Admin can delete organizations
            'manager': 'none',       # Managers cannot delete organizations
            'individual': 'none',    # Individuals cannot delete organizations
        },
    },

    # ========================================================================
    # TEAMS MODULE - Team management within organizations
    # ========================================================================
    'teams': {
        'create': {
            'admin': 'client',      # Admin can create any team
            'manager': 'mine',       # Manager can create sub-teams
            'individual': 'none',    # Individuals cannot create teams
        },
        'read': {
            'admin': 'client',      # Admin sees all teams
            'manager': 'client',     # Managers see all teams
            'individual': 'team',    # Individuals see their team(s)
        },
        'update': {
            'admin': 'client',      # Admin can update any team
            'manager': 'none',       # Manager cannot update teams
            'individual': 'none',    # Individuals cannot update teams
        },
        'delete': {
            'admin': 'client',      # Admin can delete teams
            'manager': 'none',       # Managers cannot delete teams
            'individual': 'none',    # Individuals cannot delete teams
        },
    },
    
    # ========================================================================
    # SALES_QUOTAS MODULE - Sales quota management
    # ========================================================================
    'sales_quotas': {
        'create': {
            'admin': 'client',      # Admin can create any quota
            'manager': 'team',       # Manager can create team quotas
            'individual': 'none',    # Individuals cannot create quotas
        },
        'read': {
            'admin': 'client',      # Admin sees all quotas
            'manager': 'team',       # Manager sees team quotas
            'individual': 'mine',    # Individuals see own quotas
        },
        'update': {
            'admin': 'client',      # Admin can update any quota
            'manager': 'team',       # Manager can update team quotas
            'individual': 'none',    # Individuals cannot update quotas
        },
        'delete': {
            'admin': 'client',      # Admin can delete quotas
            'manager': 'none',       # Manager cannot delete quotas
            'individual': 'none',    # Individuals cannot delete quotas
        },
    },
    
    # ========================================================================
    # SALES_PLANS MODULE - Sales planning and strategy
    # ========================================================================
    'sales_plans': {
        'create': {
            'admin': 'client',      # Admin can create any plan
            'manager': 'team',       # Manager can create team plans
            'individual': 'mine',    # Individuals can create own plans
        },
        'read': {
            'admin': 'client',      # Admin sees all plans
            'manager': 'team',       # Manager sees team plans
            'individual': 'mine',    # Individuals see own plans
        },
        'update': {
            'admin': 'client',      # Admin can update any plan
            'manager': 'team',       # Manager can update team plans
            'individual': 'mine',    # Individuals can update own plans
        },
        'delete': {
            'admin': 'client',      # Admin can delete plans
            'manager': 'team',       # Manager can delete team plans
            'individual': 'mine',    # Individuals can delete own plans
        },
    },
    
    # ========================================================================
    # SALES_MILESTONES MODULE - Sales milestone tracking
    # ========================================================================
    'sales_milestones': {
        'create': {
            'admin': 'client',      # Admin can create any milestone
            'manager': 'team',       # Manager can create team milestones
            'individual': 'mine',    # Individuals can create own milestones
        },
        'read': {
            'admin': 'client',      # Admin sees all milestones
            'manager': 'team',       # Manager sees team milestones
            'individual': 'mine',    # Individuals see own milestones
        },
        'update': {
            'admin': 'client',      # Admin can update any milestone
            'manager': 'team',       # Manager can update team milestones
            'individual': 'mine',    # Individuals can update own milestones
        },
        'delete': {
            'admin': 'client',      # Admin can delete milestones
            'manager': 'team',       # Manager can delete team milestones
            'individual': 'mine',    # Individuals can delete own milestones
        },
    },

}