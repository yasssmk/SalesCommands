// frontend/src/sections/activities/signals/wizard/WizardSignalAdd.jsx
/**
 * WizardSignalAdd — main container for the multi-section signal capture wizard.
 *
 * Rendered as a Dialog (centered modal) with a 2-step Apple-style flow:
 *   STEP 0 — Capture     : segmented control + 3 sections (Pain / Objective / TechStack)
 *                          + footer "Ready X/Y" + "Review →"
 *   STEP 1 — Validation  : recap grouped by type, Include/Exclude toggles,
 *                          edit-back to Capture, Save dispatch
 *
 * Refactored from the legacy Drawer-based wizard:
 *   - Drawer → Dialog (Apple-style stepper at the top)
 *   - WizardNav → removed (replaced by the segmented control inside
 *                  WizardCaptureStep)
 *   - WizardSummary → WizardValidationStep (renamed + adapted)
 *   - defaultSection prop dropped — entry is always at Capture step
 *   - defaultContact prop dropped — no inline form drives source_contact
 *     anymore (standardisation refactor: source_contact retired from
 *     BaseSignal)
 *   - Dispatch cleanup: removed the zombie source_contact UUID-extract
 *     guard (the field is no longer present in any inline form payload)
 *
 * Staged signal shape:
 *   { _key: string, _status: 'VALIDATED'|'REJECTED', ...payload }
 *
 * At dispatch time:
 *   - Only VALIDATED signals are sent
 *   - account + source + extraPayload injected into each payload here
 *   - Promise.allSettled — partial failures stay open for retry
 *   - On full success: onSuccess() + reset + close
 *
 * Partial failure behaviour:
 *   - Succeeded signals removed from staged (already created)
 *   - Failed signals kept in staged with their error displayed in
 *     WizardValidationStep
 *   - User can toggle failed signals to REJECTED to skip them, then
 *     retry
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo, useEffect } from "react";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// ant-design icons
import CloseOutlined from "@ant-design/icons/CloseOutlined";

// project imports
import { createSignal } from "api/signals/signals";
import {
  displaySuccessSnackbar,
  displayWarningSnackbar,
} from "utils/displayError";

import WizardStepper from "./WizardStepper";
import WizardCaptureStep from "./WizardCaptureStep";
import WizardValidationStep from "./WizardValidationStep";

// ==============================|| CONSTANTS ||============================== //

/**
 * Wizard steps — passed as-is to WizardStepper. Order is meaningful:
 * step 0 = Capture (default landing), step 1 = Validation.
 */
const WIZARD_STEPS = [
  { key: "capture", label: "Capture" },
  { key: "validation", label: "Validation" },
];

const STEP_CAPTURE = 0;
const STEP_VALIDATION = 1;

const INITIAL_STAGED = {
  pain: [],
  objective: [],
  "tech-stack": [],
};

// ==============================|| HELPERS ||============================== //

/**
 * Generate a unique local key for a staged signal.
 * crypto.randomUUID() is available in all modern browsers and Node 14+.
 */
function generateKey() {
  return crypto.randomUUID();
}

// ==============================|| WIZARD SIGNAL ADD ||============================== //

/**
 * WizardSignalAdd
 *
 * @param {boolean}  open             - Dialog open state
 * @param {Function} onClose          - Called on close (no payload)
 * @param {Function} onSuccess        - Called after all signals dispatched successfully
 * @param {string}   accountId        - Account UUID — required for all signal creates
 * @param {Object}   choices          - From useGetSignalChoices()
 * @param {boolean}  choicesLoading
 * @param {Object}   extraPayload     - Injected into every signal at dispatch
 *                                      e.g. { source_activity, decision_cycle, campaign }
 */
