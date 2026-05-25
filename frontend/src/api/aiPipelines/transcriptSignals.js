// frontend/src/api/aiPipelines/transcriptSignals.js
/**
 * API mutation for the AI Pipelines module — Transcript Signals extraction.
 *
 * Backend: app_modules/ai_pipelines/views/transcript_signals_view.py
 * Tier:    T4 — External pipeline (chained 3rd-party LLM calls).
 *
 * The backend convention is defined in backend/core/timeout_conventions.py.
 * Key rules applied here:
 *
 *   R3 (polling fallback) — never try/catch a plain POST for T4 ops.
 *                           On 202 Accepted OR client-side timeout, we
 *                           hand off to handleBulkTimeout which polls
 *                           /ops/{idempotency_key}/ for up to 3 minutes.
 *
 *   R4 (deterministic key) — Idempotency-Key is
 *                            sha256(activityId :: trimmedTranscript),
 *                            NOT the random UUID axios auto-injects.
 *                            Same inputs → same key → backend replays
 *                            cached response within 10-min Redis TTL.
 *
 *   R5 (UX wait pattern)  — the wizard stays open during polling. We
 *                            expose onProgress(attempt, max) so the
 *                            UI can surface a meaningful "still
 *                            processing..." state to the user.
 *
 * Return value
 * ------------
 * Always a flat object. The wizard discriminates on `code`:
 *
 *   { success: true, data }                                  → render validation step
 *   { success: false, code: 'ALREADY_EXTRACTED', data }      → render "already done" banner
 *   { success: false, code: 'IDEMPOTENCY_CONFLICT' }         → render conflict error (rare)
 *   { success: false, code: 'IDEMPOTENCY_REPLAY_FAILED' }    → render "previous failure" with wait hint
 *   { success: false, code: 'TIMEOUT_PENDING', isPending }   → render "still running in background"
 *   { success: false, code: 'POLL_FAILED' }                  → render polling-side error
 *   { success: false, error, status }                        → render generic error
 *
 * No SWR hooks here — the extraction is a one-shot mutation, not a
 * cacheable read. The wizard fires it imperatively and consumes the
 * result on resolution.
 */

import { api } from "utils/axiosClient";
import { handleBulkTimeout, revalidateMultiple } from "api/_swr";
import { isValidUUID } from "utils/validators";

// ==============================|| CONSTANTS ||============================== //

/**
 * Pipeline run status values returned by the backend.
 * Mirrors backend AIPipelineStatus enum
 * (app_modules/ai_pipelines/constants.py).
 */
export const AI_PIPELINE_STATUS = {
  SUCCESS: "SUCCESS",
  PARTIAL: "PARTIAL",
  PARSE_ERROR: "PARSE_ERROR",
  LLM_ERROR: "LLM_ERROR",
  TIMEOUT: "TIMEOUT",
};

export const AI_PIPELINE_STATUS_LABELS = {
  SUCCESS: "Extraction completed",
  PARTIAL: "Extraction partially completed",
  PARSE_ERROR: "Extraction failed (parsing error)",
  LLM_ERROR: "Extraction failed (provider error)",
  TIMEOUT: "Extraction timed out",
};

export const AI_PIPELINE_STATUS_COLORS = {
  SUCCESS: "success",
  PARTIAL: "warning",
  PARSE_ERROR: "error",
  LLM_ERROR: "error",
  TIMEOUT: "error",
};

/**
 * Outcome codes returned by extractTranscriptSignals.
 *
 * Aligned with the `code` field emitted by
 * backend/app_modules/ai_pipelines/views/transcript_signals_view.py.
 * The wizard switches on this to render the appropriate UI state.
 */
export const EXTRACTION_OUTCOME_CODES = {
  // Backend-emitted codes
  ALREADY_EXTRACTED: "ALREADY_EXTRACTED", // 409 layer-2 DB dedup hit
  IDEMPOTENCY_CONFLICT: "IDEMPOTENCY_CONFLICT", // 409 same key + different payload
  IDEMPOTENCY_REPLAY_FAILED: "IDEMPOTENCY_REPLAY_FAILED", // 500 replay of a previously-failed run
  IDEMPOTENCY_UNKNOWN_STATE: "IDEMPOTENCY_UNKNOWN_STATE", // 500 corrupted Redis state

  // Client-emitted codes (polling side)
  TIMEOUT_PENDING: "TIMEOUT_PENDING", // polling exhausted attempts, server still working
  POLL_FAILED: "POLL_FAILED", // polling helper errored out
};

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  transcriptSignalsExtract: "/module-ai-pipelines/transcript-signals/extract/",
};

