// frontend/src/sections/activities/signals/wizard/WizardSignalAITranscript.jsx
/**
 * WizardSignalAITranscript — AI/transcript-driven entry point to signal capture.
 *
 * Sits beside WizardSignalAdd as a sibling wizard. Both target the same
 * destination (a curated set of signals on the activity) via the same
 * Validation step component (WizardValidationStep), but follow opposite
 * journeys regarding signal lifecycle:
 *
 *   WizardSignalAdd  : Capture → Validation
 *                      Signals do NOT exist in DB. The wizard stages them
 *                      locally and `createSignal()` is dispatched on confirm.
 *
 *   WizardSignalAITranscript : Review → Processing → Validate
 *                              The backend pipeline CREATES the signals in
 *                              DB as PENDING. The wizard validates them:
 *                              `validateSignal()` for accepted ones,
 *                              `deleteSignal()` for rejected ones.
 *                              No createSignal is ever called from here.
 *
 * Tier T4 conventions (see backend/core/timeout_conventions.py):
 *   R3 Polling fallback — handled inside extractTranscriptSignals
 *   R4 Deterministic key — handled inside extractTranscriptSignals
 *   R5 UX wait pattern   — wizard stays open during entire extraction
 *                          and polling. Close-during-extraction shows
 *                          confirmation; the backend operation continues.
 *
 * State machine on the Processing step:
 *
 *                            ┌──────────────────────┐
 *                            │ idle (Review step)   │
 *                            └──────────┬───────────┘
 *                                       │  Send to AI
 *                                       ▼
 *                            ┌──────────────────────┐
 *                            │ running              │
 *                            │ (sync window <60s)   │
 *                            └──────────┬───────────┘
 *                                       │  axios timeout
 *                                       ▼
 *                            ┌──────────────────────┐
 *                            │ polling              │
 *                            │ (≤3 min, attempt n/m)│
 *                            └──┬─────────┬─────────┘
 *                               │         │
 *           ┌───────────────────┘         └─────────────────────┐
 *           │ success                     │ error / timeout / dedup
 *           ▼                             ▼
 *  ┌─────────────────┐         ┌────────────────────────────────┐
 *  │ → STEP_VALIDATE │         │ STEP_PROCESSING + banner       │
 *  │   staged is     │         │  • ALREADY_EXTRACTED → info    │
 *  │   populated     │         │  • TIMEOUT_PENDING   → warn    │
 *  │   from result   │         │  • REPLAY_FAILED     → error   │
 *  └─────────────────┘         │  • other             → error   │
 *                              └────────────────────────────────┘
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo, useEffect } from "react";

// material-ui
import Alert from "@mui/material/Alert";
import AlertTitle from "@mui/material/AlertTitle";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import FormControlLabel from "@mui/material/FormControlLabel";
import IconButton from "@mui/material/IconButton";
import LinearProgress from "@mui/material/LinearProgress";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// ant-design icons
import ArrowLeftOutlined from "@ant-design/icons/ArrowLeftOutlined";
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import InfoCircleOutlined from "@ant-design/icons/InfoCircleOutlined";
import SendOutlined from "@ant-design/icons/SendOutlined";
import WarningOutlined from "@ant-design/icons/WarningOutlined";

// project imports
import { validateSignal, deleteSignal } from "api/signals/signals";
import {
  extractTranscriptSignals,
  EXTRACTION_OUTCOME_CODES,
} from "api/aiPipelines/transcriptSignals";
import {
  displaySuccessSnackbar,
  displayWarningSnackbar,
} from "utils/displayError";

import WizardStepper from "./WizardStepper";
import WizardValidationStep from "./WizardValidationStep";

// ==============================|| CONSTANTS ||============================== //

const WIZARD_STEPS = [
  { key: "review", label: "Review" },
  { key: "processing", label: "Processing" },
  { key: "validate", label: "Validate" },
];

const STEP_REVIEW = 0;
const STEP_PROCESSING = 1;
const STEP_VALIDATE = 2;

const INITIAL_STAGED = {
  pain: [],
  objective: [],
  impact: [],
  "tech-stack": [],
};

// ==============================|| TRANSCRIPT REVIEW STEP ||============================== //

/**
 * Step 0 — TranscriptReview.
 *
 * Editable transcript area, LLM safety alert, "Include my notes" checkbox,
 * Send button. Calling onSendToAI triggers the real extraction pipeline.
 *
 * The notes themselves are not displayed inline — only their availability
 * is communicated through the checkbox label. Concatenation with the
 * transcript happens at LLM submission time (sprint LLM future scope —
 * MVP backend ignores notes and only consumes the transcript).
 */
