// frontend/src/api/aiPipelines/dealHealth.js
/**
 * API mutation for the Deal Health diagnostic pipeline.
 *
 * Backend: app_modules/ai_pipelines/views/deal_health_view.py
 * Endpoint: POST /module-ai-pipelines/deal-health/run/
 *
 * Runs a single LLM call to diagnose deal maturity from validated signals
 * and transcripts. Returns a DealHealthSnapshot.
 *
 * The pipeline is synchronous server-side but usually outlasts the client's
 * bulk-profile timeout (a reasoning model: more than a minute). On a client
 * timeout the run goes on and writes its snapshot: the caller polls
 * GET .../health-snapshots/latest/ for up to DEAL_HEALTH_POLL_CONFIG
 * (~3 min, the server polling window R2 of core/timeout_conventions.py, as
 * the Activity Run AI: activityExtraction.js EXTRACTION_POLL_CONFIG). The
 * run state shared by every trigger lives in hooks/useDealHealthRunner.js.
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
  dealHealthRun: "/module-ai-pipelines/deal-health/run/",
  snapshotLatest: (cycleId) =>
    `/decision_cycles/${cycleId}/health-snapshots/latest/`,
  snapshotList: (cycleId) =>
    `/decision_cycles/${cycleId}/health-snapshots/`,
};

// ==============================|| RUN CONSTANTS ||============================== //

// Sprint « Deal health v2 », 5c: the polling window after a client timeout —
// 36 x 5 s ≈ 3 min, the backend's POLLING_MAX_ATTEMPTS x
// POLLING_INTERVAL_SECONDS (core/timeout_conventions.py), within which the
// deal health call ends (DEAL_HEALTH_TIMEOUT_S).
export const DEAL_HEALTH_POLL_CONFIG = {
  intervalMs: 5000,
  maxAttempts: 36,
};

// The labels and messages of a deal health run, shared by every trigger.
export const DEAL_HEALTH_RUN_LABELS = {
  RUN: "Run Deal Health",
  RERUN: "Re-run",
  HEADER: "Deal Health",
  RUNNING: "Analysis in progress…",
  DONE: "Deal health diagnostic completed",
  // End of the polling window, no snapshot yet: information, not an error.
  STILL_RUNNING:
    "The analysis is taking longer than usual. The diagnostic will appear on this deal once it is ready — no need to run it again.",
};

// ==============================|| MUTATION ||============================== //

/**
 * Run deal-health diagnostic pipeline on a decision cycle.
 *
 * Triggers POST /module-ai-pipelines/deal-health/run/ with bulk profile
 * (18s timeout). The backend performs a single LLM call and persists a
 * DealHealthSnapshot atomically.
 *
 * On any outcome (success or error), snapshot caches are revalidated so
 * that a server-side snapshot created before a client timeout is picked up
 * when the Strategic tab mounts.
 *
 * @param {string} cycleId - UUID of the DecisionCycle.
 * @returns {Promise<Object>} { success, data } or { success, error, status, response }
 */
