// frontend/src/hooks/useTerritoryFilters.js

import { useState, useCallback, useMemo } from 'react';

/**
 * Default empty filters object
 * Structure matches backend API query params
 */
const DEFAULT_FILTERS = {
  type: '',
  classification: '',
  account_scope: '',      // 'mine' | 'team' | '' (all)
  account_owner: null     // User object or null (only used if account_scope is empty)
};

/**
 * Hook for managing territory filters state
 * 
 * Phase 1: Client-side only, no persistence
 * Future: Sync with territory filter_definition from backend
 * 
 * @param {Object} initialFilters - Optional initial filter values
 * @returns {Object} Filter state and handlers
 */
export default function useTerritoryFilters(initialFilters = {}) {
  
  // ==============================|| STATE ||============================== //
  
  const [filters, setFilters] = useState({
    ...DEFAULT_FILTERS,
    ...initialFilters
  });

  // Temporary filters (before Apply)
  const [pendingFilters, setPendingFilters] = useState({
    ...DEFAULT_FILTERS,
    ...initialFilters
  });

  // ==============================|| COMPUTED ||============================== //

 /**
 * Count of active (non-empty) filters
 * Note: account_scope and account_owner are mutually exclusive (count as 1 max)
 */
const activeFiltersCount = useMemo(() => {
  let count = 0;
  const hasAccountScope = filters.account_scope && filters.account_scope !== '';
  
  Object.entries(filters).forEach(([key, value]) => {
    // Skip account_owner if account_scope is active (they're mutually exclusive)
    if (key === 'account_owner' && hasAccountScope) {
      return;
    }
    
    if (Array.isArray(value) && value.length > 0) {
      count++;
    } else if (value !== '' && value !== null && value !== undefined) {
      count++;
    }
  });
  
  return count;
}, [filters]);

  /**
   * Check if any filter is active
   */
  const hasActiveFilters = useMemo(() => {
    return activeFiltersCount > 0;
  }, [activeFiltersCount]);

  /**
   * Check if pending filters differ from applied filters
   * Compares by value, handling objects (like account_owner) by their ID
   */
  const hasPendingChanges = useMemo(() => {
    const normalizeForComparison = (obj) => {
      const result = {};
      Object.entries(obj).forEach(([key, value]) => {
        if (value && typeof value === 'object' && value.id) {
          // For objects with ID (like user), compare by ID
          result[key] = value.id;
        } else {
          result[key] = value;
        }
      });
      return result;
    };
    
    return JSON.stringify(normalizeForComparison(filters)) !== 
          JSON.stringify(normalizeForComparison(pendingFilters));
  }, [filters, pendingFilters]);

  /**
 * Get filters formatted for API call
 * Removes empty values
 * 
 * Priority rules:
 * - If account_scope is set (mine/team), account_owner is ignored
 * - If account_scope is empty, account_owner is used
 */
const apiFilters = useMemo(() => {
  const result = {};
  const hasAccountScope = filters.account_scope && filters.account_scope !== '';
  
  Object.entries(filters).forEach(([key, value]) => {
    // Skip account_owner if account_scope is active (scope takes priority)
    if (key === 'account_owner' && hasAccountScope) {
      return;
    }
    
    // Map account_scope to owner_scope for backend compatibility
    // Backend uses OwnerScopeMixin which expects 'owner_scope' query param
    if (key === 'account_scope') {
      if (value && value !== '') {
        result['owner_scope'] = value;
      }
      return;
    }
    
    if (Array.isArray(value) && value.length > 0) {
      result[key] = value;
    } else if (value !== '' && value !== null && value !== undefined) {
      // Extract ID for object values (e.g., account_owner user object)
      if (typeof value === 'object' && value.id) {
        result[key] = value.id;
      } else {
        result[key] = value;
      }
    }
  });
  return result;
}, [filters]);

  // ==============================|| HANDLERS ||============================== //

  /**
   * Update a single pending filter
   */
  const updatePendingFilter = useCallback((key, value) => {
    setPendingFilters(prev => ({
      ...prev,
      [key]: value
    }));
  }, []);

  /**
   * Update multiple pending filters at once
   */
  const updatePendingFilters = useCallback((updates) => {
    setPendingFilters(prev => ({
      ...prev,
      ...updates
    }));
  }, []);

  /**
   * Apply pending filters (trigger data refresh)
   */
  const applyFilters = useCallback(() => {
    setFilters({ ...pendingFilters });
  }, [pendingFilters]);

  /**
   * Clear all filters (both pending and applied)
   */
  const clearFilters = useCallback(() => {
    setFilters({ ...DEFAULT_FILTERS });
    setPendingFilters({ ...DEFAULT_FILTERS });
  }, []);

  /**
   * Reset pending filters to match applied filters (cancel changes)
   */
  const resetPendingFilters = useCallback(() => {
    setPendingFilters({ ...filters });
  }, [filters]);

  /**
   * Set filters directly (e.g., when loading a territory)
   */
  const setFiltersDirectly = useCallback((newFilters) => {
    const merged = { ...DEFAULT_FILTERS, ...newFilters };
    setFilters(merged);
    setPendingFilters(merged);
  }, []);

  // ==============================|| RETURN ||============================== //

  return {
    // State
    filters,
    pendingFilters,
    
    // Computed
    activeFiltersCount,
    hasActiveFilters,
    hasPendingChanges,
    apiFilters,
    
    // Handlers
    updatePendingFilter,
    updatePendingFilters,
    applyFilters,
    clearFilters,
    resetPendingFilters,
    setFiltersDirectly
  };
}

// ==============================|| CONSTANTS EXPORT ||============================== //

export { DEFAULT_FILTERS };