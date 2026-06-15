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
 * Unlike activity extraction, this pipeline is synchronous with no polling
 * or idempotency key management — a simple POST that returns the snapshot.
 *
 * Return value:
 *   { success: true, data: { run, snapshot } }   → pipeline succeeded
 *   { success: false, error, status, response }   → generic error
 */

import { api } from "utils/axiosClient";
import { revalidateMultiple } from "api/_swr";
import { isValidUUID } from "utils/validators";

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  dealHealthRun: "/module-ai-pipelines/deal-health/run/",
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
    response: result.response || null,
  };
}
