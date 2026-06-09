// frontend/src/api/aiPipelines/lastRun.js
/**
 * SWR hook for the last extraction run metadata of an activity.
 *
 * Backend: GET /module-ai-pipelines/last-run/?activity_id=<uuid>
 *
 * Returns the most recent SUCCESS or PARTIAL AIPipelineRun for the
 * given activity, used by the Notes Tab for:
 *   - "Last analyzed on …" caption (Mod 4)
 *   - Frontend dedup detection in the extraction modal (Mod 3)
 */

import { useMemo } from "react";
import useSWR from "swr";
import { useAuth } from "hooks/useAuth";
import { tenantKey } from "api/_swr";
import { isValidUUID } from "utils/validators";

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  lastRun: "/module-ai-pipelines/last-run/",
};

// ==============================|| HOOK ||============================== //

/**
 * Fetch the last extraction run for an activity.
 *
 * @param {string|null} activityId - Activity UUID.
 * @returns {Object} { lastRun, runsByPipeline, lastRunLoading, lastRunError, mutateLastRun }
 *
 * lastRun shape (when a run exists):
 *   {
 *     last_run_at: string (ISO 8601),
 *     last_run_by: { id: string, full_name: string } | null,
 *     input_hash: string (64-char sha256 hex),
 *     pipeline_type: string,
 *     status: string,
 *     created_signals_count: number,
 *   }
 *
 * runsByPipeline shape:
 *   {
 *     TRANSCRIPT_SIGNALS: { ...same shape as lastRun... } | null,
 *     NEXT_STEPS:         { ...same shape as lastRun... } | null,
 *   }
 *
 * lastRun is null when no prior run exists for this activity.
 */
export function useGetLastExtractionRun(activityId) {
  const { tenantId } = useAuth();
  const enabled = Boolean(activityId && isValidUUID(activityId));

  const url = enabled
    ? `${endpoints.lastRun}?activity_id=${activityId}`
    : null;

  const swrKey = tenantKey(url, tenantId);

  const { data, isLoading, error, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: false,
  });

  return useMemo(
    () => ({
      lastRun: data?.last_run ?? null,
      latestRun: data?.latest_run ?? null,
      runsByPipeline: data?.runs_by_pipeline ?? {
        TRANSCRIPT_SIGNALS: null,
        NEXT_STEPS: null,
      },
      lastRunLoading: isLoading,
      lastRunError: error,
      mutateLastRun: mutate,
    }),
    [data, isLoading, error, mutate],
  );
}