// ==============================|| SIGNAL LIST PREFIXES ||============================== //

/**
 * SWR cache prefixes invalidated after a successful extraction.
 *
 * The pipeline creates PENDING signals across all 4 types — every
 * list that displays them (account workspace SignalsTab, activity
 * SignalsTab, etc.) needs to refetch so the new rows appear without
 * a manual page reload.
 *
 * Kept in sync with endpoints in api/signals/signals.js.
 */
const SIGNAL_LIST_PREFIXES = [
  "/module-signals/pain/",
  "/module-signals/objective/",
  "/module-signals/impact/",
  "/module-signals/tech-stack/",
];

// ==============================|| HELPERS ||============================== //

/**
 * Compute a deterministic Idempotency-Key for an (activity, transcript) pair.
 *
 * Convention R4 (T4 strategy = deterministic). Same inputs → same key
 * → backend replays the cached response within Redis TTL without
 * re-running the pipeline.
 *
 * The `::` separator prevents prefix-collision between concatenations
 * (e.g. activity='abc' + transcript='def' has the same naive
 * concatenation as activity='a' + transcript='bcdef').
 *
 * Output is a 64-char hex SHA-256 string — same shape as the random
 * UUIDs axios would otherwise generate, so transparent to the
 * idempotency framework on both ends.
 *
 * @param {string} activityId
 * @param {string} trimmedTranscript
 * @returns {Promise<string>}
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
 * `handleBulkTimeout` returns one of:
 *   { status: 'succeeded', result: { http_status, data: <body> } }
 *   { status: 'failed', error }
 *   { status: 'still_running', message? }
 *   null  (no idempotency key found — should not happen in this flow)
 *
 * `result.data` inside the cache mirrors the SYNC HTTP response body,
 * so we extract the same fields (success / data / code / error) and
 * normalize to the public return shape.
 *
 * Side effect: on success we trigger signal-list revalidation here so
 * polled-path callers and sync-path callers refresh the UI uniformly.
 *
 * @param {Object|null} pollResult
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

  // ---- Succeeded: the server stored a finalized response in Redis ----
  if (pollResult.status === "succeeded") {
    const cached = pollResult.result || {};
    const httpStatus = cached.http_status;
    const body = cached.data || {};

    // HTTP 200 → successful extraction
    if (httpStatus === 200 && body.success === true) {
      revalidateMultiple(SIGNAL_LIST_PREFIXES);
      return {
        success: true,
        data: body.data || null,
      };
    }

    // HTTP 409 → either DB-dedup hit (ALREADY_EXTRACTED) or
    //           idempotency conflict (same key + different payload).
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

    // Unexpected cached state — surface as-is so the wizard can show
    // a generic error instead of crashing on missing fields.
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

  // ---- Failed: the server marked the op as failed via fail_op ----
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

  // ---- Still running: polling gave up but the server may still finish ----
  if (pollResult.status === "still_running") {
    return {
      success: false,
      isPending: true,
      code: EXTRACTION_OUTCOME_CODES.TIMEOUT_PENDING,
      error:
        pollResult.message ||
        "Operation is taking longer than expected. It will continue in the background — refresh the Signals tab in a moment.",
    };
  }

  // ---- Unknown poll status — defensive fallback ----
  return {
    success: false,
    code: EXTRACTION_OUTCOME_CODES.POLL_FAILED,
    error: `Unknown polling outcome: ${pollResult.status}`,
  };
}

// ==============================|| MUTATION ||============================== //

/**
 * EXTRACT SIGNALS FROM TRANSCRIPT
 *
 * Triggers a 3-stage LLM extraction pipeline (pain / objective /
 * tech-stack) for the given activity's transcript. The pipeline runs
 * server-side; the client either receives the result synchronously
 * (8-15s typical) or recovers it via polling (60-180s for slow runs,
 * up to 3 min before polling gives up).
 *
 * Persisted signals land as PENDING so the rep can validate / reject
 * them via the Signals tab on the account workspace or inside the
 * wizard.
 *
 * UX integration
 * --------------
 * The wizard fires this and stays open until the promise resolves.
 * Pass `onProgress(attempt, maxAttempts)` to receive polling progress
 * updates -- the wizard uses this to flip from "Analyzing..." to
 * "Still processing... (n/max)" during the polling phase.
 *
 * Cost protection
 * ---------------
 * The Idempotency-Key is DETERMINISTIC (sha256 of activity + trimmed
 * transcript). Clicking "Extract" twice with the same inputs → backend
 * replays the cached response within 10 min Redis TTL, no tokens
 * burned. After TTL, the layer-2 DB check on AIPipelineRun.input_hash
 * catches the retry and returns a 409 ALREADY_EXTRACTED.
 *
 * Editing the transcript by even one character → different key →
 * fresh extraction. That is intentional: the rep is asking for a new
 * analysis on different input.
 *
 * @param {string} activityId - UUID of the Activity owning the transcript.
 * @param {string} transcript - Raw transcript text. Backend enforces
 *                              50 <= len(stripped) <= 50000.
 * @param {Function|null} onProgress - Optional polling progress callback:
 *                                     (attempt: number, maxAttempts: number) => void.
 *                                     Called on each polling attempt. NOT called
 *                                     on the sync path.
 * @returns {Promise<Object>} See module docstring for return shape.
 */
