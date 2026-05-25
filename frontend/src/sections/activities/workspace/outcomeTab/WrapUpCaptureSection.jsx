// frontend/src/sections/activities/workspace/outcomeTab/WrapUpCaptureSection.jsx
/**
 * WrapUpCaptureSection — Capture half of the Activity Wrap-up tab.
 *
 * Self-contained section that drives the post-call workflow:
 *   1. Notes      : editable text block, persists to Activity.outcome_notes
 *   2. Transcript : editable text block, persists to Activity.transcript
 *   3. CTAs       : "Extract signals with AI" (opens WizardSignalAITranscript)
 *                   and "Add signals manually" (opens WizardSignalAdd)
 *   4. Signals    : section toggle (Pain / Objective / TechStack) + SignalList
 *                   with PENDING + VALIDATED signals linked to this activity.
 *                   Full action set: validate / reject / edit / delete +
 *                   PainImpact CRUD on Pain signals.
 *
 * Holds all state internally (signal hooks, modal states, edit-mode
 * toggles for Notes/Transcript). The parent ActivityWrapUpTab only
 * forwards `activity`, `onSave`, and `isLocked`.
 *
 * Notes and Transcript edits go through `onSave(field, value)` —
 * the parent's handleSaveField calls updateActivity and mutates the
 * activity SWR cache, which propagates back here via the `activity` prop.
 */

"use client";

import PropTypes from "prop-types";
import { useState, useEffect, useMemo, useCallback } from "react";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// ant-design icons
import CheckOutlined from "@ant-design/icons/CheckOutlined";
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import PlusOutlined from "@ant-design/icons/PlusOutlined";
import RobotOutlined from "@ant-design/icons/RobotOutlined";

// project imports
import {
  useGetSignalsByActivity,
  useGetSignalChoices,
  validateSignal,
  deleteSignal,
} from "api/signals/signals";
import { deletePainImpact } from "api/signals/painImpacts";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

import SignalList from "sections/accounts/signals/SignalList";
import AlertSignalReject from "sections/accounts/signals/AlertSignalReject";
import AddPainImpactDialog from "sections/accounts/signals/pain/AddPainImpactDialog";
import SignalEditDialog from "sections/activities/signals/SignalEditDialog";
import WizardSignalAdd from "sections/activities/signals/wizard/WizardSignalAdd";
import WizardSignalAITranscript from "sections/activities/signals/wizard/WizardSignalAITranscript";

// ==============================|| CONSTANTS ||============================== //

const TYPE_OPTIONS = [
  { value: "pain", label: "Pain" },
  { value: "objective", label: "Objective" },
  { value: "impact", label: "Impact" },
  { value: "tech-stack", label: "Tech Stack" },
];

// ==============================|| EDITABLE TEXT BLOCK ||============================== //

/**
 * EditableTextBlock — click-to-edit text area with explicit Save / Cancel.
 *
 * Display mode: clickable Box with the saved content (or placeholder).
 * Edit mode:    TextField with the configured rows + Save / Cancel buttons.
 *
 * Save is disabled while saving, or when the value matches the original.
 * On successful save (onSave returns true), exits edit mode automatically.
 * On failure, stays in edit mode so the user can retry.
 *
 * Syncs `value` from `initialValue` whenever the parent's value changes
 * AND the user is not currently editing — prevents a stale local state
 * when the activity SWR cache mutates externally.
 */
