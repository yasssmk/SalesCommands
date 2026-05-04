// frontend/src/sections/activities/workspace/ActivitySignalsTab.jsx
/**
 * ActivitySignalsTab — Signals section in the Activity Workspace.
 *
 * Two panels stacked vertically:
 *
 *   1. ACTIVITY SIGNALS
 *      Section toggle (People · Pain · Objective · Tech Stack) + SignalList
 *      for the active section. Rep can validate / reject / delete from here.
 *      "Add Signal" opens WizardSignalAdd with source_activity + source_contact
 *      pre-filled from the activity context.
 *
 *   2. LLM PLACEHOLDER (Sprint 2)
 *      Visually present but disabled section. Communicates to the rep that
 *      transcript-based extraction is coming.
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo } from "react";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";

// ant-design icons
import ExperimentOutlined from "@ant-design/icons/ExperimentOutlined";
import PlusOutlined from "@ant-design/icons/PlusOutlined";
import RobotOutlined from "@ant-design/icons/RobotOutlined";

// project imports
import SignalList from "sections/accounts/signals/SignalList";
import AlertSignalReject from "sections/accounts/signals/AlertSignalReject";
import SignalEditDialog from "sections/accounts/signals/SignalEditDialog";
import WizardSignalAdd from "sections/accounts/signals/wizard/WizardSignalAdd";
import AddPainImpactDialog from "sections/accounts/signals/pain/AddPainImpactDialog";

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

// ==============================|| CONSTANTS ||============================== //

/** Section toggle — 4 signal types */
const TYPE_OPTIONS = [
  { value: "pain", label: "Pain" },
  { value: "objective", label: "Objective" },
  { value: "tech-stack", label: "Tech Stack" },
];

// ==============================|| LLM PLACEHOLDER ||============================== //

/**
 * LlmPlaceholder — Sprint 2 reserved area.
 *
 * Visually distinct (dashed border + muted palette) to signal
 * "coming soon" without hiding the section or leaving blank space.
 */
function LlmPlaceholder() {
  return (
    <Paper
      variant="outlined"
      sx={{
        borderStyle: "dashed",
        borderColor: "divider",
        borderRadius: 1.5,
        p: 3,
        bgcolor: "action.hover",
        opacity: 0.75,
      }}
    >
      <Stack spacing={1.5} alignItems="center">
        <RobotOutlined style={{ fontSize: 32, color: "#8c8c8c" }} />

        <Stack spacing={0.5} alignItems="center">
          <Typography variant="subtitle2" color="text.secondary">
            Transcript analysis
          </Typography>
          <Typography
            variant="body2"
            color="text.disabled"
            textAlign="center"
            maxWidth={380}
          >
            Once you paste a call transcript, signals extracted by the LLM will
            appear here for review — validate or reject each one before they are
            added to the account signal board.
          </Typography>
        </Stack>

        <Chip
          icon={<ExperimentOutlined />}
          label="Available in Sprint 2"
          size="small"
          variant="outlined"
          sx={{
            color: "text.disabled",
            borderColor: "divider",
            fontSize: "0.7rem",
          }}
        />
      </Stack>
    </Paper>
  );
}

// ==============================|| SECTION HEADER ||============================== //

function SectionHeader({ title, count }) {
  return (
    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
      <Typography variant="subtitle1" fontWeight={600}>
        {title}
      </Typography>
      {count !== undefined && count > 0 && (
        <Chip
          label={count}
          size="small"
          color="default"
          sx={{ height: 18, fontSize: "0.68rem" }}
        />
      )}
    </Stack>
  );
}

SectionHeader.propTypes = {
  title: PropTypes.string.isRequired,
  count: PropTypes.number,
};

// ==============================|| ACTIVITY SIGNALS TAB ||============================== //

/**
 * ActivitySignalsTab
 *
 * @param {Object} activity - Full activity object from useGetActivity()
 */