function TranscriptReviewStep({
  transcript,
  onTranscriptChange,
  includeNotes,
  onIncludeNotesChange,
  hasNotes,
  onSendToAI,
}) {
  const isEmpty = !transcript?.trim();

  return (
    <Stack spacing={2.5} sx={{ p: 3 }}>
      {/* Safety alert */}
      <Alert severity="warning" variant="outlined">
        <AlertTitle sx={{ mb: 0.5 }}>External LLM processing</AlertTitle>
        <Typography variant="body2" color="text.secondary">
          This content will be sent to an external Large Language Model for
          analysis. Before continuing, remove or replace with placeholders any
          sensitive elements: contact names, monetary amounts, contractual
          terms, internal credentials, or any data your organisation considers
          confidential.
        </Typography>
      </Alert>

      {/* Transcript editor */}
      <Box>
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ mb: 0.5, display: "block" }}
        >
          Transcript ({transcript?.length ?? 0} characters)
        </Typography>
        <TextField
          fullWidth
          multiline
          minRows={12}
          maxRows={20}
          value={transcript}
          onChange={(e) => onTranscriptChange(e.target.value)}
          placeholder="Paste or edit your transcript here..."
          variant="outlined"
        />
      </Box>

      {/* Include notes checkbox */}
      <FormControlLabel
        control={
          <Checkbox
            checked={includeNotes}
            onChange={(e) => onIncludeNotesChange(e.target.checked)}
            disabled={!hasNotes}
            size="small"
          />
        }
        label={
          <Typography variant="body2" color="text.secondary">
            Include my private notes{" "}
            {hasNotes
              ? "(available on this activity)"
              : "(none on this activity)"}
          </Typography>
        }
      />

      {/* Send button */}
      <Stack direction="row" justifyContent="flex-end">
        <Button
          variant="contained"
          color="primary"
          startIcon={<SendOutlined />}
          onClick={onSendToAI}
          disabled={isEmpty}
        >
          Send to AI
        </Button>
      </Stack>
    </Stack>
  );
}

TranscriptReviewStep.propTypes = {
  transcript: PropTypes.string.isRequired,
  onTranscriptChange: PropTypes.func.isRequired,
  includeNotes: PropTypes.bool.isRequired,
  onIncludeNotesChange: PropTypes.func.isRequired,
  hasNotes: PropTypes.bool.isRequired,
  onSendToAI: PropTypes.func.isRequired,
};

// ==============================|| PROCESSING STEP ||============================== //

/**
 * Step 1 — Processing.
 *
 * Renders one of several states based on the extraction lifecycle:
 *
 *   running           : initial backend call in flight (sync ≤ 60s)
 *   polling           : axios timed out, frontend polling /ops/{key}/
 *   already_extracted : backend layer-2 DB dedup hit (409)
 *   timeout_pending   : polling exhausted, server still working
 *   replay_failed     : previous attempt failed (Redis-cached error)
 *   error             : generic failure (network, validation, server)
 *
 * On success the parent auto-advances to STEP_VALIDATE — this component
 * does not render a success state itself.
 */
