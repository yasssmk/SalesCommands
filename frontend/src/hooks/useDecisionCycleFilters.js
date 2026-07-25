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
  // Unified status — one of the backend DecisionCycleFilterSet literals:
  // '' | OPEN | WON | LOST | ON_HOLD | NOT_QUALIFIED
  //    | NOT_STARTED | IN_PROGRESS | OVERDUE | STALLED
  status: "",
  owner: null, // user object (AsyncUserSelect)
  team: null, // team object (AsyncTeamSelect)
  contact: null, // contact object (AsyncContactSelect)
  source_campaign: null, // campaign object {id, name} (static select)
  product: null, // product object {id, name} (static select)
};

// Object-valued facets (async / lookup selectors). Their neutral value is null
// and they contribute to apiFilters as `<key>=<obj>.id`.
const OBJECT_FACETS = ["account", "owner", "team", "contact", "source_campaign", "product"];

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
    if (filters.status) count++;
    for (const key of OBJECT_FACETS) {
      if (filters[key]?.id) count++;
    }
    return count;
  }, [filters]);

  const hasActiveFilters = useMemo(
    () => activeFiltersCount > 0,
    [activeFiltersCount],
  );

  const hasPendingChanges = useMemo(() => {
    const normalize = (obj) => {
      const norm = { owner_scope: obj.owner_scope, status: obj.status };
      for (const key of OBJECT_FACETS) norm[key] = obj[key]?.id || null;
      return norm;
    };
    return (
      JSON.stringify(normalize(filters)) !==
      JSON.stringify(normalize(pendingFilters))
    );
  }, [filters, pendingFilters]);

  /**
   * Filters formatted for the API (from the APPLIED filters). Every param name
   * matches the backend DecisionCycleFilterSet exactly.
   *   - owner_scope: 'mine'/'team' forwarded; 'all' omitted (tenant-wide).
   *   - status: the unified literal, forwarded as-is (backend maps OPEN →
   *     outcome IS NULL, WON/LOST/… → outcome exact, derived states → annotation).
   *   - object facets → `<key>=<obj>.id` (account, owner, team, contact,
   *     source_campaign, product).
   */
  const apiFilters = useMemo(() => {
    const result = {};
    if (filters.owner_scope && filters.owner_scope !== "all") {
      result.owner_scope = filters.owner_scope;
    }
    if (filters.status) {
      result.status = filters.status;
    }
    for (const key of OBJECT_FACETS) {
      if (filters[key]?.id) result[key] = filters[key].id;
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

export { DEFAULT_FILTERS, OBJECT_FACETS };
