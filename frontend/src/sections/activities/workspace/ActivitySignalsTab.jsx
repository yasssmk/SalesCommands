// frontend/src/sections/activities/workspace/ActivitySignalsTab.jsx
/**
 * ActivitySignalsTab — Signals section in the Activity Workspace.
 *
 * Three panels stacked vertically:
 *
 *   1. ACTIVITY SIGNALS
 *      Lists all signals already linked to this activity (both qual + tech-stack).
 *      Rep can validate / reject / edit / supersede / delete from here.
 *
 *   2. ADD SIGNAL
 *      Button to manually create a signal linked to this activity.
 *      - source_activity pre-filled (extraPayload)
 *      - source_contact pre-filled if the activity has exactly one contact
 *      - accountId derived from activity.account
 *
 *   3. LLM PLACEHOLDER (Sprint 2)
 *      Visually present but disabled section. Communicates to the rep that
 *      transcript-based extraction is coming. No hidden / invisible markup.
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
import Typography from "@mui/material/Typography";

// ant-design icons
import ExperimentOutlined from "@ant-design/icons/ExperimentOutlined";
import PlusOutlined from "@ant-design/icons/PlusOutlined";
import RobotOutlined from "@ant-design/icons/RobotOutlined";

// project imports
import SignalList from "sections/accounts/signals/SignalList";
import FormSignalAdd from "sections/accounts/signals/FormSignalAdd";
import FormSignalEdit from "sections/accounts/signals/FormSignalEdit";
import AlertSignalReject from "sections/accounts/signals/AlertSignalReject";

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
   * Detect single contact — pre-fill source_contact in the add form.
   * activity.contacts shape is assumed to be an array of { id, ... }.
   * If the field is absent or has more than one contact, we leave it empty.
   */
  const defaultContactId = useMemo(() => {
    const contacts = activity?.contacts ?? [];
    if (contacts.length === 1) return contacts[0]?.id ?? null;
    return null;
  }, [activity]);

  /**
   * Extra payload injected into FormSignalAdd at submit time.
   * source_activity links the new signal to this activity.
   */
  const extraPayload = useMemo(
    () => (activityId ? { source_activity: activityId } : {}),
    [activityId],
  );

  // ==============================|| DATA FETCHING ||============================== //

  const {
    signals: qualSignals,
    signalsLoading: qualLoading,
    signalsError: qualError,
    mutateSignals: mutateQual,
  } = useGetSignalsByActivity(activityId, "qualification");

  const {
    signals: tsSignals,
    signalsLoading: tsLoading,
    signalsError: tsError,
    mutateSignals: mutateTs,
  } = useGetSignalsByActivity(activityId, "tech-stack");

  const { choices, choicesLoading } = useGetSignalChoices();

  // ==============================|| DERIVED LIST ||============================== //

  const signals = useMemo(() => {
    const taggedQual = qualSignals.map((s) => ({
      ...s,
      signalType: "qualification",
    }));
    const taggedTs = tsSignals.map((s) => ({ ...s, signalType: "tech-stack" }));
    return [...taggedQual, ...taggedTs].sort(
      (a, b) => new Date(b.created_at) - new Date(a.created_at),
    );
  }, [qualSignals, tsSignals]);

  const isLoading = qualLoading || tsLoading;
  const hasError = qualError || tsError;

  // ==============================|| REVALIDATE ||============================== //

  const mutateAll = useCallback(() => {
    mutateQual();
    mutateTs();
  }, [mutateQual, mutateTs]);

  // ==============================|| MODAL STATE ||============================== //

  const [addOpen, setAddOpen] = useState(false);

  const [editModal, setEditModal] = useState({
    open: false,
    signal: null,
    signalType: null,
  });

  const [rejectModal, setRejectModal] = useState({
    open: false,
    signal: null,
    signalType: null,
  });

  // ==============================|| HANDLERS ||============================== //

  const handleAddClose = useCallback(() => setAddOpen(false), []);

  const handleAddSuccess = useCallback(() => {
    setAddOpen(false);
    mutateAll();
    displaySuccessSnackbar("Signal added to this activity");
  }, [mutateAll]);

  const handleEdit = useCallback((signal, signalType) => {
    setEditModal({ open: true, signal, signalType });
  }, []);

  const handleEditClose = useCallback(() => {
    setEditModal({ open: false, signal: null, signalType: null });
  }, []);

  const handleEditSuccess = useCallback(() => {
    setEditModal({ open: false, signal: null, signalType: null });
    mutateAll();
    displaySuccessSnackbar("Signal updated");
  }, [mutateAll]);

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

  /** Supersede from activity context — opens FormSignalAdd in supersede mode */
  const [supersedeTarget, setSupersedeTarget] = useState(null);

  const handleSupersede = useCallback((signal, signalType) => {
    setSupersedeTarget({ signal, signalType });
    setAddOpen(true);
  }, []);

  const handleAddOrSupersedeClose = useCallback(() => {
    setAddOpen(false);
    setSupersedeTarget(null);
  }, []);

  const handleAddOrSupersedeSuccess = useCallback(() => {
    setAddOpen(false);
    setSupersedeTarget(null);
    mutateAll();
    displaySuccessSnackbar(
      supersedeTarget ? "Signal superseded" : "Signal added to this activity",
    );
  }, [mutateAll, supersedeTarget]);

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      {/* ==================== PANEL 1: ACTIVITY SIGNALS ==================== */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ mb: 1.5 }}
      >
        <SectionHeader
          title="Signals from this activity"
          count={signals.length}
        />
        <Button
          variant="outlined"
          size="small"
          startIcon={<PlusOutlined />}
          onClick={() => {
            setSupersedeTarget(null);
            setAddOpen(true);
          }}
          disabled={!accountId}
        >
          Add Signal
        </Button>
      </Stack>

      <SignalList
        signals={signals}
        loading={isLoading}
        error={hasError}
        onValidate={handleValidate}
        onReject={handleRejectOpen}
        onEdit={handleEdit}
        onSupersede={handleSupersede}
        onDelete={handleDelete}
        emptyMessage="No signals linked to this activity yet"
        emptyDescription="Add a signal manually or extract them from the transcript below"
      />

      <Divider sx={{ my: 3 }} />

      {/* ==================== PANEL 2: LLM PLACEHOLDER ==================== */}
      <SectionHeader title="Transcript analysis" />
      <LlmPlaceholder />

      {/* ==================== MODALS ==================== */}

      <FormSignalAdd
        open={addOpen}
        onClose={handleAddOrSupersedeClose}
        onSuccess={handleAddOrSupersedeSuccess}
        accountId={accountId ?? ""}
        choices={choices}
        choicesLoading={choicesLoading}
        supersedeTarget={supersedeTarget}
        extraPayload={extraPayload}
        defaultContactId={defaultContactId}
      />

      <FormSignalEdit
        open={editModal.open}
        onClose={handleEditClose}
        onSuccess={handleEditSuccess}
        signal={editModal.signal}
        signalType={editModal.signalType}
        choices={choices}
        choicesLoading={choicesLoading}
      />

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
  /** Full activity object from useGetActivity() */
  activity: PropTypes.shape({
    id: PropTypes.string,
    account: PropTypes.oneOfType([PropTypes.string, PropTypes.object]),
    contacts: PropTypes.arrayOf(PropTypes.shape({ id: PropTypes.string })),
  }),
};