export async function extractTranscriptSignals(
  activityId,
  transcript,
  onProgress = null,
) {
  // === 1. Client-side validation (predictable 400s short-circuited locally) ===
  if (!activityId || !isValidUUID(activityId)) {
    return {
      success: false,
      error: "Invalid activity ID format",
      status: 400,
    };
  }

  const trimmedTranscript =
    typeof transcript === "string" ? transcript.trim() : "";
  if (!trimmedTranscript) {
    return {
      success: false,
      error: "Transcript cannot be empty",
      status: 400,
    };
  }

  // === 2. Compute deterministic Idempotency-Key ===
  let idempotencyKey = null;
  try {
    idempotencyKey = await computeIdempotencyKey(activityId, trimmedTranscript);
  } catch (err) {
    // crypto.subtle is only available in secure contexts (HTTPS or
    // localhost). Outside those, fall back to letting axios auto-inject
    // a random UUID -- breaks the deterministic-replay guarantee but
    // the operation still works (each call = fresh extraction).
    console.warn(
      "[extractTranscriptSignals] crypto.subtle unavailable, falling back to axios auto-injected random idempotency key.",
      err,
    );
    idempotencyKey = null;
  }

  // === 3. POST to the extraction endpoint ===
  const requestConfig = {
    profile: "bulk", // 60s axios timeout; polling handles anything beyond
  };
  if (idempotencyKey) {
    // Explicit header overrides the axios interceptor's auto-injection.
    // See utils/axiosClient.js request interceptor:
    //     "if (!config.headers['Idempotency-Key']) { auto-inject }"
    requestConfig.headers = { "Idempotency-Key": idempotencyKey };
  }

  const result = await api.post(
    endpoints.transcriptSignalsExtract,
    {
      activity_id: activityId,
      transcript: trimmedTranscript,
    },
    requestConfig,
  );

  // === 4. Response path dispatch ===

  // ---- 4a. HTTP 202 — another worker is already processing this key ----
  // The axios response interceptor enriches `response.data` with
  // __is202 / __poll_url / __idempotency_key when status == 202.
  if (result?.data?.__is202) {
    const pollResult = await handleBulkTimeout(
      { idempotencyKey: idempotencyKey || result.data.__idempotency_key },
      SIGNAL_LIST_PREFIXES,
      onProgress,
      null, // no onSyncComplete -- the resolved promise IS the completion signal
    );
    return mapPollResult(pollResult);
  }

  // ---- 4b. Sync HTTP 200 — pipeline finished within axios timeout ----
  if (result.success) {
    revalidateMultiple(SIGNAL_LIST_PREFIXES);
    const body = result.data || {};
    return {
      success: true,
      data: body.data || null,
    };
  }

  // ---- 4c. Client-side timeout — server may still be processing ----
  // Convention R3: polling fallback is mandatory for T4. We pass the
  // SAME idempotency key the request was sent with so /ops/{key}/
  // returns the server-side state for THIS operation.
  if (result.isTimeout) {
    const pollResult = await handleBulkTimeout(
      { idempotencyKey: idempotencyKey || result.idempotencyKey },
      SIGNAL_LIST_PREFIXES,
      onProgress,
      null,
    );
    return mapPollResult(pollResult);
  }

  // ---- 4d. HTTP 409 — ALREADY_EXTRACTED or IDEMPOTENCY_CONFLICT ----
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

  // ---- 4e. Other errors (400 validation, 500 server, 502/503/etc.) ----
  return {
    success: false,
    error: result.error,
    status: result.status ?? 0,
    response: result.response ?? null,
  };
}
