// frontend/src/hooks/useDecisionCycleFilters.js

import { useState, useCallback, useMemo } from "react";
import { useAuth } from "hooks/useAuth";
import { resolveDefaultOwnerScope } from "utils/ownerScope";

/**
 * Default decision-cycle filters.
 *
 * owner_scope is seeded from the user's tier (individual → 'mine',
 * manager → 'team', admin → 'all') and re-applies on every mount (no
 * persistence), same as the Territory/Campaign list drawers. The user can
 * widen or narrow it from the filter drawer; 'all' sends no owner_scope param
 * (the backend then returns the tenant-wide, client-scoped list).
 */
const DEFAULT_FILTERS = {
  owner_scope: "all", // neutral base; overridden per-tier at seed
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
  const { user } = useAuth();
  // Stable primitive derived from the memoised user (AuthGuard guarantees the
  // user is loaded at mount), so the lazy seed reads the real tier at init —
  // no flash, no useEffect — and clearFilters keeps a stable identity. An
  // explicit initialFilters.owner_scope still wins (spread last).
  const defaultScope = resolveDefaultOwnerScope(user);

  // ==============================|| STATE ||============================== //

  const [filters, setFilters] = useState(() => ({
    ...DEFAULT_FILTERS,
    owner_scope: defaultScope,
    ...initialFilters,
  }));

  const [pendingFilters, setPendingFilters] = useState(() => ({
    ...DEFAULT_FILTERS,
    owner_scope: defaultScope,
    ...initialFilters,
  }));

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

  // Clear resets to the TIER DEFAULT (not the neutral 'all'), same as a fresh
  // visit. defaultScope is a stable primitive, so this callback identity holds.
  const clearFilters = useCallback(() => {
    setFilters({ ...DEFAULT_FILTERS, owner_scope: defaultScope });
    setPendingFilters({ ...DEFAULT_FILTERS, owner_scope: defaultScope });
  }, [defaultScope]);

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