export async function runDealHealth(cycleId) {
  if (!cycleId || !isValidUUID(cycleId)) {
    return {
      success: false,
      error: "Invalid cycle ID format",
      status: 0,
    };
  }

  const snapshotPrefix = `/decision_cycles/${cycleId}/health-snapshots/`;

  let result;
  try {
    result = await api.post(
      endpoints.dealHealthRun,
      { decision_cycle_id: cycleId },
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
    isTimeout: result.isTimeout || false,
    response: result.response || null,
  };
}

/**
 * Poll the latest snapshot until a new one appears (recovery after a client
 * timeout).
 *
 * The deal-health pipeline runs synchronously server-side but can outlast the
 * client's bulk-profile timeout. When runDealHealth times out, the snapshot
 * may still have been written — this polls GET .../health-snapshots/latest/
 * and resolves as soon as a snapshot newer than `previousSnapshotId` is seen.
 *
 * @param {string} cycleId - UUID of the DecisionCycle.
 * @param {string|null} previousSnapshotId - id (or snapshot_date) of the
 *   snapshot present before the run, or null if there was none.
 * @param {Object} [opts]
 * @param {number} [opts.intervalMs] - Delay between attempts
 *   (default DEAL_HEALTH_POLL_CONFIG).
 * @param {number} [opts.maxAttempts] - Maximum poll attempts
 *   (default DEAL_HEALTH_POLL_CONFIG).
 * @returns {Promise<Object>} { success: true, data } on a new snapshot,
 *   otherwise { success: false, timedOut: true }.
 */
export async function pollForNewSnapshot(
  cycleId,
  previousSnapshotId,
  {
    intervalMs = DEAL_HEALTH_POLL_CONFIG.intervalMs,
    maxAttempts = DEAL_HEALTH_POLL_CONFIG.maxAttempts,
  } = {},
) {
  if (!cycleId || !isValidUUID(cycleId)) {
    return { success: false, error: "Invalid cycle ID format" };
  }

  const snapshotPrefix = `/decision_cycles/${cycleId}/health-snapshots/`;

  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, intervalMs));

    const result = await api.get(endpoints.snapshotLatest(cycleId));
    if (result.success) {
      const snapshot = result.data?.data ?? result.data ?? null;
      const currentId = snapshot?.id ?? snapshot?.snapshot_date ?? null;
      if (snapshot && currentId && currentId !== previousSnapshotId) {
        revalidateMultiple([snapshotPrefix]);
        return { success: true, data: snapshot };
      }
    }
  }

  return { success: false, timedOut: true };
}

/**
 * Fetch the id (or snapshot_date fallback) of the latest snapshot, or null.
 *
 * Used to capture a baseline before a run so a subsequent poll can tell a
 * newly written snapshot apart from a pre-existing one.
 *
 * @param {string} cycleId - UUID of the DecisionCycle.
 * @returns {Promise<string|null>}
 */
export async function getLatestSnapshotId(cycleId) {
  if (!cycleId || !isValidUUID(cycleId)) return null;

  const result = await api.get(endpoints.snapshotLatest(cycleId));
  if (!result.success) return null;

  const snapshot = result.data?.data ?? result.data ?? null;
  return snapshot?.id ?? snapshot?.snapshot_date ?? null;
}

// ==============================|| SWR HOOKS ||============================== //

/**
 * GET latest deal-health snapshot for a decision cycle.
 *
 * GET /decision_cycles/{cycleId}/health-snapshots/latest/
 *
 * Backend returns { success: true, data: <snapshot|null> }.
 * When no snapshot exists, data is null — this is NOT an error.
 *
 * @param {string} cycleId - UUID of the DecisionCycle.
 * @returns {Object} { snapshot, snapshotLoading, snapshotError, mutateSnapshot }
 */
export function useGetDealHealthSnapshot(cycleId) {
  const { tenantId } = useAuth();

  const swrKey = useMemo(() => {
    if (!cycleId || !isValidUUID(cycleId)) return null;
    return tenantKey(endpoints.snapshotLatest(cycleId), tenantId);
  }, [cycleId, tenantId]);

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

/**
 * GET deal-health snapshot history for a decision cycle.
 *
 * GET /decision_cycles/{cycleId}/health-snapshots/
 *
 * @param {string} cycleId - UUID of the DecisionCycle.
 * @returns {Object} { snapshots, snapshotsLoading, snapshotsError, mutateSnapshots }
 */
export function useGetDealHealthHistory(cycleId) {
  const { tenantId } = useAuth();

  const swrKey = useMemo(() => {
    if (!cycleId || !isValidUUID(cycleId)) return null;
    return tenantKey(endpoints.snapshotList(cycleId), tenantId);
  }, [cycleId, tenantId]);

  const { data, isLoading, error, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  return useMemo(
    () => ({
      snapshots: data?.data?.results ?? data?.data ?? [],
      snapshotsLoading: isLoading,
      snapshotsError: error,
      mutateSnapshots: mutate,
    }),
    [data, isLoading, error, mutate],
  );
}
