// frontend/src/hooks/useTeamTodoFilters.js

import { useState, useCallback, useMemo } from 'react';

// The manager team todo has two filters, both single-value: team (a subtree id)
// and owner (a person id). Modeled on useTerritoryFilters (pending -> apply for
// the drawer) with an extra immediate-apply path for the bloc-1 drill-down, so a
// click on a person and the panel's Person select drive the SAME state.
const DEFAULT_FILTERS = { team: '', owner: '' };

/**
 * Hook for the manager team todo filters (team + owner). Returns the applied
 * `filters`, the drawer's `pendingFilters`, `apiFilters` (empty values dropped,
 * ready for the query params), and handlers. `applyFilterImmediate` sets pending
 * AND applied at once — used by the per-person drill-down (no Apply step).
 */
export default function useTeamTodoFilters() {
  const [filters, setFilters] = useState({ ...DEFAULT_FILTERS });
  const [pendingFilters, setPendingFilters] = useState({ ...DEFAULT_FILTERS });

  const activeFiltersCount = useMemo(
    () => Object.values(filters).filter((v) => v !== '' && v != null).length,
    [filters],
  );

  const apiFilters = useMemo(() => {
    const out = {};
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== '' && v != null) out[k] = v;
    });
    return out;
  }, [filters]);

  const updatePendingFilter = useCallback((key, value) => {
    setPendingFilters((prev) => ({ ...prev, [key]: value }));
  }, []);

  const updatePendingFilters = useCallback((updates) => {
    setPendingFilters((prev) => ({ ...prev, ...updates }));
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

  // Set one/several filters and apply immediately (drill-down + chip removal),
  // keeping pending in sync so the drawer reflects the change.
  const applyFilterImmediate = useCallback((updates) => {
    setFilters((prev) => ({ ...prev, ...updates }));
    setPendingFilters((prev) => ({ ...prev, ...updates }));
  }, []);

  return {
    filters,
    pendingFilters,
    apiFilters,
    activeFiltersCount,
    hasActiveFilters: activeFiltersCount > 0,
    updatePendingFilter,
    updatePendingFilters,
    applyFilters,
    clearFilters,
    resetPendingFilters,
    applyFilterImmediate,
  };
}

export { DEFAULT_FILTERS };
