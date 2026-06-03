// frontend/src/api/aiPipelines/activityExtraction.js
/**
 * API mutation for the unified Activity Extraction endpoint.
 *
 * Backend: app_modules/ai_pipelines/views/activity_extraction_view.py
 * Endpoint: POST /module-ai-pipelines/activity-extraction/run/
 * Tier: T4 — External pipeline (chained 3rd-party LLM calls, 10-180s).
 *
 * Runs BOTH pipelines in a single call:
 *   1. Qualification signals (Pain/Objective/Impact/TechStack/Blocker)
 *   2. Next-step suggestions
 *
 * Key conventions (backend/core/timeout_conventions.py):
 *
 *   R3 (polling fallback) — On 202 Accepted or client timeout, poll
 *                           /core/operations/{key}/status/ for up to ~3 min.
 *
 *   R4 (deterministic key) — Idempotency-Key = sha256(activityId :: curatedTranscript).
 *                            Computed on the CURATED transcript (post-modal edit),
 *                            not the stored Activity.transcript.
 *
 * Return value — always a flat object, discriminated on `code`:
 *
 *   { success: true, data }                                → extraction succeeded
 *   { success: false, code: 'ALREADY_EXTRACTED', data }    → 409 DB dedup hit
 *   { success: false, code: 'IDEMPOTENCY_CONFLICT' }      → 409 same key + different payload
 *   { success: false, code: 'TIMEOUT_PENDING', isPending } → polling exhausted, server still working
 *   { success: false, code: 'POLL_FAILED' }                → polling-side error
 *   { success: false, error, status }                      → generic error
 */

import { api } from "utils/axiosClient";
import { revalidateMultiple } from "api/_swr";
import { pollOperationStatus } from "utils/pollOperationStatus";
import { isValidUUID } from "utils/validators";

// ==============================|| CONSTANTS ||============================== //

export const EXTRACTION_STATUS = {
  SUCCESS: "SUCCESS",
  PARTIAL: "PARTIAL",
  FAILED: "FAILED",
};

export const PIPELINE_STATUS = {
  SUCCESS: "SUCCESS",
  PARTIAL: "PARTIAL",
  PARSE_ERROR: "PARSE_ERROR",
  LLM_ERROR: "LLM_ERROR",
  TIMEOUT: "TIMEOUT",
};

export const PIPELINE_STATUS_LABELS = {
  SUCCESS: "Extraction completed",
  PARTIAL: "Extraction partially completed",
  PARSE_ERROR: "Extraction failed (parsing error)",
  LLM_ERROR: "Extraction failed (provider error)",
  TIMEOUT: "Extraction timed out",
};

export const EXTRACTION_OUTCOME_CODES = {
  ALREADY_EXTRACTED: "ALREADY_EXTRACTED",
  IDEMPOTENCY_CONFLICT: "IDEMPOTENCY_CONFLICT",
  IDEMPOTENCY_REPLAY_FAILED: "IDEMPOTENCY_REPLAY_FAILED",
  IDEMPOTENCY_UNKNOWN_STATE: "IDEMPOTENCY_UNKNOWN_STATE",
  TIMEOUT_PENDING: "TIMEOUT_PENDING",
  POLL_FAILED: "POLL_FAILED",
};

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  activityExtractionRun: "/module-ai-pipelines/activity-extraction/run/",
};

// ==============================|| SIGNAL LIST PREFIXES ||============================== //

const SIGNAL_LIST_PREFIXES = [
  "/module-signals/pain/",
  "/module-signals/objective/",
  "/module-signals/impact/",
  "/module-signals/tech-stack/",
  "/module-signals/blocker/",
  "/module-signals/next-step/",
];

// ==============================|| POLLING CONFIG ||============================== //

const EXTRACTION_POLL_CONFIG = {
  maxAttempts: 12,
  baseDelay: 2000,
  maxDelay: 15000,
  exponentialFactor: 2,
};

// ==============================|| HELPERS ||============================== //

/**
 * Compute a deterministic Idempotency-Key for an (activity, curatedTranscript) pair.
 *
 * Convention R4 (T4 strategy = deterministic). Same curated content → same key
 * → backend replays cached response within Redis TTL without re-running.
 *
 * @param {string} activityId
 * @param {string} trimmedTranscript - The curated transcript (post-modal edit).
 * @returns {Promise<string>} 64-char hex SHA-256 string.
 */