function ProcessingStep({
  extracting,
  pollProgress,
  extractionResult,
  onBackToReview,
  onRetry,
}) {
  // ---- In-flight: extraction is running (sync or polling) ----
  if (extracting) {
    const isPolling = Boolean(pollProgress && pollProgress.max > 0);
    return (
      <Stack
        spacing={2.5}
        sx={{ p: 3, alignItems: "center", textAlign: "center" }}
      >
        <CircularProgress size={48} />
        <Stack spacing={0.5} sx={{ maxWidth: 460 }}>
          <Typography variant="subtitle1" fontWeight={600}>
            {isPolling
              ? "Still processing..."
              : "Analyzing transcript with AI..."}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {isPolling
              ? `This is taking longer than expected — we're polling for the result (attempt ${pollProgress.attempt} of ${pollProgress.max}).`
              : "The AI is extracting signals from your transcript. This typically takes 10 seconds to 3 minutes depending on transcript length."}
          </Typography>
        </Stack>
        {isPolling && (
          <Box sx={{ width: "100%", maxWidth: 360 }}>
            <LinearProgress
              variant="determinate"
              value={Math.min(
                100,
                (pollProgress.attempt / pollProgress.max) * 100,
              )}
            />
          </Box>
        )}
      </Stack>
    );
  }

  // ---- Non-success outcomes after extraction completed ----
  if (!extractionResult) return null; // defensive — shouldn't happen

  const code = extractionResult.code;
  const dedupData = extractionResult.data;

  if (code === EXTRACTION_OUTCOME_CODES.ALREADY_EXTRACTED) {
    const createdAt = dedupData?.created_at
      ? new Date(dedupData.created_at).toLocaleDateString()
      : null;
    const signalsCount = dedupData?.created_signals_count;
    return (
      <Stack
        spacing={2.5}
        sx={{ p: 3, alignItems: "center", textAlign: "center" }}
      >
        <InfoCircleOutlined style={{ fontSize: 48, color: "#1890ff" }} />
        <Stack spacing={0.5} sx={{ maxWidth: 460 }}>
          <Typography variant="subtitle1" fontWeight={600}>
            This transcript was already processed
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {createdAt ? `Extraction ran on ${createdAt}. ` : ""}
            {signalsCount > 0
              ? `${signalsCount} signal${signalsCount === 1 ? "" : "s"} are available in the Signals section. `
              : ""}
            To extract again, edit the transcript so it differs from the
            previous attempt.
          </Typography>
        </Stack>
        <Stack direction="row" spacing={1.5} sx={{ pt: 1 }}>
          <Button
            variant="outlined"
            onClick={onBackToReview}
            startIcon={<ArrowLeftOutlined />}
          >
            Back to transcript
          </Button>
        </Stack>
      </Stack>
    );
  }

  if (code === EXTRACTION_OUTCOME_CODES.TIMEOUT_PENDING) {
    return (
      <Stack
        spacing={2.5}
        sx={{ p: 3, alignItems: "center", textAlign: "center" }}
      >
        <WarningOutlined style={{ fontSize: 48, color: "#faad14" }} />
        <Stack spacing={0.5} sx={{ maxWidth: 460 }}>
          <Typography variant="subtitle1" fontWeight={600}>
            Operation still running
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {extractionResult.error ||
              "The extraction is taking longer than expected. It will complete in the background — refresh the Signals section in a moment to see the results."}
          </Typography>
        </Stack>
        <Stack direction="row" spacing={1.5} sx={{ pt: 1 }}>
          <Button
            variant="outlined"
            onClick={onBackToReview}
            startIcon={<ArrowLeftOutlined />}
          >
            Back to transcript
          </Button>
          <Button variant="contained" onClick={onRetry}>
            Retry
          </Button>
        </Stack>
      </Stack>
    );
  }

  if (code === EXTRACTION_OUTCOME_CODES.IDEMPOTENCY_REPLAY_FAILED) {
    return (
      <Stack
        spacing={2.5}
        sx={{ p: 3, alignItems: "center", textAlign: "center" }}
      >
        <WarningOutlined style={{ fontSize: 48, color: "#cf1322" }} />
        <Stack spacing={0.5} sx={{ maxWidth: 460 }}>
          <Typography variant="subtitle1" fontWeight={600}>
            Previous attempt failed
          </Typography>
          <Typography variant="body2" color="text.secondary">
            A previous attempt with this transcript failed. Wait a few minutes
            (~10 min) before retrying, or edit the transcript to trigger a fresh
            attempt.
          </Typography>
          {extractionResult.error && (
            <Typography
              variant="caption"
              color="text.disabled"
              sx={{ mt: 1, fontStyle: "italic" }}
            >
              Detail: {extractionResult.error}
            </Typography>
          )}
        </Stack>
        <Stack direction="row" spacing={1.5} sx={{ pt: 1 }}>
          <Button
            variant="outlined"
            onClick={onBackToReview}
            startIcon={<ArrowLeftOutlined />}
          >
            Back to transcript
          </Button>
          <Button variant="contained" onClick={onRetry}>
            Retry
          </Button>
        </Stack>
      </Stack>
    );
  }

  // Generic error fallback (network, validation, server, IDEMPOTENCY_CONFLICT, etc.)
  return (
    <Stack
      spacing={2.5}
      sx={{ p: 3, alignItems: "center", textAlign: "center" }}
    >
      <WarningOutlined style={{ fontSize: 48, color: "#cf1322" }} />
      <Stack spacing={0.5} sx={{ maxWidth: 460 }}>
        <Typography variant="subtitle1" fontWeight={600}>
          Extraction failed
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {extractionResult.error ||
            "An unexpected error occurred while extracting signals from the transcript."}
        </Typography>
      </Stack>
      <Stack direction="row" spacing={1.5} sx={{ pt: 1 }}>
        <Button
          variant="outlined"
          onClick={onBackToReview}
          startIcon={<ArrowLeftOutlined />}
        >
          Back to transcript
        </Button>
        <Button variant="contained" onClick={onRetry}>
          Retry
        </Button>
      </Stack>
    </Stack>
  );
}

