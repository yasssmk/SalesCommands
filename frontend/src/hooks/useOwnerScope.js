// frontend/src/hooks/useOwnerScope.js

import { useState, useCallback, useMemo, useEffect } from 'react';
import { useAuth } from 'hooks/useAuth';

/**
 * Owner scope options
 */
export const OWNER_SCOPES = {
  MINE: 'mine',
  TEAM: 'team',
  ALL: 'all'
};

/**
 * Scope labels for display
 */
export const OWNER_SCOPE_LABELS = {
  [OWNER_SCOPES.MINE]: 'Mine',
  [OWNER_SCOPES.TEAM]: 'My Team',
  [OWNER_SCOPES.ALL]: 'All'
};

/**
 * Hook for managing owner scope filtering
 * 
 * Defaults:
 * - Admin: 'all' (sees everything by default)
 * - Manager: 'team' (sees team + sub-teams)
 * - Individual: 'mine' (sees only own records)
 * 
 * @param {Object} options
 * @param {string} options.storageKey - localStorage key for persistence (e.g., 'territories', 'accounts')
 * @returns {Object} Scope state and handlers
 */
export default function useOwnerScope({ storageKey = 'default' } = {}) {
  const { user } = useAuth();
  
  // ==============================|| ROLE DETECTION ||============================== //
  
  const userRole = useMemo(() => {
    if (!user) return 'individual';
    
    // Check role object (from JWT)
    const role = user.role;
    if (role) {
      if (role.is_admin === true) return 'admin';
      if (role.is_manager === true) return 'manager';
      if (role.is_individual === true) return 'individual';
    }
    
    // Fallback: check is_superuser
    if (user.is_superuser === true) return 'admin';
    
    return 'individual';
  }, [user]);

  // ==============================|| DEFAULT SCOPE BY ROLE ||============================== //
  
  const defaultScope = useMemo(() => {
    switch (userRole) {
      case 'admin':
        return OWNER_SCOPES.ALL;
      case 'manager':
        return OWNER_SCOPES.TEAM;
      default:
        return OWNER_SCOPES.MINE;
    }
  }, [userRole]);

  // ==============================|| VISIBLE OPTIONS BY ROLE ||============================== //
  
  const visibleOptions = useMemo(() => {
  // All users can see all options
  // The difference is only the default value
  return [OWNER_SCOPES.MINE, OWNER_SCOPES.TEAM, OWNER_SCOPES.ALL];
}, []);

  // ==============================|| STATE WITH LOCALSTORAGE ||============================== //
  
  const localStorageKey = `ownerScope_${storageKey}`;
  
  // Initialize state
  const getInitialScope = useCallback(() => {
    if (typeof window === 'undefined') return defaultScope;
    
    try {
      const stored = localStorage.getItem(localStorageKey);
      // Validate stored value is still valid for user's role
      if (stored && visibleOptions.includes(stored)) {
        return stored;
      }
    } catch (e) {
      console.warn('Failed to read from localStorage:', e);
    }
    
    return defaultScope;
  }, [defaultScope, localStorageKey, visibleOptions]);

  const [scope, setScope] = useState(getInitialScope);

  // Re-initialize when user role changes
  useEffect(() => {
    const newInitial = getInitialScope();
    setScope(newInitial);
  }, [userRole, getInitialScope]);

  // Sync to localStorage when scope changes
  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem(localStorageKey, scope);
      } catch (e) {
        console.warn('Failed to write to localStorage:', e);
      }
    }
  }, [scope, localStorageKey]);

  // Reset to default if role changes and current scope is invalid
  useEffect(() => {
    if (!visibleOptions.includes(scope)) {
      setScope(defaultScope);
    }
  }, [visibleOptions, scope, defaultScope]);

  // ==============================|| HANDLERS ||============================== //
  
  const handleScopeChange = useCallback((newScope) => {
    if (visibleOptions.includes(newScope)) {
      setScope(newScope);
    }
  }, [visibleOptions]);

  const resetToDefault = useCallback(() => {
    setScope(defaultScope);
  }, [defaultScope]);

  // ==============================|| API PARAMS ||============================== //
  
  /**
   * Returns params to send to backend API
   * Only includes owner_scope if not 'all'
   */
  const apiParams = useMemo(() => {
    if (scope === OWNER_SCOPES.ALL) {
      return {};
    }
    return { owner_scope: scope };
  }, [scope]);

  // ==============================|| CHIP DISPLAY ||============================== //
  
  /**
   * Returns chip label for active filters display
   * null for 'all' (no chip needed)
   */
  const chipLabel = useMemo(() => {
    if (scope === OWNER_SCOPES.ALL) {
      return null;
    }
    return `Owner: ${OWNER_SCOPE_LABELS[scope] || scope}`;
  }, [scope]);

  /**
   * Check if scope filter is active (not 'all')
   */
  const isFiltered = useMemo(() => {
    return scope !== OWNER_SCOPES.ALL;
  }, [scope]);

  // ==============================|| RETURN ||============================== //
  
  return {
    // State
    scope,
    setScope: handleScopeChange,
    resetToDefault,
    
    // Derived
    defaultScope,
    visibleOptions,
    apiParams,
    chipLabel,
    isFiltered,
    
    // Role info
    userRole,
    showTeamOption: userRole !== 'individual'
  };
}