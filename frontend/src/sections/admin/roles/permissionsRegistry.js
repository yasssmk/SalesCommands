// frontend/src/sections/admin/roles/permissionsRegistry.js

/**
 * PERMISSIONS REGISTRY - LOCAL COPY
 * 
 * This is a frontend copy of the backend REGISTRY from backend/permissions/registry/
 * 
 * ⚠️ CRITICAL: This must be kept in sync with the backend REGISTRY.
 * Any divergence will cause inconsistency between what users see and what's actually enforced.
 * 
 * Structure:
 * - 10 modules (accounts, contacts, activities, leads, opportunities, campaign, pipelines, templates, users, products)
 * - 4 actions (create, read, update, delete)
 * - 3 tiers (admin, manager, individual)
 * - 4 scopes (client, team, mine, none)
 * 
 * Scopes meaning:
 * - client: Access to all tenant data
 * - team: Access limited to user's team
 * - mine: Access to personal data only
 * - none: No access (denied)
 */

// ==============================|| TYPE DEFINITIONS ||============================== //

/**
 * @typedef {'create' | 'read' | 'update' | 'delete'} Action
 * @typedef {'admin' | 'manager' | 'individual'} Tier
 * @typedef {'client' | 'team' | 'mine' | 'none'} Scope
 */

// ==============================|| CONSTANTS ||============================== //

export const MODULES = [
  'accounts',
  'contacts',
  'activities',
  'leads',
  'opportunities',
  'campaign',
  'pipelines',
  'templates',
  'users',
  'products'
];

export const ACTIONS = ['create', 'read', 'update', 'delete'];

export const TIERS = ['admin', 'manager', 'individual'];

export const SCOPES = ['client', 'team', 'mine', 'none'];

// ==============================|| PERMISSIONS REGISTRY ||============================== //

/**
 * Main permissions registry
 * Structure: { module: { action: { tier: scope } } }
 */
export const PERMISSIONS_REGISTRY = {
  // ========================================================================
  // ACCOUNTS MODULE
  // Ownership: user-based (owner_user, owner_team, created_by)
  // ========================================================================
  accounts: {
    create: {
      admin: 'client',      // Admin can create any account
      manager: 'team',      // Manager can create for their team
      individual: 'mine'    // Individual can create their own
    },
    read: {
      admin: 'client',      // Admin sees all accounts
      manager: 'client',    // Manager sees all accounts
      individual: 'client'  // Individual sees all accounts
    },
    update: {
      admin: 'client',      // Admin can update any account
      manager: 'team',      // Manager can update team accounts
      individual: 'mine'    // Individual can update own accounts
    },
    delete: {
      admin: 'client',      // Admin can delete any account
      manager: 'none',      // Manager cannot delete accounts
      individual: 'none'    // Individual cannot delete accounts
    }
  },

  // ========================================================================
  // CONTACTS MODULE
  // Ownership: user-based (owner_user, owner_team)
  // ========================================================================
  contacts: {
    create: {
      admin: 'client',
      manager: 'team',
      individual: 'mine'
    },
    read: {
      admin: 'client',
      manager: 'client',
      individual: 'client'
    },
    update: {
      admin: 'client',
      manager: 'team',
      individual: 'mine'
    },
    delete: {
      admin: 'client',
      manager: 'none',
      individual: 'none'
    }
  },

  // ========================================================================
  // ACTIVITIES MODULE
  // Ownership: user-based (owner_user, assigned_to_user)
  // ========================================================================
  activities: {
    create: {
      admin: 'client',
      manager: 'team',
      individual: 'mine'
    },
    read: {
      admin: 'client',
      manager: 'client',
      individual: 'client'
    },
    update: {
      admin: 'client',
      manager: 'team',
      individual: 'mine'
    },
    delete: {
      admin: 'client',
      manager: 'mine',
      individual: 'mine'
    }
  },

  // ========================================================================
  // LEADS MODULE
  // Ownership: user-based (owner_user, owner_team)
  // ========================================================================
  leads: {
    create: {
      admin: 'client',
      manager: 'team',
      individual: 'mine'
    },
    read: {
      admin: 'client',
      manager: 'client',
      individual: 'client'
    },
    update: {
      admin: 'client',
      manager: 'team',
      individual: 'mine'
    },
    delete: {
      admin: 'client',
      manager: 'none',
      individual: 'none'
    }
  },

  // ========================================================================
  // OPPORTUNITIES MODULE
  // Ownership: user-based (owner_user, owner_team)
  // ========================================================================
  opportunities: {
    create: {
      admin: 'client',
      manager: 'team',
      individual: 'mine'
    },
    read: {
      admin: 'client',
      manager: 'client',
      individual: 'client'
    },
    update: {
      admin: 'client',
      manager: 'team',
      individual: 'mine'
    },
    delete: {
      admin: 'client',
      manager: 'none',
      individual: 'none'
    }
  },

  // ========================================================================
  // CAMPAIGN MODULE
  // Ownership: team-based
  // ========================================================================
  campaign: {
    create: {
      admin: 'client',
      manager: 'team',
      individual: 'none'
    },
    read: {
      admin: 'client',
      manager: 'client',
      individual: 'client'
    },
    update: {
      admin: 'client',
      manager: 'team',
      individual: 'none'
    },
    delete: {
      admin: 'client',
      manager: 'none',
      individual: 'none'
    }
  },

  // ========================================================================
  // PIPELINES MODULE
  // Ownership: client-level configuration
  // ========================================================================
  pipelines: {
    create: {
      admin: 'client',
      manager: 'none',
      individual: 'none'
    },
    read: {
      admin: 'client',
      manager: 'client',
      individual: 'client'
    },
    update: {
      admin: 'client',
      manager: 'none',
      individual: 'none'
    },
    delete: {
      admin: 'client',
      manager: 'none',
      individual: 'none'
    }
  },

  // ========================================================================
  // TEMPLATES MODULE
  // Ownership: client-level configuration
  // ========================================================================
  templates: {
    create: {
      admin: 'client',
      manager: 'team',
      individual: 'none'
    },
    read: {
      admin: 'client',
      manager: 'client',
      individual: 'client'
    },
    update: {
      admin: 'client',
      manager: 'team',
      individual: 'none'
    },
    delete: {
      admin: 'client',
      manager: 'none',
      individual: 'none'
    }
  },

  // ========================================================================
  // USERS MODULE
  // Ownership: self-based for profile, admin for management
  // ========================================================================
  users: {
    create: {
      admin: 'client',
      manager: 'none',
      individual: 'none'
    },
    read: {
      admin: 'client',
      manager: 'client',
      individual: 'mine'
    },
    update: {
      admin: 'client',
      manager: 'none',
      individual: 'mine'
    },
    delete: {
      admin: 'client',
      manager: 'none',
      individual: 'none'
    }
  },

  // ========================================================================
  // PRODUCTS MODULE
  // Ownership: client-level catalog
  // ========================================================================
  products: {
    create: {
      admin: 'client',
      manager: 'none',
      individual: 'none'
    },
    read: {
      admin: 'client',
      manager: 'client',
      individual: 'client'
    },
    update: {
      admin: 'client',
      manager: 'none',
      individual: 'none'
    },
    delete: {
      admin: 'client',
      manager: 'none',
      individual: 'none'
    }
  }
};

