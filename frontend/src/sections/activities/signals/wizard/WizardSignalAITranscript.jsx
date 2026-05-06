// frontend/src/sections/activities/signals/wizard/WizardSignalAITranscript.jsx
/**
 * WizardSignalAITranscript — AI/transcript-driven entry point to signal capture.
 *
 * Sits beside WizardSignalAdd as a sibling wizard. Both target the same
 * destination (signal creation) via the same Validation step component
 * (WizardValidationStep), but follow different journeys:
 *
 *   WizardSignalAdd  : Capture (manual inline forms) → Validation
 *   WizardSignalAI…  : Review (transcript + alert) → Processing → Validation
 *
 * MVP scope:
 *   - Step 0 (Review)     : fully functional — transcript editable, alert,
 *                           "Include my notes" checkbox, Send button.
 *   - Step 1 (Processing) : placeholder — LLM channel not yet wired. User
 *                           must click "Continue to validation" to advance.
 *   - Step 2 (Validation) : fully wired — reuses WizardValidationStep,
 *                           dispatch logic mirrors WizardSignalAdd. In MVP
 *                           `staged` arrives empty (no LLM call), so the
 *                           empty state of WizardValidationStep renders.
 *
 * Future LLM integration (sprint dédié) — replace the placeholders with:
 *   1. A real LLM call inside handleSendToAI:
 *        const llmPayload = { transcript, notes: includeNotes ? initialNotes : null };
 *        const { signals } = await callLLMExtractor(llmPayload);
 *        setStaged(groupByType(signals));
 *        setActiveStep(STEP_VALIDATE);   // auto-advance on response
 *   2. The "Continue to validation" button on ProcessingStep becomes
 *      obsolete — drop it (or keep only as a manual fallback on error).
 *   3. SIGNAL_SOURCE constant flips to the agreed enum value (likely
 *      'LLM_TRANSCRIPT'). Coordinate with backend on the exact value.
 *   4. handleStartEdit gets a real implementation — either a sub-dialog
 *      rendering the relevant inline form, or a 4th step.
 *
 * Transcript editing is local to the wizard — edits are NOT persisted to
 * Activity.transcript. The rep can placeholdize sensitive data before each
 * LLM submission without altering the source-of-truth on the activity.
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
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import FormControlLabel from "@mui/material/FormControlLabel";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// ant-design icons
import ArrowLeftOutlined from "@ant-design/icons/ArrowLeftOutlined";
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import RobotOutlined from "@ant-design/icons/RobotOutlined";
import SendOutlined from "@ant-design/icons/SendOutlined";

// project imports
import { createSignal } from "api/signals/signals";
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
  "tech-stack": [],
};

/**
 * SignalSource value sent to the backend when this wizard dispatches signals.
 *
 * MVP value is 'MANUAL' because no LLM call runs yet — any signal that
 * happens to land in the validation step is effectively manually curated.
 *
 * TODO LLM SPRINT: switch to the appropriate SignalSource enum value for
 * AI-extracted signals (likely 'LLM_TRANSCRIPT' or similar). Backend
 * SignalSource enum exposes MANUAL / LLM_* / EXTERNAL_RESEARCH — coordinate
 * with backend on the exact value before flipping.
 */
const SIGNAL_SOURCE = "MANUAL";

// ==============================|| TRANSCRIPT REVIEW STEP ||============================== //

/**
 * Step 0 — TranscriptReview.
 *
 * Editable transcript area, LLM safety alert, "Include my notes" checkbox,
 * Send button. Calling onSendToAI advances the parent to STEP_PROCESSING.
 *
 * The notes themselves are not displayed inline — only their availability
 * is communicated through the checkbox label. Concatenation with the
 * transcript happens at LLM submission time (see parent handleSendToAI).
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
 * Step 1 — Processing (MVP placeholder).
 *
 * In MVP this step is a static placeholder — the LLM channel is not yet
 * wired. The user must click "Continue to validation" to advance manually.
 *
 * Once the LLM is plugged in, this step will:
 *   1. Display a real loading state while the LLM call resolves.
 *   2. Auto-advance to STEP_VALIDATE on response.
 *   3. Surface an error state on failure with retry / back options.
 */
function ProcessingStep({ onBackToReview, onContinue }) {
  return (
    <Stack
      spacing={2.5}
      sx={{ p: 3, alignItems: "center", textAlign: "center" }}
    >
      <RobotOutlined style={{ fontSize: 48, color: "#8c8c8c" }} />

      <Stack spacing={0.5} sx={{ maxWidth: 420 }}>
        <Typography variant="subtitle1" fontWeight={600}>
          AI extraction not yet integrated
        </Typography>
        <Typography variant="body2" color="text.secondary">
          The LLM channel is being built. The validation flow ahead is fully
          wired — once the LLM responds it will populate this wizard with
          extracted signals automatically.
        </Typography>
      </Stack>

      {/* Manual advance — replaced by auto-advance when LLM is wired */}
      <Stack direction="row" spacing={1.5} sx={{ pt: 1 }}>
        <Button
          variant="outlined"
          onClick={onBackToReview}
          startIcon={<ArrowLeftOutlined />}
        >
          Back to review
        </Button>
        <Button variant="contained" onClick={onContinue}>
          Continue to validation
        </Button>
      </Stack>
    </Stack>
  );
}

