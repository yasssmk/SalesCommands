// frontend/src/api/signals/signalCounts.js
/**
 * SWR hook for aggregated signal counts by activity.
 *
 * Backend: GET /module-signals/by-activity/<activity_id>/counts/
 *
 * Returns pending / validated / rejected totals and a per-type breakdown.
 * Used by ActivityHeader for the orange "N to validate" badge (Sprint F4).
 */

import { useMemo } from "react";
import useSWR from "swr";
import { useAuth } from "hooks/useAuth";
import { tenantKey } from "api/_swr";
import { isValidUUID } from "utils/validators";

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  counts: (activityId) => `/module-signals/by-activity/${activityId}/counts/`,
};

// ==============================|| HOOK ||============================== //

/**
 * Fetch aggregated signal counts for an activity.
 *
 * @param {string|null} activityId - Activity UUID.
 * @returns {Object} { counts, countsLoading, countsError, mutateCounts }
 *
 * counts shape:
 *   {
 *     pending:   number,
 *     validated: number,
 *     rejected:  number,
 *     by_type: {
 *       pain:       { pending, validated, rejected },
 *       objective:  { pending, validated, rejected },
 *       impact:     { pending, validated, rejected },
 *       tech_stack: { pending, validated, rejected },
 *       blocker:    { pending, validated, rejected },
 *       next_step:  { pending, validated, rejected },
 *     }
 *   }
 */
export function useActivitySignalCounts(activityId) {
  const { tenantId } = useAuth();
  const enabled = Boolean(activityId && isValidUUID(activityId));

  const url = enabled ? endpoints.counts(activityId) : null;
  const swrKey = tenantKey(url, tenantId);

  const { data, isLoading, error, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: false,
  });

  return useMemo(
    () => ({
      counts: data ?? null,
      countsLoading: isLoading,
      countsError: error,
      mutateCounts: mutate,
    }),
    [data, isLoading, error, mutate],
  );
}