export default function WizardSignalAdd({
  open,
  onClose,
  onSuccess,
  accountId,
  choices,
  choicesLoading,
  extraPayload,
}) {
  // ==============================|| STATE ||============================== //

  const [staged, setStaged] = useState(INITIAL_STAGED);
  const [activeStep, setActiveStep] = useState(STEP_CAPTURE);
  const [submitting, setSubmitting] = useState(false);

  /**
   * Dispatch results after a partial failure.
   * null = no dispatch attempted yet, or last dispatch was a full success.
   * { succeeded: [{_key, type}], failed: [{_key, type, error}] }
   */
  const [results, setResults] = useState(null);

  /**
   * Active edit target — non-null when the user is editing a staged signal.
   * { type, _key } — type = signal type, _key = staged signal's local key.
   * When set, WizardCaptureStep aligns activeSection to type and renders
   * the inline form in edit mode for that signal.
   */
  const [editing, setEditing] = useState(null);

  /** Controls the "unsaved signals" confirmation dialog on close attempt */
  const [confirmCloseOpen, setConfirmCloseOpen] = useState(false);

  // ==============================|| RESET ON OPEN ||============================== //

  useEffect(() => {
    if (open) {
      setStaged(INITIAL_STAGED);
      setActiveStep(STEP_CAPTURE);
      setSubmitting(false);
      setResults(null);
      setEditing(null);
    }
  }, [open]);

  // ==============================|| DERIVED ||============================== //

  const totalStaged = useMemo(
    () =>
      staged.pain.length +
      staged.objective.length +
      staged["tech-stack"].length,
    [staged],
  );

  // ==============================|| STAGE HANDLERS ||============================== //

  /**
   * Add a signal payload to the staged list for a given type.
   *
   * @param {'pain'|'objective'|'tech-stack'} type
   * @param {Object} payload - Form values from the inline form (no account/extraPayload)
   */
  const handleAdd = useCallback((type, payload) => {
    setStaged((prev) => ({
      ...prev,
      [type]: [
        ...prev[type],
        { _key: generateKey(), _status: "VALIDATED", ...payload },
      ],
    }));
  }, []);

  /**
   * Flip the _status of a staged signal between VALIDATED and REJECTED.
   */
  const handleToggle = useCallback((type, key) => {
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
   * Remove a staged signal entirely from the list.
   */
  const handleRemove = useCallback((type, key) => {
    setStaged((prev) => ({
      ...prev,
      [type]: prev[type].filter((s) => s._key !== key),
    }));
  }, []);

  // ==============================|| EDIT HANDLERS ||============================== //

  /**
   * Start editing a staged signal — works from both Capture (in-place
   * edit on a section card) and Validation (edit-back: switches the
   * active step back to Capture and lets WizardCaptureStep align its
   * activeSection to the editing target via its own useEffect).
   */
  const handleStartEdit = useCallback((type, key) => {
    setEditing({ type, _key: key });
    setActiveStep(STEP_CAPTURE);
    setResults(null);
  }, []);

  /**
   * Apply an edit to a staged signal.
   * Preserves the original _key and _status — only the payload fields
   * are replaced. Clears edit mode after update.
   */
  const handleUpdate = useCallback((type, key, payload) => {
    setStaged((prev) => ({
      ...prev,
      [type]: prev[type].map((s) =>
        s._key === key ? { _key: s._key, _status: s._status, ...payload } : s,
      ),
    }));
    setEditing(null);
  }, []);

  /** Cancel edit mode without applying changes. */
  const handleCancelEdit = useCallback(() => {
    setEditing(null);
  }, []);

  // ==============================|| STEP NAVIGATION ||============================== //

  /** Advance to Validation step from Capture footer */
  const handleReviewClick = useCallback(() => {
    setActiveStep(STEP_VALIDATION);
    setResults(null);
    setEditing(null);
  }, []);

  /** Back to Capture step from Validation footer */
  const handleBackClick = useCallback(() => {
    setActiveStep(STEP_CAPTURE);
  }, []);

  /**
   * Stepper click handler — drives navigation through the stepper
   * circles. WizardStepper enforces non-clickability of the active
   * step and disabledSteps internally; we just receive the target.
   */
  const handleStepClick = useCallback(
    (idx) => {
      // Going to Validation requires at least one staged signal —
      // the stepper's disabledSteps prop already gates this, but a
      // defensive guard here costs nothing.
      if (idx === STEP_VALIDATION && totalStaged === 0) return;
      setActiveStep(idx);
      if (idx === STEP_CAPTURE) setResults(null);
    },
    [totalStaged],
  );

  // ==============================|| CLOSE FLOW ||============================== //

  const handleClose = useCallback(() => {
    if (submitting) return;
    // If signals are staged, ask for confirmation before discarding
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

  // ==============================|| DISPATCH ||============================== //

  /**
   * Dispatch all VALIDATED signals via Promise.allSettled.
   * account + source + extraPayload injected here — not in the inline forms.
   *
   * On full success: onSuccess() + close.
   * On partial failure: keep failed signals in staged, set results for display.
   *
   * Standardisation refactor — dispatch cleanup
   * --------------------------------------------
   * The legacy zombie source_contact UUID-extract guard has been removed
   * — no inline form carries source_contact in its payload anymore. The
   * remaining UUID extractions cover fields still present on the form
   * payloads (target_contact, source_activity, tech_catalog_entry,
   * related_techstack).
   */
  const handleConfirm = useCallback(async () => {
    // Collect all VALIDATED signals with their type
    const toDispatch = Object.entries(staged).flatMap(([type, signals]) =>
      signals
        .filter((s) => s._status === "VALIDATED")
        .map((s) => ({ type, signal: s })),
    );

    if (toDispatch.length === 0) return;

    setSubmitting(true);

    const settled = await Promise.allSettled(
      toDispatch.map(async ({ type, signal }) => {
        // Strip wizard-managed metadata before sending
        const { _key, _status, ...payload } = signal;

        // Normalize relation FK fields: inline forms (and Async* selectors)
        // store full objects so the UI can render them without re-fetching,
        // but the backend expects UUID strings. We downcast any remaining
        // object references here — once, at dispatch time — to keep each
        // signal type's form logic free of this serialization concern.
        //
        // Fields covered (post-standardisation refactor):
        //   target_contact       — Objective PERSONAL scope (target FK)
        //   source_activity      — Pain (required) / Objective / TechStack (optional)
        //   tech_catalog_entry   — TechStack catalog anchor (required)
        //   related_techstack    — Pain cross-reference to a TechCatalog
        //                          entry (optional, only meaningful when
        //                          what === 'TECH')
        //
        // source_contact removal note
        // ---------------------------
        // The legacy `source_contact` extraction guard was removed during
        // the standardisation refactor — the field is no longer present
        // in any inline form payload. Pain provenance is now derived
        // server-side from source_activity.contacts (m2m).
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
          source: "MANUAL",
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
        // Full success — signal created on backend
        succeeded.push({
          _key: outcome.value._key,
          type: outcome.value.type,
        });
      } else if (outcome.status === "fulfilled") {
        // Request completed but backend returned an error
        failed.push({
          _key: outcome.value._key,
          type: outcome.value.type,
          error: outcome.value.result.error ?? "Failed to create signal",
        });
      } else {
        // Promise itself rejected — network error, timeout, etc.
        // outcome.value is undefined in this branch.
        // Recover _key and type from the original toDispatch array
        // by matching on index (Promise.allSettled preserves order).
        const original = toDispatch[index];
        failed.push({
          _key: original?.signal._key,
          type: original?.type,
          error: "Network error — please check your connection and retry",
        });
      }
    });

    if (failed.length === 0) {
      // Full success — close and notify
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
      // Single failure — show the exact backend error
      displayWarningSnackbar(failed[0].error);
    } else {
      // Multiple failures — generic summary, per-signal errors shown in
      // WizardValidationStep cards.
      displayWarningSnackbar(`${failed.length} signals failed to save.`);
    }
  }, [staged, accountId, extraPayload, onSuccess, onClose]);

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
              Capture Signals
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Add signals across sections, then review and save.
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
          disabledSteps={totalStaged === 0 ? [STEP_VALIDATION] : []}
        />
      </Box>

      <Divider sx={{ flexShrink: 0 }} />

      {/* ==================== STEP CONTENT ==================== */}
      <DialogContent sx={{ p: 0, flex: 1, overflow: "hidden" }}>
        {activeStep === STEP_CAPTURE ? (
          <WizardCaptureStep
            staged={staged}
            editing={editing}
            onAdd={handleAdd}
            onToggleStatus={handleToggle}
            onRemove={handleRemove}
            onStartEdit={handleStartEdit}
            onUpdate={handleUpdate}
            onCancelEdit={handleCancelEdit}
            onReviewClick={handleReviewClick}
            choices={choices}
            choicesLoading={choicesLoading}
            accountId={accountId}
          />
        ) : (
          <WizardValidationStep
            staged={staged}
            onToggleStatus={handleToggle}
            onEdit={handleStartEdit}
            onBackClick={handleBackClick}
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

WizardSignalAdd.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onSuccess: PropTypes.func.isRequired,
  accountId: PropTypes.string.isRequired,
  choices: PropTypes.object,
  choicesLoading: PropTypes.bool,
  /** Injected into every signal at dispatch — e.g. { source_activity: id } */
  extraPayload: PropTypes.object,
};