ProcessingStep.propTypes = {
  onBackToReview: PropTypes.func.isRequired,
  onContinue: PropTypes.func.isRequired,
};

// ==============================|| WIZARD SIGNAL AI TRANSCRIPT ||============================== //

/**
 * WizardSignalAITranscript
 *
 * @param {boolean}  open              - Dialog open state
 * @param {Function} onClose           - Called on close (no payload)
 * @param {Function} onSuccess         - Called after all signals dispatched successfully
 * @param {string}   accountId         - Account UUID — required for all signal creates
 * @param {Object}   choices           - From useGetSignalChoices() — forwarded to
 *                                        WizardValidationStep / future inline forms
 * @param {boolean}  choicesLoading
 * @param {Object}   extraPayload      - Injected into every signal at dispatch
 *                                        e.g. { source_activity, decision_cycle, campaign }
 * @param {string}   initialTranscript - Pre-fill content for the transcript area
 *                                        (typically activity.transcript from the parent)
 * @param {string}   initialNotes      - The activity's private notes — sent to the
 *                                        LLM only when the user opts in via the checkbox.
 *                                        Default: empty string.
 */
export default function WizardSignalAITranscript({
  open,
  onClose,
  onSuccess,
  accountId,
  choices,
  choicesLoading,
  extraPayload,
  initialTranscript = "",
  initialNotes = "",
}) {
  // ==============================|| STATE ||============================== //

  const [activeStep, setActiveStep] = useState(STEP_REVIEW);

  // Step 0 state
  const [transcript, setTranscript] = useState(initialTranscript);
  const [includeNotes, setIncludeNotes] = useState(false);

  // Step 2 state — mirrors WizardSignalAdd
  const [staged, setStaged] = useState(INITIAL_STAGED);
  const [submitting, setSubmitting] = useState(false);
  const [results, setResults] = useState(null);

  // Close-confirmation state
  const [confirmCloseOpen, setConfirmCloseOpen] = useState(false);

  // ==============================|| RESET ON OPEN ||============================== //

  useEffect(() => {
    if (open) {
      setActiveStep(STEP_REVIEW);
      setTranscript(initialTranscript);
      setIncludeNotes(false);
      setStaged(INITIAL_STAGED);
      setSubmitting(false);
      setResults(null);
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
      staged["tech-stack"].length,
    [staged],
  );

  // ==============================|| STEP 0 HANDLERS ||============================== //

  /**
   * "Send to AI" handler — STEP_REVIEW → STEP_PROCESSING.
   *
   * MVP: simply advance to STEP_PROCESSING — no actual LLM call.
   *
   * TODO LLM SPRINT: wire the real call here. Build the LLM payload from
   * the (potentially edited) transcript, append `initialNotes` only when
   * `includeNotes` is true, then auto-advance to STEP_VALIDATE on response.
   *
   *   const llmPayload = {
   *     transcript,
   *     notes: includeNotes ? initialNotes : null,
   *   };
   *   const { signals } = await callLLMExtractor(llmPayload);
   *   setStaged(groupByType(signals));
   *   setActiveStep(STEP_VALIDATE);
   */
  const handleSendToAI = useCallback(() => {
    setActiveStep(STEP_PROCESSING);
  }, []);

  // ==============================|| STEP 1 HANDLERS ||============================== //

  const handleBackToReview = useCallback(() => {
    setActiveStep(STEP_REVIEW);
  }, []);

  /**
   * Manual advance from STEP_PROCESSING to STEP_VALIDATE — MVP only.
   * In production, this transition will be triggered automatically by
   * the LLM response (see handleSendToAI TODO).
   */
  const handleContinueToValidation = useCallback(() => {
    setActiveStep(STEP_VALIDATE);
  }, []);

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
   * Edit handler — MVP placeholder.
   *
   * In the manual wizard, edit routes the user back to the capture step
   * with the inline form pre-loaded for the target signal. This wizard
   * has no capture step — once the LLM is wired, edit will need a
   * different surface (sub-dialog with the appropriate inline form, or a
   * dedicated 4th step).
   *
   * MVP: surface a clear placeholder snackbar. With empty staged in MVP,
   * this handler is unreachable in practice (no signals → no edit
   * buttons rendered by WizardValidationStep).
   */
  const handleStartEdit = useCallback(() => {
    displayWarningSnackbar(
      "Editing AI-extracted signals will be available once the LLM channel is wired.",
    );
  }, []);

  /** Back from STEP_VALIDATE — return to review so user can re-send. */
  const handleBackFromValidation = useCallback(() => {
    setActiveStep(STEP_REVIEW);
  }, []);

  // ==============================|| DISPATCH ||============================== //

  /**
   * Dispatch all VALIDATED staged signals to the backend.
   *
   * Logic mirrors WizardSignalAdd.handleConfirm:
   *   - account + source + extraPayload injected per-payload
   *   - Promise.allSettled — partial failures stay open for retry
   *   - On full success: onSuccess() + close
   *   - On partial failure: keep failed signals in staged, show errors
   *
   * In MVP, staged is empty (no LLM call) — this handler is effectively
   * unreachable. It is wired in full so the LLM sprint can plug responses
   * into staged without further changes here.
   */
  const handleConfirm = useCallback(async () => {
    const toDispatch = Object.entries(staged).flatMap(([type, signals]) =>
      signals
        .filter((s) => s._status === "VALIDATED")
        .map((s) => ({ type, signal: s })),
    );

    if (toDispatch.length === 0) return;

    setSubmitting(true);

    const settled = await Promise.allSettled(
      toDispatch.map(async ({ type, signal }) => {
        // Strip wizard-managed metadata
        const { _key, _status, ...payload } = signal;

        // Normalize relation FK fields — same downcasting as WizardSignalAdd.
        if (
          payload.target_contact &&
          typeof payload.target_contact === "object"
        ) {
          payload.target_contact = payload.target_contact.id;
        }
        if (
          payload.source_activity &&
          typeof payload.source_activity === "object"
        ) {
          payload.source_activity = payload.source_activity.id;
        }
        if (
          payload.tech_catalog_entry &&
          typeof payload.tech_catalog_entry === "object"
        ) {
          payload.tech_catalog_entry = payload.tech_catalog_entry.id;
        }
        if (
          payload.related_techstack &&
          typeof payload.related_techstack === "object"
        ) {
          payload.related_techstack = payload.related_techstack.id;
        }

        const result = await createSignal(type, {
          ...payload,
          account: accountId,
          source: SIGNAL_SOURCE,
          ...(extraPayload ?? {}),
        });

        return { _key, type, result };
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
        });
      } else if (outcome.status === "fulfilled") {
        failed.push({
          _key: outcome.value._key,
          type: outcome.value.type,
          error: outcome.value.result.error ?? "Failed to create signal",
        });
      } else {
        const original = toDispatch[index];
        failed.push({
          _key: original?.signal._key,
          type: original?.type,
          error: "Network error — please check your connection and retry",
        });
      }
    });

    if (failed.length === 0) {
      displaySuccessSnackbar(
        `${succeeded.length} signal${succeeded.length === 1 ? "" : "s"} created successfully`,
      );
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
      displayWarningSnackbar(`${failed.length} signals failed to save.`);
    }
  }, [staged, accountId, extraPayload, onSuccess, onClose]);

  // ==============================|| STEPPER ||============================== //

  /**
   * Step navigation policy:
   *  - Review is always reachable.
   *  - Processing is reachable from Review (forward) and from Validate (back).
   *  - Validate is always reachable per product directive — even with empty
   *    staged, the user can inspect the validation surface to understand the
   *    full flow.
   *
   * Direct skips (Review → Validate without sending) are not blocked here.
   */
  const handleStepClick = useCallback((idx) => {
    setActiveStep(idx);
    if (idx !== STEP_VALIDATE) setResults(null);
  }, []);

  // ==============================|| CLOSE FLOW ||============================== //

  const handleClose = useCallback(() => {
    if (submitting) return;
    if (totalStaged > 0) {
      setConfirmCloseOpen(true);
      return;
    }
    onClose();
  }, [onClose, submitting, totalStaged]);

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
            onBackToReview={handleBackToReview}
            onContinue={handleContinueToValidation}
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

      {/* ==================== CLOSE CONFIRMATION ==================== */}
      <Dialog
        open={confirmCloseOpen}
        onClose={handleCloseDismiss}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Discard staged signals?</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary">
            You have {totalStaged} staged signal
            {totalStaged === 1 ? "" : "s"} that have not been saved yet. Closing
            the wizard will discard them permanently.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={handleCloseDismiss} color="inherit" size="small">
            Keep editing
          </Button>
          <Button
            onClick={handleCloseConfirm}
            color="error"
            variant="contained"
            size="small"
          >
            Discard & close
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
  choices: PropTypes.object,
  choicesLoading: PropTypes.bool,
  extraPayload: PropTypes.object,
  initialTranscript: PropTypes.string,
  initialNotes: PropTypes.string,
};
