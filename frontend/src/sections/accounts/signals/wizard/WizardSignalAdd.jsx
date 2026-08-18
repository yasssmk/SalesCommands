// frontend/src/sections/accounts/signals/wizard/WizardSignalAdd.jsx
/**
 * WizardSignalAdd — main container for the multi-section signal capture wizard.
 *
 * Rendered as a right-side Drawer (full height).
 *
 * Two exclusive screens:
 *   SECTIONS  — WizardNav + active section (Pain/Objective/Impact/Tech Stack)
 *               Footer: signal count + "Review & Save" button
 *
 *   SUMMARY   — WizardSummary (replaces sections entirely)
 *               Footer: owned by WizardSummary (Back + Confirm)
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
 *   - Failed signals kept in staged with their error displayed in WizardSummary
 *   - User can toggle failed signals to REJECTED to skip them, then retry
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo, useEffect } from "react";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// ant-design icons
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import SendOutlined from "@ant-design/icons/SendOutlined";

// project imports
import { createSignal } from "api/signals/signals";
import {
  displaySuccessSnackbar,
  displayWarningSnackbar,
} from "utils/displayError";

import WizardNav from "./WizardNav";
import WizardSummary from "./WizardSummary";
import PainSection from "./sections/PainSection";
import ObjectiveSection from "./sections/ObjectiveSection";
import TechStackSection from "./sections/TechStackSection";

// ==============================|| CONSTANTS ||============================== //

const DRAWER_WIDTH = 540;

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
 * @param {boolean}  open             - Drawer open state
 * @param {Function} onClose          - Called on close (no payload)
 * @param {Function} onSuccess        - Called after all signals dispatched successfully
 * @param {string}   accountId        - Account UUID — required for all signal creates
 * @param {Object}   choices          - From useGetSignalChoices()
 * @param {boolean}  choicesLoading
 * @param {Object}   extraPayload     - Injected into every signal at dispatch
 *                                      e.g. { source_activity: id }
 * @param {Object}   defaultContact   - Full contact object to pre-fill source_contact in all inline forms
 */
