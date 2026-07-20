// frontend/src/hooks/useDecisionCycleFilters.js

import { useState, useCallback, useMemo } from "react";

/**
 * Default decision-cycle filters.
 *
 * owner_scope defaults to 'mine' (the caller sees their own cycles first);
 * the user can widen it to 'team' or 'all' from the filter drawer. 'all'
 * sends no owner_scope param (the backend then returns the tenant-wide,
 * client-scoped list).
 */
const DEFAULT_FILTERS = {
  owner_scope: "all", // 'mine' | 'team' | 'all' — neutral default (opens on all cycles)
  account: null, // account object (from AsyncAccountSelect)
  status: "", // '' | 'OPEN' | 'WON' | 'LOST' | 'ON_HOLD' | 'NOT_QUALIFIED'
};

/**
 * Filter-state hook for the Decision Cycles table.
 *
 * Mirrors useTerritoryFilters (pending/applied pattern + apiFilters that map
 * to the backend query params) but with decision-cycle facets.
 */
export default function useDecisionCycleFilters(initialFilters = {}) {
  // ==============================|| STATE ||============================== //

  const [filters, setFilters] = useState({
    ...DEFAULT_FILTERS,
    ...initialFilters,
  });

  const [pendingFilters, setPendingFilters] = useState({
    ...DEFAULT_FILTERS,
    ...initialFilters,
  });

  // ==============================|| COMPUTED ||============================== //

  /**
   * Count of active (narrowing) filters. owner_scope counts when it narrows
   * below 'all' (i.e. 'mine' or 'team'); account and status count when set.
   */
  const activeFiltersCount = useMemo(() => {
    let count = 0;
    if (filters.owner_scope && filters.owner_scope !== "all") count++;
    if (filters.account?.id) count++;
    if (filters.status) count++;
    return count;
  }, [filters]);

  const hasActiveFilters = useMemo(
    () => activeFiltersCount > 0,
    [activeFiltersCount],
  );

  const hasPendingChanges = useMemo(() => {
    const normalize = (obj) => ({
      owner_scope: obj.owner_scope,
      account: obj.account?.id || null,
      status: obj.status,
    });
    return (
      JSON.stringify(normalize(filters)) !==
      JSON.stringify(normalize(pendingFilters))
    );
  }, [filters, pendingFilters]);

  /**
   * Filters formatted for the API (from the APPLIED filters).
   *   - owner_scope: 'mine'/'team' forwarded; 'all' omitted (tenant-wide).
   *   - account object → account=<id> (exact).
   *   - status 'OPEN' → outcome__isnull=true; a terminal outcome → outcome=<value>.
   */
  const apiFilters = useMemo(() => {
    const result = {};
    if (filters.owner_scope && filters.owner_scope !== "all") {
      result.owner_scope = filters.owner_scope;
    }
    if (filters.account?.id) {
      result.account = filters.account.id;
    }
    if (filters.status === "OPEN") {
      result.outcome__isnull = true;
    } else if (filters.status) {
      result.outcome = filters.status;
    }
    return result;
  }, [filters]);

  // ==============================|| HANDLERS ||============================== //

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

  // ==============================|| RETURN ||============================== //

  return {
    filters,
    pendingFilters,
    activeFiltersCount,
    hasActiveFilters,
    hasPendingChanges,
    apiFilters,
    updatePendingFilter,
    updatePendingFilters,
    applyFilters,
    clearFilters,
    resetPendingFilters,
  };
}

export { DEFAULT_FILTERS };
