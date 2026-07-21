// frontend/src/hooks/useTerritoryListFilters.js

import { useState, useCallback, useMemo } from "react";

/**
 * Filter state for the Territories list view. Mirrors useDecisionCycleFilters
 * (pending/applied + apiFilters + chips). owner_scope defaults to the neutral
 * 'all'. `owner` is a specific user object (from AsyncUserSelect) that
 * coexists with owner_scope.
 */
const DEFAULT_FILTERS = {
  owner_scope: "all", // 'mine' | 'team' | 'all'
  owner: null, // user object (specific owner)
  type: "", // '' | 'ACCOUNT' | 'CONTACT'
};

export default function useTerritoryListFilters() {
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [pendingFilters, setPendingFilters] = useState(DEFAULT_FILTERS);

  const activeFiltersCount = useMemo(() => {
    let count = 0;
    if (filters.owner_scope && filters.owner_scope !== "all") count++;
    if (filters.owner?.id) count++;
    if (filters.type) count++;
    return count;
  }, [filters]);

  const hasPendingChanges = useMemo(() => {
    const normalize = (f) => ({
      owner_scope: f.owner_scope,
      owner: f.owner?.id || null,
      type: f.type,
    });
    return (
      JSON.stringify(normalize(filters)) !==
      JSON.stringify(normalize(pendingFilters))
    );
  }, [filters, pendingFilters]);

  const apiFilters = useMemo(() => {
    const result = {};
    if (filters.owner_scope && filters.owner_scope !== "all") {
      result.owner_scope = filters.owner_scope;
    }
    if (filters.owner?.id) {
      result.owner = filters.owner.id;
    }
    if (filters.type) {
      result.type = filters.type;
    }
    return result;
  }, [filters]);

  const updatePendingFilter = useCallback((key, value) => {
    setPendingFilters((prev) => ({ ...prev, [key]: value }));
  }, []);

  const applyFilters = useCallback(() => {
    setFilters({ ...pendingFilters });
  }, [pendingFilters]);

  const clearFilters = useCallback(() => {
    setFilters({ ...DEFAULT_FILTERS });
    setPendingFilters({ ...DEFAULT_FILTERS });
  }, []);

  const resetPendingFilters = useCallback(() => {
    setPendingFilters({ ...filters });
  }, [filters]);

  // Remove a single filter (chip delete): apply immediately to both states.
  const removeFilter = useCallback((key, neutralValue) => {
    setFilters((prev) => ({ ...prev, [key]: neutralValue }));
    setPendingFilters((prev) => ({ ...prev, [key]: neutralValue }));
  }, []);

  return {
    filters,
    pendingFilters,
    activeFiltersCount,
    hasPendingChanges,
    apiFilters,
    updatePendingFilter,
    applyFilters,
    clearFilters,
    resetPendingFilters,
    removeFilter,
  };
}

export { DEFAULT_FILTERS };