ProcessingStep.propTypes = {
  extracting: PropTypes.bool.isRequired,
  pollProgress: PropTypes.shape({
    attempt: PropTypes.number,
    max: PropTypes.number,
  }),
  extractionResult: PropTypes.object,
  onBackToReview: PropTypes.func.isRequired,
  onRetry: PropTypes.func.isRequired,
};

// ==============================|| WIZARD SIGNAL AI TRANSCRIPT ||============================== //

/**
 * WizardSignalAITranscript
 *
 * @param {boolean}  open               - Dialog open state
 * @param {Function} onClose            - Called on close (no payload)
 * @param {Function} onSuccess          - Called after dispatch completes successfully
 * @param {string}   accountId          - Account UUID (kept for parity / future use)
 * @param {string}   activityId         - Activity UUID — required for the extraction call
 * @param {Object}   choices            - From useGetSignalChoices() — currently unused
 *                                        directly but kept for future inline edit support
 * @param {boolean}  choicesLoading
 * @param {string}   initialTranscript  - Pre-fill content for the transcript area
 *                                        (typically activity.transcript)
 * @param {string}   initialNotes       - The activity's private notes — referenced by
 *                                        the "Include my notes" checkbox label only.
 *                                        Backend MVP ignores notes; future LLM sprint
 *                                        may concatenate them into the prompt.
 * @param {Function} onSignalEdit       - Optional bubble-up edit handler:
 *                                        (signal, signalType) => void
 *                                        Called when the user clicks Edit on a card
 *                                        in the Validation step. Parent typically
 *                                        opens its existing SignalEditDialog.
 */
