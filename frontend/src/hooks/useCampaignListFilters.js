// frontend/src/hooks/useCampaignListFilters.js

import { useState, useCallback, useMemo } from "react";
import { useAuth } from "hooks/useAuth";
import { resolveDefaultOwnerScope } from "utils/ownerScope";

/**
 * Filter state for the Campaigns list view. Mirrors useDecisionCycleFilters
 * (pending/applied + apiFilters + chips). owner_scope is seeded from the user's
 * tier (individual → 'mine', manager → 'team', admin → 'all') and re-applies on
 * every mount (no persistence). owner / executor (users) and team are stored as
 * objects (from the async search selects); territory is an id string (from its
 * static Select).
 *
 * `initialFilters` seeds the lazy initializer once, at mount — the caller uses it
 * to AMEND the seed from the URL (e.g. ?status=ACTIVE from the Home card link).
 * It is spread LAST, so an explicit seed wins over the base default for the keys
 * it carries; owner_scope keeps its per-tier default unless the seed overrides it
 * (the two axes are orthogonal — the URL only seeds status here). The URL amorces
 * only: local state wins afterwards (clearFilters resets to the tier default, not
 * the seed), and the URL is neither rewritten on change nor cleaned after read.
 */
const DEFAULT_FILTERS = {
  owner_scope: "all", // neutral base; overridden per-tier at seed
  owner: null, // user object (specific owner)
  status: "", // '' | DRAFT | ACTIVE | PAUSED | COMPLETED | CANCELLED
  campaign_type: "", // '' | OUTBOUND | TARGETED
  territories: "", // territory id
  executor: null, // user object
  channel_override: "", // '' | AUTO | NO_CALLS
  team: null, // team object
};

export default function useCampaignListFilters(initialFilters = {}) {
  const { user } = useAuth();
  // Stable across renders within a mount: `user` is the memoised auth-context
  // value (only changes on login/refresh), so this pure derivation keeps the
  // same value and clearFilters below is not recreated each render. The user is
  // already loaded when this hook mounts (AuthGuard gates protected pages), so
  // the lazy seed reads the real tier at init — no flash, no useEffect.
  const defaultScope = resolveDefaultOwnerScope(user);

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

  const activeFiltersCount = useMemo(() => {
    let count = 0;
    if (filters.owner_scope && filters.owner_scope !== "all") count++;
    if (filters.owner?.id) count++;
    if (filters.status) count++;
    if (filters.campaign_type) count++;
    if (filters.territories) count++;
    if (filters.executor?.id) count++;
    if (filters.channel_override) count++;
    if (filters.team?.id) count++;
    return count;
  }, [filters]);

  const hasPendingChanges = useMemo(() => {
    const normalize = (f) => ({
      owner_scope: f.owner_scope,
      owner: f.owner?.id || null,
      status: f.status,
      campaign_type: f.campaign_type,
      territories: f.territories,
      executor: f.executor?.id || null,
      channel_override: f.channel_override,
      team: f.team?.id || null,
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
    if (filters.owner?.id) result.owner = filters.owner.id;
    if (filters.status) result.status = filters.status;
    if (filters.campaign_type) result.campaign_type = filters.campaign_type;
    if (filters.territories) result.territories = filters.territories;
    if (filters.executor?.id) result.executor = filters.executor.id;
    if (filters.channel_override) {
      result.channel_override = filters.channel_override;
    }
    if (filters.team?.id) result.team = filters.team.id;
    return result;
  }, [filters]);

  const updatePendingFilter = useCallback((key, value) => {
    setPendingFilters((prev) => ({ ...prev, [key]: value }));
  }, []);

  const applyFilters = useCallback(() => {
    setFilters({ ...pendingFilters });
  }, [pendingFilters]);

  // Clear resets to the TIER DEFAULT (not the neutral 'all'), same as a fresh
  // visit. defaultScope is stable (memoised user), so this callback identity
  // holds across renders.
  const clearFilters = useCallback(() => {
    setFilters({ ...DEFAULT_FILTERS, owner_scope: defaultScope });
    setPendingFilters({ ...DEFAULT_FILTERS, owner_scope: defaultScope });
  }, [defaultScope]);

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