async function computeIdempotencyKey(activityId, trimmedTranscript) {
  const text = `${activityId}::${trimmedTranscript}`;
  const encoder = new TextEncoder();
  const data = encoder.encode(text);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

/**
 * Map a poll result into the unified extraction return shape.
 *
 * @param {Object|null} pollResult - Result from pollOperationStatus.
 * @returns {Object} Unified extraction return shape.
 */
function mapPollResult(pollResult) {
  if (!pollResult) {
    return {
      success: false,
      code: EXTRACTION_OUTCOME_CODES.POLL_FAILED,
      error:
        "Polling failed — no result received from the operation status endpoint.",
    };
  }

  if (pollResult.status === "succeeded") {
    const cached = pollResult.result || {};
    const httpStatus = cached.http_status;
    const body = cached.data || {};

    if (httpStatus === 200 && body.success === true) {
      revalidateMultiple(SIGNAL_LIST_PREFIXES);
      return {
        success: true,
        data: body.data || null,
      };
    }

    if (httpStatus === 409) {
      return {
        success: false,
        code: body.code || EXTRACTION_OUTCOME_CODES.ALREADY_EXTRACTED,
        error:
          body.error ||
          "This transcript has already been processed for this activity.",
        data: body.data || null,
        status: 409,
      };
    }

    return {
      success: body.success === true,
      code: body.code || EXTRACTION_OUTCOME_CODES.IDEMPOTENCY_UNKNOWN_STATE,
      error:
        body.error ||
        "Unexpected cached response from the operation status endpoint.",
      data: body.data || null,
      status: httpStatus,
    };
  }

  if (pollResult.status === "failed") {
    const errMsg =
      (pollResult.error && (pollResult.error.message || pollResult.error)) ||
      "Operation failed during processing.";
    return {
      success: false,
      code: EXTRACTION_OUTCOME_CODES.IDEMPOTENCY_REPLAY_FAILED,
      error: String(errMsg),
    };
  }

  if (pollResult.status === "still_running") {
    return {
      success: false,
      isPending: true,
      code: EXTRACTION_OUTCOME_CODES.TIMEOUT_PENDING,
      error:
        pollResult.message ||
        "Operation is taking longer than expected. It will continue in the background — check back in a moment.",
    };
  }

  return {
    success: false,
    code: EXTRACTION_OUTCOME_CODES.POLL_FAILED,
    error: `Unknown polling outcome: ${pollResult.status}`,
  };
}

/**
 * Poll for extraction result using extended config (~3 min total).
 *
 * Called directly instead of handleBulkTimeout to use extraction-specific
 * polling parameters (12 attempts, 2s→15s backoff).
 *
 * @param {string} idempotencyKey
 * @param {Function|null} onProgress
 * @returns {Promise<Object>} Unified extraction return shape.
 */
async function pollForResult(idempotencyKey, onProgress) {
  const pollResult = await pollOperationStatus(idempotencyKey, {
    ...EXTRACTION_POLL_CONFIG,
    onProgress,
  });

  revalidateMultiple(SIGNAL_LIST_PREFIXES);
  return mapPollResult(pollResult);
}

// ==============================|| MUTATION ||============================== //

/**
 * Run unified activity extraction (qualification signals + next-step suggestions).
 *
 * Triggers both pipelines via POST /module-ai-pipelines/activity-extraction/run/.
 * The backend runs them synchronously (10-180s). If the client times out or the
 * backend returns 202, we poll for up to ~3 minutes.
 *
 * The transcript argument is the CURATED version from the preview modal,
 * not necessarily the stored Activity.transcript.
 *
 * @param {string} activityId - UUID of the Activity.
 * @param {string} curatedTranscript - Curated transcript text (post-modal edit).
 *                                     Backend enforces 50 <= len(stripped) <= 50,000.
 * @param {Function|null} onProgress - Optional polling progress callback:
 *                                     (attempt: number, maxAttempts: number) => void.
 * @returns {Promise<Object>} See module docstring for return shape.
 */
export async function runActivityExtraction(
  activityId,
  curatedTranscript,
  onProgress = null,
) {
  // === 1. Client-side validation ===
  if (!activityId || !isValidUUID(activityId)) {
    return {
      success: false,
      error: "Invalid activity ID format",
      status: 400,
    };
  }

  const trimmedTranscript =
    typeof curatedTranscript === "string" ? curatedTranscript.trim() : "";
  if (!trimmedTranscript) {
    return {
      success: false,
      error: "Transcript cannot be empty",
      status: 400,
    };
  }

  // === 2. Compute deterministic Idempotency-Key on curated content ===
  let idempotencyKey = null;
  try {
    idempotencyKey = await computeIdempotencyKey(activityId, trimmedTranscript);
  } catch (err) {
    console.warn(
      "[runActivityExtraction] crypto.subtle unavailable, falling back to auto-injected random key.",
      err,
    );
    idempotencyKey = null;
  }

  // === 3. POST to unified extraction endpoint ===
  const requestConfig = {
    profile: "bulk",
  };
  if (idempotencyKey) {
    requestConfig.headers = { "Idempotency-Key": idempotencyKey };
  }

  const result = await api.post(
    endpoints.activityExtractionRun,
    {
      activity_id: activityId,
      transcript: trimmedTranscript,
    },
    requestConfig,
  );

  // === 4. Response dispatch ===

  // 4a. HTTP 202 — operation already in progress
  if (result?.data?.__is202) {
    return pollForResult(
      idempotencyKey || result.data.__idempotency_key,
      onProgress,
    );
  }

  // 4b. Sync HTTP 200 — both pipelines finished within axios timeout
  if (result.success) {
    revalidateMultiple(SIGNAL_LIST_PREFIXES);
    const body = result.data || {};
    return {
      success: true,
      data: body.data || null,
    };
  }

  // 4c. Client-side timeout — server may still be processing
  if (result.isTimeout) {
    return pollForResult(
      idempotencyKey || result.idempotencyKey,
      onProgress,
    );
  }

  // 4d. HTTP 409 — ALREADY_EXTRACTED or IDEMPOTENCY_CONFLICT
  if (result.status === 409) {
    const body = result.data || {};
    return {
      success: false,
      code: body.code || EXTRACTION_OUTCOME_CODES.IDEMPOTENCY_CONFLICT,
      error: body.error || result.error || "Conflict during extraction.",
      data: body.data || null,
      status: 409,
    };
  }

  // 4e. Other errors (400 validation, 500 server, etc.)
  return {
    success: false,
    error: result.error,
    status: result.status ?? 0,
    response: result.response ?? null,
  };
}