export default function ActivitySignalsTab({ activity }) {
  // ==============================|| DERIVED IDs ||============================== //

  const activityId = activity?.id ?? null;

  /**
   * activity.account can be a UUID string (most serializers)
   * or a compact object { id, company_name } (detail serializer).
   * Guard both forms.
   */
  const accountId = useMemo(() => {
    if (!activity?.account) return null;
    if (typeof activity.account === "string") return activity.account;
    return activity.account?.id ?? null;
  }, [activity]);

  /**
   * Detect single contact — pre-fill source_contact in the wizard.
   * If absent or multiple contacts, leave empty (user selects in form).
   */
  const defaultContact = useMemo(() => {
    const contacts = activity?.contacts ?? [];
    if (contacts.length === 1) return contacts[0] ?? null;
    return null;
  }, [activity]);

  /**
   * Extra payload injected into every signal at wizard dispatch time.
   *
   * Provides the deal-level context the wizard cannot infer on its own:
   *   - source_activity : links each new signal to this activity (always)
   *   - decision_cycle  : copied from the activity when set
   *   - campaign        : copied from the activity's campaign_detail.id
   *   - decision_step   : copied from the activity when set
   *
   * Frontend redundancy with the backend propagation hook
   * -----------------------------------------------------
   * SignalManager.create() also auto-fills decision_cycle / campaign /
   * decision_step from source_activity when not explicitly provided
   * (Sprint 1 hook). Sending these values from the frontend is a belt-
   * and-suspenders measure: when the activity object is already loaded
   * client-side, we pass the IDs along so the write path stays fully
   * deterministic and doesn't depend on a second backend resolution.
   *
   * Backend behaviour with these values
   * -----------------------------------
   * The propagation hook respects explicit non-null values (caller
   * wins). Sending null for fields the activity doesn't carry triggers
   * the hook fallback — also safe, since null on the activity side
   * means "no value to propagate" and the field stays null on the
   * signal too.
   *
   * TechStackSignal note
   * --------------------
   * decision_cycle / campaign / decision_step are stripped from the
   * TechStack create serializer's fields list (model shadow-overrides),
   * so DRF silently ignores them on TechStack creation. Sending them
   * uniformly here is safe — no per-type branching needed.
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

  // ==============================|| SECTION STATE ||============================== //

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
    signals: techSignals,
    signalsLoading: techLoading,
    signalsError: techError,
    mutateSignals: mutateTech,
  } = useGetSignalsByActivity(activityId, "tech-stack");

  const { choices, choicesLoading } = useGetSignalChoices();

  // ==============================|| DERIVED ||============================== //

  const mutateAll = useCallback(() => {
    mutatePain();
    mutateObjective();
    mutateTech();
  }, [mutatePain, mutateObjective, mutateTech]);

  /** Total signal count across all types — shown in panel header */
  const totalCount = useMemo(
    () => painSignals.length + objectiveSignals.length + techSignals.length,
    [painSignals, objectiveSignals, techSignals],
  );

  /** Per-type counts — shown as badges in the section toggle */
  const counts = useMemo(
    () => ({
      pain: painSignals.length,
      objective: objectiveSignals.length,
      "tech-stack": techSignals.length,
    }),
    [painSignals, objectiveSignals, techSignals],
  );

  /** Active section data — signals, loading, error */
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
    techSignals,
    techLoading,
    techError,
  ]);

  // ==============================|| MODAL STATE ||============================== //

  const [wizardOpen, setWizardOpen] = useState(false);

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

  /**
   * PainImpact dialog state — see AccountSignalsTab for the same pattern.
   */
  const [impactDialog, setImpactDialog] = useState({
    open: false,
    mode: null, // 'create' | 'edit'
    painSignalId: null,
    initialImpact: null,
  });

  // ==============================|| HANDLERS ||============================== //

  const handleWizardOpen = useCallback(() => setWizardOpen(true), []);
  const handleWizardClose = useCallback(() => setWizardOpen(false), []);

  const handleWizardSuccess = useCallback(() => {
    mutateAll();
    // Wizard closes itself on full success
  }, [mutateAll]);

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

  // ==============================|| IMPACT HANDLERS ||============================== //

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

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      {/* ==================== PANEL 1: ACTIVITY SIGNALS ==================== */}

      {/* Panel header */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ mb: 1.5 }}
      >
        <SectionHeader title="Signals from this activity" count={totalCount} />
        <Button
          variant="outlined"
          size="small"
          startIcon={<PlusOutlined />}
          onClick={handleWizardOpen}
          disabled={!accountId}
        >
          Add Signal
        </Button>
      </Stack>

      {/* Section toggle */}
      <ToggleButtonGroup
        value={activeSection}
        exclusive
        onChange={handleSectionChange}
        size="small"
        aria-label="Signal section"
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

      {/* Active section list */}
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
        emptyMessage={`No ${activeSection} signals linked to this activity yet`}
        emptyDescription="Open the wizard to capture signals from this conversation"
      />

      <Divider sx={{ my: 3 }} />

      {/* ==================== PANEL 2: LLM PLACEHOLDER ==================== */}
      <SectionHeader title="Transcript analysis" />
      <LlmPlaceholder />

      {/* ==================== DRAWERS / MODALS ==================== */}

      {/* Signal capture wizard — pre-filled with activity context */}
      <WizardSignalAdd
        open={wizardOpen}
        onClose={handleWizardClose}
        onSuccess={handleWizardSuccess}
        accountId={accountId ?? ""}
        choices={choices}
        choicesLoading={choicesLoading}
        extraPayload={extraPayload}
        defaultContact={defaultContact}
        defaultSection={activeSection}
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
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

ActivitySignalsTab.propTypes = {
  activity: PropTypes.shape({
    id: PropTypes.string,
    account: PropTypes.oneOfType([PropTypes.string, PropTypes.object]),
    contacts: PropTypes.arrayOf(PropTypes.shape({ id: PropTypes.string })),
  }),
};