function EditableTextBlock({
  label,
  field,
  initialValue,
  rows = 5,
  placeholder = "Click to add...",
  showCharCount = false,
  onSave,
  isLocked = false,
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(initialValue || "");
  const [saving, setSaving] = useState(false);

  // Sync local value with parent prop when not editing (handles SWR refresh)
  useEffect(() => {
    if (!editing) {
      setValue(initialValue || "");
    }
  }, [initialValue, editing]);

  const original = initialValue || "";
  const hasChanges = value !== original;

  const handleSave = async () => {
    if (!hasChanges) {
      setEditing(false);
      return;
    }
    setSaving(true);
    const success = await onSave(field, value);
    setSaving(false);
    if (success) {
      setEditing(false);
    }
  };

  const handleCancel = () => {
    setValue(original);
    setEditing(false);
  };

  return (
    <Box>
      {/* Label row */}
      <Stack direction="row" spacing={1} alignItems="baseline" sx={{ mb: 1 }}>
        <Typography variant="subtitle2" fontWeight={600}>
          {label}
        </Typography>
        {showCharCount && (
          <Typography variant="caption" color="text.secondary">
            {value?.length ?? 0} characters
          </Typography>
        )}
      </Stack>

      {/* Edit / Display */}
      {editing ? (
        <Stack spacing={1}>
          <TextField
            fullWidth
            multiline
            minRows={rows}
            maxRows={rows * 2}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={placeholder}
            disabled={saving}
            autoFocus
          />
          <Stack direction="row" spacing={1} justifyContent="flex-end">
            <Button
              size="small"
              onClick={handleCancel}
              disabled={saving}
              startIcon={<CloseOutlined />}
            >
              Cancel
            </Button>
            <Button
              size="small"
              variant="contained"
              onClick={handleSave}
              disabled={saving || !hasChanges}
              startIcon={<CheckOutlined />}
            >
              Save
            </Button>
          </Stack>
        </Stack>
      ) : (
        <Box
          onClick={() => !isLocked && setEditing(true)}
          sx={{
            p: 2,
            borderRadius: 1,
            bgcolor: "action.hover",
            cursor: isLocked ? "default" : "pointer",
            minHeight: 60,
            "&:hover": {
              bgcolor: isLocked ? "action.hover" : "action.selected",
            },
          }}
        >
          {original ? (
            <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
              {original}
            </Typography>
          ) : (
            <Typography variant="body2" color="text.secondary">
              {placeholder}
            </Typography>
          )}
        </Box>
      )}
    </Box>
  );
}

EditableTextBlock.propTypes = {
  label: PropTypes.string.isRequired,
  field: PropTypes.string.isRequired,
  initialValue: PropTypes.string,
  rows: PropTypes.number,
  placeholder: PropTypes.string,
  showCharCount: PropTypes.bool,
  onSave: PropTypes.func.isRequired,
  isLocked: PropTypes.bool,
};

// ==============================|| WRAP-UP CAPTURE SECTION ||============================== //

/**
 * WrapUpCaptureSection
 *
 * @param {Object}   activity  - Full activity object (from useGetActivity)
 * @param {Function} onSave    - (fieldKey, newValue) => Promise<boolean>.
 *                               Persists Notes / Transcript via parent's
 *                               handleSaveField → updateActivity.
 * @param {boolean}  isLocked  - Activity is COMPLETED or CANCELLED →
 *                               disables editing surfaces.
 */
export default function WrapUpCaptureSection({
  activity,
  onSave,
  isLocked = false,
}) {
  // ==============================|| DERIVED IDs ||============================== //

  const activityId = activity?.id ?? null;

  /**
   * activity.account can be a UUID string or a compact object
   * { id, company_name } — guard both forms (mirrors ActivitySignalsTab).
   */
  const accountId = useMemo(() => {
    if (!activity?.account) return null;
    if (typeof activity.account === "string") return activity.account;
    return activity.account?.id ?? null;
  }, [activity]);

  /**
   * extraPayload — injected into every signal at wizard dispatch.
   * Same logic as ActivitySignalsTab: links each created signal to this
   * activity via source_activity, plus copies decision_cycle / campaign /
   * decision_step from the activity for deterministic write paths.
   *
   * Note: backend SignalManager.create() also auto-fills these from
   * source_activity when omitted — sending them here is belt-and-
   * suspenders, harmless when null.
   */
  const extraPayload = useMemo(() => {
    if (!activityId) return {};
    return {
      source_activity: activityId,
      decision_cycle: activity?.decision_cycle ?? null,
      campaign: activity?.campaign_detail?.id ?? null,
      decision_step: activity?.decision_step ?? null,
    };
  }, [
    activityId,
    activity?.decision_cycle,
    activity?.campaign_detail?.id,
    activity?.decision_step,
  ]);

  // ==============================|| SECTION TOGGLE ||============================== //

  const [activeSection, setActiveSection] = useState("pain");

  const handleSectionChange = useCallback((_e, newValue) => {
    if (newValue !== null) setActiveSection(newValue);
  }, []);

  // ==============================|| DATA FETCHING ||============================== //

  const {
    signals: painSignals,
    signalsLoading: painLoading,
    signalsError: painError,
    mutateSignals: mutatePain,
  } = useGetSignalsByActivity(activityId, "pain");

  const {
    signals: objectiveSignals,
    signalsLoading: objectiveLoading,
    signalsError: objectiveError,
    mutateSignals: mutateObjective,
  } = useGetSignalsByActivity(activityId, "objective");

  const {
    signals: impactSignals,
    signalsLoading: impactLoading,
    signalsError: impactError,
    mutateSignals: mutateImpact,
  } = useGetSignalsByActivity(activityId, "impact");

  const {
    signals: techSignals,
    signalsLoading: techLoading,
    signalsError: techError,
    mutateSignals: mutateTech,
  } = useGetSignalsByActivity(activityId, "tech-stack");

  const { choices, choicesLoading } = useGetSignalChoices();

  const mutateAll = useCallback(() => {
    mutatePain();
    mutateObjective();
    mutateImpact();
    mutateTech();
  }, [mutatePain, mutateObjective, mutateImpact, mutateTech]);

  // ==============================|| DERIVED LIST DATA ||============================== //

  const totalCount = useMemo(
    () =>
      painSignals.length +
      objectiveSignals.length +
      impactSignals.length +
      techSignals.length,
    [painSignals, objectiveSignals, impactSignals, techSignals],
  );

  const counts = useMemo(
    () => ({
      pain: painSignals.length,
      objective: objectiveSignals.length,
      impact: impactSignals.length,
      "tech-stack": techSignals.length,
    }),
    [painSignals, objectiveSignals, impactSignals, techSignals],
  );

  const activeData = useMemo(() => {
    switch (activeSection) {
      case "pain":
        return { signals: painSignals, loading: painLoading, error: painError };
      case "objective":
        return {
          signals: objectiveSignals,
          loading: objectiveLoading,
          error: objectiveError,
        };
      case "impact":
        return {
          signals: impactSignals,
          loading: impactLoading,
          error: impactError,
        };
      case "tech-stack":
        return { signals: techSignals, loading: techLoading, error: techError };
      default:
        return { signals: [], loading: false, error: null };
    }
  }, [
    activeSection,
    painSignals,
    painLoading,
    painError,
    objectiveSignals,
    objectiveLoading,
    objectiveError,
    impactSignals,
    impactLoading,
    impactError,
    techSignals,
    techLoading,
    techError,
  ]);

  // ==============================|| MODAL STATE ||============================== //

  const [wizardManualOpen, setWizardManualOpen] = useState(false);
  const [wizardAIOpen, setWizardAIOpen] = useState(false);

  const [rejectModal, setRejectModal] = useState({
    open: false,
    signal: null,
    signalType: null,
  });

  const [editModal, setEditModal] = useState({
    open: false,
    signal: null,
    signalType: null,
  });

  const [impactDialog, setImpactDialog] = useState({
    open: false,
    mode: null, // 'create' | 'edit'
    painSignalId: null,
    initialImpact: null,
  });

  // ==============================|| WIZARD HANDLERS ||============================== //

  const handleWizardManualOpen = useCallback(
    () => setWizardManualOpen(true),
    [],
  );
  const handleWizardManualClose = useCallback(
    () => setWizardManualOpen(false),
    [],
  );

  const handleWizardAIOpen = useCallback(() => setWizardAIOpen(true), []);
  const handleWizardAIClose = useCallback(() => setWizardAIOpen(false), []);

  const handleWizardSuccess = useCallback(() => {
    mutateAll();
    // Wizards close themselves on full success
  }, [mutateAll]);

  // ==============================|| SIGNAL ACTION HANDLERS ||============================== //

  const handleValidate = useCallback(
    async (signal, signalType) => {
      const result = await validateSignal(signalType, signal.id);
      if (result.success) {
        mutateAll();
        displaySuccessSnackbar("Signal validated");
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll],
  );

  const handleRejectOpen = useCallback((signal, signalType) => {
    setRejectModal({ open: true, signal, signalType });
  }, []);

  const handleRejectClose = useCallback(() => {
    setRejectModal({ open: false, signal: null, signalType: null });
  }, []);

  const handleRejectSuccess = useCallback(() => {
    setRejectModal({ open: false, signal: null, signalType: null });
    mutateAll();
    displaySuccessSnackbar("Signal rejected");
  }, [mutateAll]);

  const handleEdit = useCallback((signal, signalType) => {
    setEditModal({ open: true, signal, signalType });
  }, []);

  const handleEditClose = useCallback(() => {
    setEditModal({ open: false, signal: null, signalType: null });
  }, []);

  const handleEditSuccess = useCallback(() => {
    mutateAll();
    // Dialog closes itself on success
  }, [mutateAll]);

  const handleDelete = useCallback(
    async (signal, signalType) => {
      const result = await deleteSignal(signalType, signal.id);
      if (result.success) {
        mutateAll();
        displaySuccessSnackbar("Signal deleted");
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll],
  );

  // ==============================|| PAIN IMPACT HANDLERS ||============================== //

  const handleAddImpact = useCallback((painSignalId) => {
    setImpactDialog({
      open: true,
      mode: "create",
      painSignalId,
      initialImpact: null,
    });
  }, []);

  const handleEditImpact = useCallback((impact) => {
    setImpactDialog({
      open: true,
      mode: "edit",
      painSignalId: null,
      initialImpact: impact,
    });
  }, []);

  const handleImpactDialogClose = useCallback(() => {
    setImpactDialog({
      open: false,
      mode: null,
      painSignalId: null,
      initialImpact: null,
    });
  }, []);

  const handleImpactDialogSuccess = useCallback(() => {
    mutatePain();
    displaySuccessSnackbar("Impact saved");
  }, [mutatePain]);

  const handleDeleteImpact = useCallback(
    async (impact) => {
      const result = await deletePainImpact(impact.id);
      if (result.success) {
        mutatePain();
        displaySuccessSnackbar("Impact deleted");
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutatePain],
  );

  // ==============================|| CTA STATE ||============================== //

  const transcript = activity?.transcript ?? "";
  const hasTranscript = Boolean(transcript.trim());

  // CTA — "Extract signals with AI"
  // Disabled when locked, no transcript, or no accountId
  const aiDisabled = isLocked || !hasTranscript || !accountId;
  const aiTooltip = !hasTranscript
    ? "Paste a transcript first"
    : !accountId
      ? "Activity not loaded"
      : "";

  // CTA — "Add signals manually"
  // Disabled when locked or no accountId
  const manualDisabled = isLocked || !accountId;

  // ==============================|| RENDER ||============================== //

  return (
    <Stack spacing={3}>
      {/* ==================== NOTES ==================== */}
      <EditableTextBlock
        label="Notes"
        field="outcome_notes"
        initialValue={activity?.outcome_notes}
        rows={5}
        placeholder="Capture key takeaways, observations, decisions made during the call..."
        onSave={onSave}
        isLocked={isLocked}
      />

      {/* ==================== TRANSCRIPT ==================== */}
      <EditableTextBlock
        label="Transcript"
        field="transcript"
        initialValue={activity?.transcript}
        rows={15}
        placeholder="Paste the call transcript or email content here..."
        showCharCount
        onSave={onSave}
        isLocked={isLocked}
      />

      {/* ==================== CTA ROW ==================== */}
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={1.5}
        alignItems={{ xs: "stretch", sm: "center" }}
      >
        <Tooltip title={aiTooltip} arrow>
          <span style={{ display: "inline-flex" }}>
            <Button
              variant="contained"
              color="primary"
              startIcon={<RobotOutlined />}
              onClick={handleWizardAIOpen}
              disabled={aiDisabled}
            >
              Extract signals with AI
            </Button>
          </span>
        </Tooltip>

        <Button
          variant="outlined"
          startIcon={<PlusOutlined />}
          onClick={handleWizardManualOpen}
          disabled={manualDisabled}
        >
          Add signals manually
        </Button>
      </Stack>

      {/* ==================== SIGNALS LIST ==================== */}
      <Box>
        {/* Header */}
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
          <Typography variant="subtitle2" fontWeight={600}>
            Signals from this activity
          </Typography>
          {totalCount > 0 && (
            <Chip
              label={totalCount}
              size="small"
              sx={{ height: 18, fontSize: "0.68rem" }}
            />
          )}
        </Stack>

        {/* Type toggle */}
        <ToggleButtonGroup
          value={activeSection}
          exclusive
          onChange={handleSectionChange}
          size="small"
          aria-label="Signal type"
          sx={{ mb: 2 }}
        >
          {TYPE_OPTIONS.map((opt) => (
            <ToggleButton
              key={opt.value}
              value={opt.value}
              sx={{ textTransform: "none", px: 1.5, fontSize: "0.78rem" }}
            >
              {opt.label}
              {counts[opt.value] > 0 && (
                <Chip
                  label={counts[opt.value]}
                  size="small"
                  sx={{
                    ml: 0.75,
                    height: 18,
                    fontSize: "0.62rem",
                    pointerEvents: "none",
                  }}
                />
              )}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>

        {/* List for active section */}
        <SignalList
          signals={activeData.signals}
          signalType={activeSection}
          loading={activeData.loading}
          error={activeData.error}
          onValidate={handleValidate}
          onReject={handleRejectOpen}
          onEdit={handleEdit}
          onDelete={handleDelete}
          choices={choices}
          onAddImpact={handleAddImpact}
          onEditImpact={handleEditImpact}
          onDeleteImpact={handleDeleteImpact}
          emptyMessage={`No ${activeSection.replace("-", " ")} signals captured yet`}
          emptyDescription="Use the buttons above to capture signals from this conversation"
        />
      </Box>

      {/* ==================== MODALS ==================== */}

      {/* Manual wizard */}
      <WizardSignalAdd
        open={wizardManualOpen}
        onClose={handleWizardManualClose}
        onSuccess={handleWizardSuccess}
        accountId={accountId ?? ""}
        choices={choices}
        choicesLoading={choicesLoading}
        extraPayload={extraPayload}
      />

      {/* AI / Transcript wizard */}
      <WizardSignalAITranscript
        open={wizardAIOpen}
        onClose={handleWizardAIClose}
        onSuccess={handleWizardSuccess}
        accountId={accountId ?? ""}
        activityId={activityId ?? ""}
        choices={choices}
        choicesLoading={choicesLoading}
        initialTranscript={activity?.transcript ?? ""}
        initialNotes={activity?.outcome_notes ?? ""}
        onSignalEdit={handleEdit}
      />

      {/* Reject confirmation */}
      <AlertSignalReject
        open={rejectModal.open}
        onClose={handleRejectClose}
        onSuccess={handleRejectSuccess}
        signal={rejectModal.signal}
        signalType={rejectModal.signalType}
      />

      {/* Edit dialog */}
      <SignalEditDialog
        open={editModal.open}
        onClose={handleEditClose}
        onSuccess={handleEditSuccess}
        signal={editModal.signal}
        signalType={editModal.signalType}
        accountId={accountId ?? ""}
        choices={choices}
        choicesLoading={choicesLoading}
      />

      {/* PainImpact dialog — dual create/edit */}
      <AddPainImpactDialog
        open={impactDialog.open}
        onClose={handleImpactDialogClose}
        onSuccess={handleImpactDialogSuccess}
        painSignalId={impactDialog.painSignalId}
        accountId={accountId ?? ""}
        initialImpact={impactDialog.initialImpact}
      />
    </Stack>
  );
}

// ==============================|| PROP TYPES ||============================== //

WrapUpCaptureSection.propTypes = {
  activity: PropTypes.shape({
    id: PropTypes.string,
    account: PropTypes.oneOfType([PropTypes.string, PropTypes.object]),
    outcome_notes: PropTypes.string,
    transcript: PropTypes.string,
    decision_cycle: PropTypes.string,
    decision_step: PropTypes.string,
    campaign_detail: PropTypes.shape({ id: PropTypes.string }),
  }),
  onSave: PropTypes.func.isRequired,
  isLocked: PropTypes.bool,
};