export default function WizardSignalAdd({
  open,
  onClose,
  onSuccess,
  accountId,
  choices,
  choicesLoading,
  extraPayload,
  defaultContact,
  defaultSection,
}) {
  // ==============================|| STATE ||============================== //

  const [staged, setStaged] = useState(INITIAL_STAGED);
  const [activeSection, setActiveSection] = useState(defaultSection ?? "pain");
  const [showSummary, setShowSummary] = useState(false);
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
   * When set, the active section renders the inline form in edit mode
   * instead of the card for that signal.
   */
  const [editing, setEditing] = useState(null);

  /** Controls the "unsaved signals" confirmation dialog on close attempt */
  const [confirmCloseOpen, setConfirmCloseOpen] = useState(false);

  /** True when the active section has an inline form open with unsaved input */
  const [sectionFormOpen, setSectionFormOpen] = useState(false);

  /**
   * Section the user wants to navigate to, held in pending state while
   * the "leave unsaved form?" confirmation dialog is open.
   */
  const [pendingSection, setPendingSection] = useState(null);

  // ==============================|| RESET ON OPEN ||============================== //

  useEffect(() => {
    if (open) {
      setStaged(INITIAL_STAGED);
      setActiveSection(defaultSection ?? "pain");
      setShowSummary(false);
      setSubmitting(false);
      setResults(null);
      setEditing(null);
    }
  }, [open, defaultSection]);

  // ==============================|| DERIVED ||============================== //

  const stagedCounts = useMemo(
    () => ({
      pain: staged.pain.length,
      objective: staged.objective.length,
      "tech-stack": staged["tech-stack"].length,
    }),
    [staged],
  );

  const totalStaged = useMemo(
    () => Object.values(stagedCounts).reduce((acc, n) => acc + n, 0),
    [stagedCounts],
  );

  const validatedCount = useMemo(
    () =>
      Object.values(staged)
        .flat()
        .filter((s) => s._status === "VALIDATED").length,
    [staged],
  );

  // ==============================|| STAGE HANDLERS ||============================== //

  /**
   * Add a signal payload to the staged list for a given type.
   * Called by each Section component via a type-specific wrapper.
   *
   * @param {'pain'|'objective'|'impact'|'tech-stack'} type
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

  // Type-specific wrappers — each section receives (payload) => void

  const handleAddPain = useCallback(
    (payload) => handleAdd("pain", payload),
    [handleAdd],
  );
  const handleAddObjective = useCallback(
    (payload) => handleAdd("objective", payload),
    [handleAdd],
  );
  const handleAddTechStack = useCallback(
    (payload) => handleAdd("tech-stack", payload),
    [handleAdd],
  );

  // ==============================|| TOGGLE HANDLERS ||============================== //

  /**
   * Flip the _status of a staged signal between VALIDATED and REJECTED.
   *
   * @param {'pain'|'objective'|'impact'|'tech-stack'} type
   * @param {string} key - _key of the signal to toggle
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

  // Type-specific wrappers for sections (_key) => void

  const handleTogglePain = useCallback(
    (_key) => handleToggle("pain", _key),
    [handleToggle],
  );
  const handleToggleObjective = useCallback(
    (_key) => handleToggle("objective", _key),
    [handleToggle],
  );
  const handleToggleTechStack = useCallback(
    (_key) => handleToggle("tech-stack", _key),
    [handleToggle],
  );

  // ==============================|| REMOVE HANDLERS ||============================== //

  /**
   * Remove a staged signal entirely from the list.
   *
   * @param {'pain'|'objective'|'impact'|'tech-stack'} type
   * @param {string} key - _key of the signal to remove
   */
  const handleRemove = useCallback((type, key) => {
    setStaged((prev) => ({
      ...prev,
      [type]: prev[type].filter((s) => s._key !== key),
    }));
  }, []);

  // Type-specific wrappers for sections (_key) => void

  const handleRemovePain = useCallback(
    (_key) => handleRemove("pain", _key),
    [handleRemove],
  );
  const handleRemoveObjective = useCallback(
    (_key) => handleRemove("objective", _key),
    [handleRemove],
  );

  const handleRemoveTechStack = useCallback(
    (_key) => handleRemove("tech-stack", _key),
    [handleRemove],
  );

  // ==============================|| EDIT HANDLERS ||============================== //

  /**
   * Start editing a staged signal from within a section view.
   * The section will render the inline form pre-filled with signal data.
   *
   * @param {'pain'|'objective'|'impact'|'tech-stack'} type
   * @param {string} key - _key of the signal to edit
   */
  const handleStartEdit = useCallback((type, key) => {
    setEditing({ type, _key: key });
  }, []);

  /**
   * Start editing a staged signal from the Summary screen.
   * Closes Summary, switches to the signal's section, then enters edit mode.
   *
   * @param {'pain'|'objective'|'impact'|'tech-stack'} type
   * @param {string} key - _key of the signal to edit
   */
  const handleStartEditFromSummary = useCallback((type, key) => {
    setShowSummary(false);
    setResults(null);
    setActiveSection(type);
    setEditing({ type, _key: key });
  }, []);

  /**
   * Apply an edit to a staged signal.
   * Preserves the original _key and _status — only the payload fields are replaced.
   * Clears edit mode after update.
   *
   * @param {'pain'|'objective'|'impact'|'tech-stack'} type
   * @param {string} key - _key of the signal being updated
   * @param {Object} payload - New payload from the inline form
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

  // Type-specific wrappers for sections — (_key) => void, (_key, payload) => void

  const handleStartEditPain = useCallback(
    (_key) => handleStartEdit("pain", _key),
    [handleStartEdit],
  );
  const handleStartEditObjective = useCallback(
    (_key) => handleStartEdit("objective", _key),
    [handleStartEdit],
  );
  const handleStartEditTechStack = useCallback(
    (_key) => handleStartEdit("tech-stack", _key),
    [handleStartEdit],
  );

  const handleUpdatePain = useCallback(
    (_key, payload) => handleUpdate("pain", _key, payload),
    [handleUpdate],
  );
  const handleUpdateObjective = useCallback(
    (_key, payload) => handleUpdate("objective", _key, payload),
    [handleUpdate],
  );
  const handleUpdateTechStack = useCallback(
    (_key, payload) => handleUpdate("tech-stack", _key, payload),
    [handleUpdate],
  );

  // ==============================|| NAVIGATION HANDLERS ||============================== //

  const handleSectionChange = useCallback(
    (section) => {
      if (sectionFormOpen) {
        // A form is open in the current section — ask before navigating away
        setPendingSection(section);
        return;
      }
      setSectionFormOpen(false);
      setActiveSection(section);
    },
    [sectionFormOpen],
  );

  /** User confirms leaving the section with an unsaved form */
  const handleSectionChangeProceed = useCallback(() => {
    if (pendingSection) {
      setSectionFormOpen(false);
      setActiveSection(pendingSection);
      setPendingSection(null);
      setEditing(null);
    }
  }, [pendingSection]);

  /** User cancels — stays on the current section */
  const handleSectionChangeDismiss = useCallback(() => {
    setPendingSection(null);
  }, []);

  const handleReviewAndSave = useCallback(() => {
    setShowSummary(true);
    setResults(null);
    setEditing(null);
  }, []);

  const handleBack = useCallback(() => {
    setShowSummary(false);
  }, []);

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
        // Fields covered:
        //   source_contact       — Pain / Objective (where required)
        //   target_contact       — Objective (target of the relation)
        //   source_activity      — All types (optional except Pain where
        //                          it is required by the backend serializer)
        //                          entry (optional, only meaningful when
        //                          what === 'TECH'). Field exposed by
        //                          InlinePainForm in sub-step 7.1.
        if (
          payload.source_contact &&
          typeof payload.source_contact === "object"
        ) {
          payload.source_contact = payload.source_contact.id;
        }
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
      // Multiple failures — generic summary, per-signal errors shown in WizardSummary
      displayWarningSnackbar(`${failed.length} signals failed to save.`);
    }
  }, [staged, accountId, extraPayload, onSuccess, onClose]);

  // ==============================|| RENDER — SECTION CONTENT ||============================== //

  const renderSection = () => {
    const sharedProps = {
      choices,
      choicesLoading,
      accountId,
      defaultContact,
      onFormOpenChange: setSectionFormOpen,
      hasActivityContext: Boolean(extraPayload?.source_activity),
      onCancelEdit: handleCancelEdit,
    };

    // Only expose editingKey to the section that owns the signal being edited
    const editingKeyFor = (type) =>
      editing?.type === type ? editing._key : null;

    switch (activeSection) {
      case "pain":
        return (
          <PainSection
            stagedSignals={staged.pain}
            onAdd={handleAddPain}
            onToggleStatus={handleTogglePain}
            onRemove={handleRemovePain}
            onEdit={handleStartEditPain}
            onUpdate={handleUpdatePain}
            editingKey={editingKeyFor("pain")}
            {...sharedProps}
          />
        );
      case "objective":
        return (
          <ObjectiveSection
            stagedSignals={staged.objective}
            onAdd={handleAddObjective}
            onToggleStatus={handleToggleObjective}
            onRemove={handleRemoveObjective}
            onEdit={handleStartEditObjective}
            onUpdate={handleUpdateObjective}
            editingKey={editingKeyFor("objective")}
            {...sharedProps}
          />
        );
      case "tech-stack":
        return (
          <TechStackSection
            stagedSignals={staged["tech-stack"]}
            onAdd={handleAddTechStack}
            onToggleStatus={handleToggleTechStack}
            onRemove={handleRemoveTechStack}
            onEdit={handleStartEditTechStack}
            onUpdate={handleUpdateTechStack}
            editingKey={editingKeyFor("tech-stack")}
            {...sharedProps}
          />
        );
      default:
        return null;
    }
  };

  // ==============================|| RENDER ||============================== //

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={handleClose}
      PaperProps={{
        sx: {
          width: { xs: "100vw", sm: DRAWER_WIDTH },
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        },
      }}
    >
      {/* ==================== HEADER ==================== */}
      <Box sx={{ px: 3, py: 2, flexShrink: 0 }}>
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
      </Box>

      <Divider sx={{ flexShrink: 0 }} />

      {/* ==================== SCREEN: SECTIONS ==================== */}
      {!showSummary && (
        <>
          {/* Nav tabs */}
          <Box sx={{ flexShrink: 0 }}>
            <WizardNav
              activeSection={activeSection}
              onChange={handleSectionChange}
              stagedCounts={stagedCounts}
            />
          </Box>

          {/* Section content — scrollable */}
          <Box sx={{ flex: 1, overflowY: "auto", px: 3, py: 2.5 }}>
            {renderSection()}
          </Box>

          <Divider sx={{ flexShrink: 0 }} />

          {/* Section footer */}
          <Box sx={{ px: 3, py: 2, flexShrink: 0 }}>
            <Stack
              direction="row"
              justifyContent="space-between"
              alignItems="center"
            >
              {/* Staged count — shows ready/total to make exclusions visible */}
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="caption" color="text.secondary">
                  Ready
                </Typography>
                <Chip
                  label={
                    totalStaged === 0
                      ? "0"
                      : validatedCount === totalStaged
                        ? `${totalStaged}`
                        : `${validatedCount} / ${totalStaged}`
                  }
                  size="small"
                  color={
                    validatedCount === 0
                      ? "default"
                      : validatedCount < totalStaged
                        ? "warning"
                        : "primary"
                  }
                  sx={{ height: 20, fontSize: "0.68rem" }}
                />
              </Stack>

              {/* Review & Save — enabled as long as something is staged,
                  even if all are excluded (user can re-include in Summary) */}
              <Button
                variant="contained"
                size="small"
                onClick={handleReviewAndSave}
                disabled={totalStaged === 0}
                startIcon={<SendOutlined style={{ fontSize: 13 }} />}
              >
                Review & Save
              </Button>
            </Stack>
          </Box>
        </>
      )}

      {/* ==================== SCREEN: SUMMARY ==================== */}
      {showSummary && (
        <Box
          sx={{
            flex: 1,
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <WizardSummary
            staged={staged}
            onToggleStatus={handleToggle}
            onEdit={handleStartEditFromSummary}
            onBack={handleBack}
            onConfirm={handleConfirm}
            submitting={submitting}
            results={results}
            choices={choices}
          />
        </Box>
      )}

      {/* ==================== SECTION CHANGE CONFIRMATION ==================== */}
      <Dialog
        open={Boolean(pendingSection)}
        onClose={handleSectionChangeDismiss}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Leave unsaved form?</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary">
            You have an unsaved signal form open. Switching sections will
            discard what you&apos;ve typed.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button
            onClick={handleSectionChangeDismiss}
            color="inherit"
            size="small"
          >
            Stay here
          </Button>
          <Button
            onClick={handleSectionChangeProceed}
            color="warning"
            variant="contained"
            size="small"
          >
            Leave anyway
          </Button>
        </DialogActions>
      </Dialog>

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
    </Drawer>
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
  /** Pre-fills source_contact in all inline forms */
  defaultContact: PropTypes.object,
  /** Section open by default — defaults to 'pain' */
  defaultSection: PropTypes.oneOf(["pain", "objective", "tech-stack"]),
};
