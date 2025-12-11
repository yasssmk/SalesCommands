// frontend/src/hooks/useTerritoryFilters.js

import { useState, useCallback, useMemo } from 'react';

/**
 * Default empty filters object
 * Structure matches backend API query params
 */
const DEFAULT_FILTERS = {
  type: '',
  classification: '',
  account_owner: null
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
   */
  const activeFiltersCount = useMemo(() => {
    return Object.values(filters).filter(value => {
      if (Array.isArray(value)) return value.length > 0;
      return value !== '' && value !== null && value !== undefined;
    }).length;
  }, [filters]);

  /**
   * Check if any filter is active
   */
  const hasActiveFilters = useMemo(() => {
    return activeFiltersCount > 0;
  }, [activeFiltersCount]);

  /**
   * Check if pending filters differ from applied filters
   */
  const hasPendingChanges = useMemo(() => {
    return JSON.stringify(filters) !== JSON.stringify(pendingFilters);
  }, [filters, pendingFilters]);

  /**
   * Get filters formatted for API call
   * Removes empty values
   */
  const apiFilters = useMemo(() => {
  const result = {};
  Object.entries(filters).forEach(([key, value]) => {
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