// ==============================|| HELPER FUNCTIONS ||============================== //

/**
 * Get scope for a specific module/action/tier combination
 * @param {string} module - Module name
 * @param {Action} action - CRUD action
 * @param {Tier} tier - User tier
 * @returns {Scope} Scope level or 'none' if not found
 */
export const getScope = (module, action, tier) => {
  try {
    const modulePerms = PERMISSIONS_REGISTRY[module];
    if (!modulePerms) {
      console.warn(`Module '${module}' not found in registry`);
      return 'none';
    }

    const actionPerms = modulePerms[action];
    if (!actionPerms) {
      console.warn(`Action '${action}' not found for module '${module}'`);
      return 'none';
    }

    const scope = actionPerms[tier];
    if (!scope) {
      console.warn(`Tier '${tier}' not found for module '${module}' action '${action}'`);
      return 'none';
    }

    return scope;
  } catch (error) {
    console.error('Error getting scope:', error);
    return 'none';
  }
};

/**
 * Get all permissions for a specific tier across all modules
 * @param {Tier} tier - User tier
 * @returns {Object} Object with module names as keys and action permissions as values
 */
export const getAllPermissionsForTier = (tier) => {
  const permissions = {};
  
  MODULES.forEach(module => {
    permissions[module] = {};
    ACTIONS.forEach(action => {
      permissions[module][action] = getScope(module, action, tier);
    });
  });
  
  return permissions;
};

/**
 * Check if a tier has any permission for a module
 * @param {string} module - Module name
 * @param {Tier} tier - User tier
 * @returns {boolean} True if tier has at least one non-'none' permission
 */
export const hasModuleAccess = (module, tier) => {
  const modulePerms = PERMISSIONS_REGISTRY[module];
  if (!modulePerms) return false;
  
  return ACTIONS.some(action => {
    const scope = modulePerms[action]?.[tier];
    return scope && scope !== 'none';
  });
};

/**
 * Get readable label for scope
 * @param {Scope} scope - Scope value
 * @returns {string} Human-readable label
 */
export const getScopeLabel = (scope) => {
  const labels = {
    client: 'All',
    team: 'Team',
    mine: 'Mine',
    none: 'None'
  };
  return labels[scope] || scope;
};

/**
 * Get icon name for scope (for use with Ant Design icons)
 * @param {Scope} scope - Scope value
 * @returns {string} Icon name
 */
export const getScopeIcon = (scope) => {
  const icons = {
    client: 'CheckCircleOutlined',
    team: 'TeamOutlined',
    mine: 'UserOutlined',
    none: 'CloseCircleOutlined'
  };
  return icons[scope] || 'QuestionCircleOutlined';
};

/**
 * Get color for scope (for use with Ant Design theme)
 * @param {Scope} scope - Scope value
 * @returns {string} Color key for theme
 */
export const getScopeColor = (scope) => {
  const colors = {
    client: 'success',
    team: 'warning',
    mine: 'info',
    none: 'error'
  };
  return colors[scope] || 'default';
};

// ==============================|| EXPORTS ||============================== //

export default PERMISSIONS_REGISTRY;