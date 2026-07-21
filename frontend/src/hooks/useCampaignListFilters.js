// frontend/src/hooks/useCampaignListFilters.js

import { useState, useCallback, useMemo } from "react";

/**
 * Filter state for the Campaigns list view. Mirrors useDecisionCycleFilters
 * (pending/applied + apiFilters + chips). owner_scope defaults to the neutral
 * 'all'. owner / executor (users) and team are stored as objects (from the
 * async search selects); territory is an id string (from its static Select).
 */
const DEFAULT_FILTERS = {
  owner_scope: "all", // 'mine' | 'team' | 'all'
  owner: null, // user object (specific owner)
  status: "", // '' | DRAFT | ACTIVE | PAUSED | COMPLETED | CANCELLED
  campaign_type: "", // '' | OUTBOUND | TARGETED
  territories: "", // territory id
  executor: null, // user object
  channel_override: "", // '' | AUTO | EMAIL_ONLY
  team: null, // team object
};

export default function useCampaignListFilters() {
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [pendingFilters, setPendingFilters] = useState(DEFAULT_FILTERS);

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
