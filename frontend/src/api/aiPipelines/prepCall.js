// frontend/src/api/aiPipelines/prepCall.js
/**
 * API mutation and SWR hooks for the Prep Call tactical brief pipeline.
 *
 * Backend: app_modules/ai_pipelines/views/prep_call_view.py
 * Endpoints:
 *   POST /module-ai-pipelines/prep-call/run/
 *   GET  /module-ai-pipelines/prep-call/by-activity/<uuid>/
 *
 * Runs a single LLM call to produce a tactical pre-call brief from
 * validated signals and the latest DealHealthSnapshot. Returns a
 * PrepCallSnapshot.
 *
 * Return value:
 *   { success: true, data: { run, snapshot } }   → pipeline succeeded
 *   { success: false, error, status, response }   → generic error
 */

import useSWR from "swr";
import { useMemo } from "react";
import { useAuth } from "hooks/useAuth";
import { api } from "utils/axiosClient";
import { tenantKey, revalidateMultiple } from "api/_swr";
import { isValidUUID } from "utils/validators";

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  prepCallRun: "/module-ai-pipelines/prep-call/run/",
  prepCallByActivity: (activityId) =>
    `/module-ai-pipelines/prep-call/by-activity/${activityId}/`,
};

// ==============================|| MUTATION ||============================== //

/**
 * Run prep-call brief pipeline on an activity.
 *
 * Triggers POST /module-ai-pipelines/prep-call/run/ with bulk profile
 * (60s timeout). The backend performs a single LLM call and persists a
 * PrepCallSnapshot atomically.
 *
 * On any outcome (success or error), snapshot caches are revalidated so
 * that a server-side snapshot created before a client timeout is picked up.
 *
 * @param {string} activityId - UUID of the Activity.
 * @param {string|null} contactId - UUID of the target Contact (optional).
 * @returns {Promise<Object>} { success, data } or { success, error, status, response }
 */
export async function runPrepCall(activityId, contactId = null) {
  if (!activityId || !isValidUUID(activityId)) {
    return {
      success: false,
      error: "Invalid activity ID format",
      status: 0,
    };
  }

  const snapshotPrefix = `/module-ai-pipelines/prep-call/by-activity/${activityId}/`;

  let result;
  try {
    result = await api.post(
      endpoints.prepCallRun,
      {
        activity_id: activityId,
        contact_id: contactId || null,
      },
      { profile: "bulk" },
    );
  } finally {
    revalidateMultiple([snapshotPrefix]);
  }

  if (result.success) {
    const data = result.data?.data || result.data;
    return { success: true, data };
  }

  return {
    success: false,
    error: result.error,
    status: result.status || 0,
    response: result.response || null,
  };
}

// ==============================|| SWR HOOKS ||============================== //

/**
 * GET latest prep-call snapshot for an activity.
 *
 * GET /module-ai-pipelines/prep-call/by-activity/{activityId}/
 *
 * Backend returns { success: true, data: <snapshot|null> }.
 * When no snapshot exists, data is null — this is NOT an error.
 *
 * @param {string} activityId - UUID of the Activity.
 * @returns {Object} { snapshot, snapshotLoading, snapshotError, mutateSnapshot }
 */
export function useGetPrepCallSnapshot(activityId) {
  const { tenantId } = useAuth();

  const swrKey = useMemo(() => {
    if (!activityId || !isValidUUID(activityId)) return null;
    return tenantKey(endpoints.prepCallByActivity(activityId), tenantId);
  }, [activityId, tenantId]);

  const { data, isLoading, error, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  return useMemo(
    () => ({
      snapshot: data?.data ?? null,
      snapshotLoading: isLoading,
      snapshotError: error,
      mutateSnapshot: mutate,
    }),
    [data, isLoading, error, mutate],
  );
}
