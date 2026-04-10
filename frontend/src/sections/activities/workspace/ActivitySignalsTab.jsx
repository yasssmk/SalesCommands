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
import WizardSignalAdd from "sections/accounts/signals/wizard/WizardSignalAdd";

import {
  useGetSignalsByActivity,
  useGetSignalChoices,
  validateSignal,
  deleteSignal,
} from "api/accounts/signals";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// ==============================|| CONSTANTS ||============================== //

/** Section toggle — 4 signal types */
const TYPE_OPTIONS = [
  { value: "people", label: "People" },
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
   * source_activity links each new signal to this activity.
   */
  const extraPayload = useMemo(
    () => (activityId ? { source_activity: activityId } : {}),
    [activityId],
  );

  // ==============================|| SECTION STATE ||============================== //

  const [activeSection, setActiveSection] = useState("pain");

  const handleSectionChange = useCallback((_e, newValue) => {
    if (newValue !== null) setActiveSection(newValue);
  }, []);

  // ==============================|| DATA FETCHING ||============================== //

  const {
    signals: peopleSignals,
    signalsLoading: peopleLoading,
    signalsError: peopleError,
    mutateSignals: mutatePeople,
  } = useGetSignalsByActivity(activityId, "people");

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
    mutatePeople();
    mutatePain();
    mutateObjective();
    mutateTech();
  }, [mutatePeople, mutatePain, mutateObjective, mutateTech]);

  /** Total signal count across all types — shown in panel header */
  const totalCount = useMemo(
    () =>
      peopleSignals.length +
      painSignals.length +
      objectiveSignals.length +
      techSignals.length,
    [peopleSignals, painSignals, objectiveSignals, techSignals],
  );

  /** Per-type counts — shown as badges in the section toggle */
  const counts = useMemo(
    () => ({
      people: peopleSignals.length,
      pain: painSignals.length,
      objective: objectiveSignals.length,
      "tech-stack": techSignals.length,
    }),
    [peopleSignals, painSignals, objectiveSignals, techSignals],
  );

  /** Active section data — signals, loading, error */
  const activeData = useMemo(() => {
    switch (activeSection) {
      case "people":
        return {
          signals: peopleSignals,
          loading: peopleLoading,
          error: peopleError,
        };
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
    peopleSignals,
    peopleLoading,
    peopleError,
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
        displayErrorSnackbar(result.error || "Failed to validate signal");
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

  /**
   * TODO: Edit form deferred from MVP.
   * Wire up per-type edit forms here in Sprint 7.
   */
  const handleEdit = useCallback((_signal, _signalType) => {
    // no-op for MVP
  }, []);

  const handleDelete = useCallback(
    async (signal, signalType) => {
      const result = await deleteSignal(signalType, signal.id);
      if (result.success) {
        mutateAll();
        displaySuccessSnackbar("Signal deleted");
      } else {
        displayErrorSnackbar(result.error || "Failed to delete signal");
      }
    },
    [mutateAll],
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