export default function WizardSignalAITranscript({
  open,
  onClose,
  onSuccess,
  // eslint-disable-next-line no-unused-vars
  accountId,
  activityId,
  // eslint-disable-next-line no-unused-vars
  choices,
  // eslint-disable-next-line no-unused-vars
  choicesLoading,
  initialTranscript = "",
  initialNotes = "",
  onSignalEdit,
}) {
  // ==============================|| STATE ||============================== //

  const [activeStep, setActiveStep] = useState(STEP_REVIEW);

  // Step 0 — Review state
  const [transcript, setTranscript] = useState(initialTranscript);
  const [includeNotes, setIncludeNotes] = useState(false);

  // Step 1 — Processing state
  const [extracting, setExtracting] = useState(false);
  const [pollProgress, setPollProgress] = useState(null); // { attempt, max } | null
  const [extractionResult, setExtractionResult] = useState(null);

  // Step 2 — Validation state (post-extraction lifecycle dispatch)
  const [staged, setStaged] = useState(INITIAL_STAGED);
  const [submitting, setSubmitting] = useState(false);
  const [results, setResults] = useState(null);

  // Close confirmation — only used while extraction is in flight
  const [confirmCloseOpen, setConfirmCloseOpen] = useState(false);

  // ==============================|| RESET ON OPEN ||============================== //

  useEffect(() => {
    if (open) {
      setActiveStep(STEP_REVIEW);
      setTranscript(initialTranscript);
      setIncludeNotes(false);
      setExtracting(false);
      setPollProgress(null);
      setExtractionResult(null);
      setStaged(INITIAL_STAGED);
      setSubmitting(false);
      setResults(null);
      setConfirmCloseOpen(false);
    }
  }, [open, initialTranscript]);

  // ==============================|| DERIVED ||============================== //

  const hasNotes = useMemo(
    () => Boolean(initialNotes && initialNotes.trim()),
    [initialNotes],
  );

  const totalStaged = useMemo(
    () =>
      staged.pain.length +
      staged.objective.length +
      staged.impact.length +
      staged["tech-stack"].length,
    [staged],
  );

  // ==============================|| EXTRACTION FLOW ||============================== //

  /**
   * Convert the backend's signals_by_stage payload into the wizard's
   * staged shape. Each backend signal already has a real `id` from the
   * pipeline-created PENDING row — we use it as the wizard's local `_key`
   * for uniqueness and ergonomics (lookups during dispatch use signal.id).
   *
   * Default _status is VALIDATED ("include by default") — the user
   * toggles Excluded on any signal they want to drop.
   *
   * The local `next` shape mirrors INITIAL_STAGED — adding a new
   * signal type only requires extending that constant; this builder
   * picks it up automatically via Object.keys.
   */
  const buildStagedFromExtraction = useCallback((signalsByStage) => {
    const next = { pain: [], objective: [], impact: [], "tech-stack": [] };
    for (const type of Object.keys(next)) {
      const backendList = signalsByStage?.[type] ?? [];
      next[type] = backendList.map((sig) => ({
        ...sig,
        _key: sig.id, // real DB id — guaranteed unique per signal
        _status: "VALIDATED",
      }));
    }
    return next;
  }, []);

  /**
   * Polling progress callback wired into extractTranscriptSignals.
   * Called once per polling attempt; flips the Processing step from
   * "running" presentation to "polling" presentation.
   */
  const handlePollProgress = useCallback((attempt, max) => {
    setPollProgress({ attempt, max });
  }, []);

  /**
   * Send-to-AI handler — STEP_REVIEW → STEP_PROCESSING.
   *
   * Calls the real extraction pipeline. Outcomes:
   *   success                       → populate staged, auto-advance to STEP_VALIDATE
   *   ALREADY_EXTRACTED             → stay on STEP_PROCESSING with info banner
   *   TIMEOUT_PENDING               → stay with warning banner
   *   IDEMPOTENCY_REPLAY_FAILED     → stay with error banner + wait hint
   *   other error                   → stay with generic error banner + Retry
   *
   * Per Convention R4 (T4 / deterministic key), the call is idempotent
   * within Redis TTL — re-clicking returns the cached result instantly
   * without re-spending LLM tokens.
   */
  const handleSendToAI = useCallback(async () => {
    // Clear any prior extraction state so re-run repopulates cleanly
    setStaged(INITIAL_STAGED);
    setResults(null);
    setExtractionResult(null);
    setPollProgress(null);

    setActiveStep(STEP_PROCESSING);
    setExtracting(true);

    let result;
    try {
      result = await extractTranscriptSignals(
        activityId,
        transcript,
        handlePollProgress,
      );
    } catch (err) {
      // extractTranscriptSignals handles its own errors and returns a
      // result envelope. A thrown exception here would be a programmer
      // error in the helper itself — surface it as a generic failure.
      result = {
        success: false,
        error: err?.message || "Unexpected error during extraction.",
      };
    }

    setExtracting(false);

    // Success path → populate staged + advance to Validate
    if (result.success) {
      const built = buildStagedFromExtraction(result.data?.signals_by_stage);
      setStaged(built);
      setExtractionResult(result);
      setActiveStep(STEP_VALIDATE);
      return;
    }

    // Non-success → stay on Processing with the appropriate banner
    setExtractionResult(result);
  }, [activityId, transcript, handlePollProgress, buildStagedFromExtraction]);

  // ==============================|| STEP 1 HANDLERS ||============================== //

  const handleBackToReview = useCallback(() => {
    setActiveStep(STEP_REVIEW);
    setExtractionResult(null);
    setPollProgress(null);
    // Don't clear staged here — simple navigation back to review preserves
    // any user toggles. Staged is cleared at the start of handleSendToAI
    // when the user actually re-extracts.
  }, []);

  const handleRetryExtraction = useCallback(() => {
    handleSendToAI();
  }, [handleSendToAI]);

  // ==============================|| STEP 2 HANDLERS — STAGED MUTATIONS ||============================== //

  /** Toggle a staged signal's _status between VALIDATED and REJECTED. */
  const handleToggleStatus = useCallback((type, key) => {
    setStaged((prev) => ({
      ...prev,
      [type]: prev[type].map((s) =>
        s._key === key
          ? {
              ...s,
              _status: s._status === "VALIDATED" ? "REJECTED" : "VALIDATED",
            }
          : s,
      ),
    }));
  }, []);

  /**
   * Edit handler — bubbles up to the parent via onSignalEdit prop.
   *
   * The parent (WrapUpCaptureSection) wires its existing handleEdit,
   * which opens its existing SignalEditDialog with the appropriate
   * inline form. This avoids duplicating the edit surface inside the
   * wizard.
   *
   * Trade-off: the wizard's staged state is NOT synced with the edit
   * result — displayed text may go stale after a save. Acceptable for
   * MVP because:
   *   - signal.id is unchanged → dispatch (validate/delete) still
   *     targets the right row regardless of stale display
   *   - the user just edited; they remember what they typed
   *   - closing & re-opening shows fresh data via re-fetch
   */
  const handleStartEdit = useCallback(
    (type, _key) => {
      const signal = (staged[type] ?? []).find((s) => s._key === _key);
      if (!signal) return;

      if (typeof onSignalEdit === "function") {
        // Strip wizard-managed metadata before bubbling up
        // eslint-disable-next-line no-unused-vars
        const { _key: _omitKey, _status: _omitStatus, ...rest } = signal;
        onSignalEdit(rest, type);
      } else {
        // No handler provided — degraded mode (shouldn't happen in normal use)
        displayWarningSnackbar("Editing is unavailable in this context.");
      }
    },
    [staged, onSignalEdit],
  );

  /** Back from STEP_VALIDATE — return to Review (transcript still pre-filled). */
  const handleBackFromValidation = useCallback(() => {
    setActiveStep(STEP_REVIEW);
  }, []);

  // ==============================|| DISPATCH (VALIDATE / DELETE) ||============================== //

  /**
   * Dispatch all staged signals to the backend.
   *
   * Lifecycle transitions (NOT creates — signals already exist as PENDING):
   *   _status === 'VALIDATED' → validateSignal()  (PENDING → VALIDATED)
   *   _status === 'REJECTED'  → deleteSignal()    (row removed; silent MVP)
   *
   * Uses Promise.allSettled so partial failures keep the wizard open
   * with succeeded signals removed from staged and failed ones still
   * visible with their error message.
   */
  const handleConfirm = useCallback(async () => {
    // ALL staged signals participate — VALIDATED ones get validated,
    // REJECTED ones get deleted. (In WizardSignalAdd we only dispatched
    // VALIDATED; here REJECTED also has a destination.)
    const toDispatch = Object.entries(staged).flatMap(([type, signals]) =>
      signals.map((s) => ({ type, signal: s })),
    );

    if (toDispatch.length === 0) return;

    setSubmitting(true);

    const settled = await Promise.allSettled(
      toDispatch.map(async ({ type, signal }) => {
        const action = signal._status === "REJECTED" ? "delete" : "validate";

        const result =
          action === "validate"
            ? await validateSignal(type, signal.id)
            : await deleteSignal(type, signal.id);

        return { _key: signal._key, type, action, result };
      }),
    );

    setSubmitting(false);

    const succeeded = [];
    const failed = [];

    settled.forEach((outcome, index) => {
      if (outcome.status === "fulfilled" && outcome.value.result.success) {
        succeeded.push({
          _key: outcome.value._key,
          type: outcome.value.type,
          action: outcome.value.action, // ← propagate the operation type
        });
      } else if (outcome.status === "fulfilled") {
        // Request completed but backend returned an error envelope.
        const fallback =
          outcome.value.action === "delete"
            ? "Failed to reject signal"
            : "Failed to validate signal";
        failed.push({
          _key: outcome.value._key,
          type: outcome.value.type,
          error: outcome.value.result.error ?? fallback,
        });
      } else {
        // Promise itself rejected — network error, timeout, etc.
        const original = toDispatch[index];
        failed.push({
          _key: original?.signal._key,
          type: original?.type,
          error: "Network error — please check your connection and retry",
        });
      }
    });

    if (failed.length === 0) {
      // Split counts to be precise: validated signals are kept, rejected
      // ones are deleted. "Processed" was ambiguous and read as "saved",
      // which over-counted the saves whenever a rejection was in the batch.
      const validatedCount = succeeded.filter(
        (s) => s.action === "validate",
      ).length;
      const rejectedCount = succeeded.filter(
        (s) => s.action === "delete",
      ).length;

      let message;
      if (rejectedCount === 0) {
        message = `${validatedCount} signal${validatedCount === 1 ? "" : "s"} validated`;
      } else if (validatedCount === 0) {
        message = `${rejectedCount} signal${rejectedCount === 1 ? "" : "s"} rejected`;
      } else {
        message = `${validatedCount} validated, ${rejectedCount} rejected`;
      }

      displaySuccessSnackbar(message);
      onSuccess();
      onClose();
      return;
    }

    // Partial failure — remove succeeded from staged, keep failed for retry
    const succeededKeys = new Set(succeeded.map((s) => s._key));

    setStaged((prev) => {
      const next = {};
      for (const type of Object.keys(prev)) {
        next[type] = prev[type].filter((s) => !succeededKeys.has(s._key));
      }
      return next;
    });

    setResults({ succeeded, failed });

    if (failed.length === 1) {
      displayWarningSnackbar(failed[0].error);
    } else {
      displayWarningSnackbar(`${failed.length} signals failed to process.`);
    }
  }, [staged, onSuccess, onClose]);

  // ==============================|| STEPPER NAVIGATION ||============================== //

  const handleStepClick = useCallback(
    (idx) => {
      // Block navigation while any in-flight operation is running.
      // Extraction continues in background even if the wizard closes,
      // so a forced cancel from the stepper would be confusing.
      if (extracting || submitting) return;

      // Can't jump forward to Processing without a context (an extraction
      // having been started or completed). Can't jump to Validate without
      // staged signals.
      if (idx === STEP_PROCESSING && !extractionResult) return;
      if (idx === STEP_VALIDATE && totalStaged === 0) return;

      setActiveStep(idx);

      // Navigating to Review wipes the extraction result so the
      // Processing step doesn't surface a stale banner if revisited.
      if (idx === STEP_REVIEW) {
        setExtractionResult(null);
        setPollProgress(null);
      }
      if (idx !== STEP_VALIDATE) setResults(null);
    },
    [extracting, submitting, extractionResult, totalStaged],
  );

  // ==============================|| CLOSE FLOW ||============================== //

  const handleClose = useCallback(() => {
    // Block close during dispatch — would orphan the Promise.allSettled
    if (submitting) return;

    // Confirm before closing during extraction — server continues but
    // the user might mistake closing for cancelling, so we warn.
    if (extracting) {
      setConfirmCloseOpen(true);
      return;
    }

    // Otherwise (idle on any step, or post-extraction with staged
    // signals not yet validated) — just close. Staged signals stay as
    // PENDING in DB; the user can pick them up later from the Signals
    // section. No data loss.
    onClose();
  }, [onClose, submitting, extracting]);

  const handleCloseConfirm = useCallback(() => {
    setConfirmCloseOpen(false);
    onClose();
  }, [onClose]);

  const handleCloseDismiss = useCallback(() => {
    setConfirmCloseOpen(false);
  }, []);

  // ==============================|| RENDER ||============================== //

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          height: "min(80vh, 720px)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        },
      }}
    >
      {/* ==================== HEADER ==================== */}
      <DialogTitle sx={{ px: 3, py: 2, flexShrink: 0 }}>
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
        >
          <Stack spacing={0.25}>
            <Typography variant="h6" fontWeight={600}>
              Extract Signals from Transcript
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Review the transcript, send it for AI analysis, then validate the
              result.
            </Typography>
          </Stack>
          <IconButton
            size="small"
            onClick={handleClose}
            disabled={submitting}
            aria-label="Close wizard"
          >
            <CloseOutlined style={{ fontSize: 16 }} />
          </IconButton>
        </Stack>
      </DialogTitle>

      <Divider sx={{ flexShrink: 0 }} />

      {/* ==================== STEPPER ==================== */}
      <Box sx={{ flexShrink: 0 }}>
        <WizardStepper
          steps={WIZARD_STEPS}
          activeStep={activeStep}
          onStepClick={handleStepClick}
        />
      </Box>

      <Divider sx={{ flexShrink: 0 }} />

      {/* ==================== STEP CONTENT ==================== */}
      <DialogContent sx={{ p: 0, flex: 1, overflow: "auto" }}>
        {activeStep === STEP_REVIEW && (
          <TranscriptReviewStep
            transcript={transcript}
            onTranscriptChange={setTranscript}
            includeNotes={includeNotes}
            onIncludeNotesChange={setIncludeNotes}
            hasNotes={hasNotes}
            onSendToAI={handleSendToAI}
          />
        )}

        {activeStep === STEP_PROCESSING && (
          <ProcessingStep
            extracting={extracting}
            pollProgress={pollProgress}
            extractionResult={extractionResult}
            onBackToReview={handleBackToReview}
            onRetry={handleRetryExtraction}
          />
        )}

        {activeStep === STEP_VALIDATE && (
          <WizardValidationStep
            staged={staged}
            onToggleStatus={handleToggleStatus}
            onEdit={handleStartEdit}
            onBackClick={handleBackFromValidation}
            onConfirm={handleConfirm}
            submitting={submitting}
            results={results}
          />
        )}
      </DialogContent>

      {/* ==================== CLOSE CONFIRMATION (during extraction only) ==================== */}
      <Dialog
        open={confirmCloseOpen}
        onClose={handleCloseDismiss}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Close while extracting?</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary">
            The AI extraction will continue running in the background. You can
            come back to the Signals section in a few moments to see the
            results.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={handleCloseDismiss} color="inherit" size="small">
            Keep waiting
          </Button>
          <Button
            onClick={handleCloseConfirm}
            color="warning"
            variant="contained"
            size="small"
          >
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Dialog>
  );
}

// ==============================|| PROP TYPES ||============================== //

WizardSignalAITranscript.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onSuccess: PropTypes.func.isRequired,
  accountId: PropTypes.string.isRequired,
  activityId: PropTypes.string.isRequired,
  choices: PropTypes.object,
  choicesLoading: PropTypes.bool,
  initialTranscript: PropTypes.string,
  initialNotes: PropTypes.string,
  onSignalEdit: PropTypes.func,
};
