// frontend/src/sections/accounts/workspace/AccountSignalsTab.jsx
/**
 * AccountSignalsTab — container for the Signals tab in Account Workspace.
 *
 * Responsibilities:
 *   - Fetch all 4 signal types for the account (4 SWR calls)
 *   - Own all modal/drawer states (wizard add, reject)
 *   - Dispatch validate / reject / delete to the API layer
 *   - Render one SignalList at a time based on the active section
 *   - Status filter applied server-side via SWR filters
 *
 * Edit is deferred from MVP — onEdit handler is a no-op with a TODO.
 * Modal state lives here so it persists across open/close cycles.
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo } from "react";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";

// ant-design icons
import PlusOutlined from "@ant-design/icons/PlusOutlined";

// project imports
import SignalList from "../signals/SignalList";
import AlertSignalReject from "../signals/AlertSignalReject";
import SignalEditDialog from "../signals/SignalEditDialog";
import WizardSignalAdd from "../signals/wizard/WizardSignalAdd";
import AddPainImpactDialog from "../signals/pain/AddPainImpactDialog";

import {
  useGetSignalsByAccount,
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

/** Section toggle options — 4 signal types */
const TYPE_OPTIONS = [
  { value: "people", label: "People" },
  { value: "pain", label: "Pain" },
  { value: "objective", label: "Objective" },
  { value: "tech-stack", label: "Tech Stack" },
];

/** Status filter dropdown options */
const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "PENDING", label: "Pending" },
  { value: "VALIDATED", label: "Validated" },
  { value: "REJECTED", label: "Rejected" },
];

// ==============================|| ACCOUNT SIGNALS TAB ||============================== //

/**
 * AccountSignalsTab
 *
 * @param {string} accountId - Account UUID (required)
 * @param {Object} account   - Full account object (optional, for form context)
 */
export default function AccountSignalsTab({ accountId, account }) {
  // ==============================|| FILTER STATE ||============================== //

  const [activeType, setActiveType] = useState("pain");
  const [statusFilter, setStatusFilter] = useState("");

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
   * PainImpact dialog state — used for both create and edit modes.
   *   mode='create': painSignalId set, initialImpact null
   *   mode='edit':   initialImpact set, painSignalId derived from it
   */
  const [impactDialog, setImpactDialog] = useState({
    open: false,
    mode: null, // 'create' | 'edit'
    painSignalId: null,
    initialImpact: null,
  });

  // ==============================|| DATA FETCHING ||============================== //

  const sharedFilters = useMemo(
    () => ({ status: statusFilter || undefined }),
    [statusFilter],
  );

  const sharedOptions = useMemo(
    () => ({ ordering: "-created_at", filters: sharedFilters }),
    [sharedFilters],
  );

  const {
    signals: peopleSignals,
    signalsLoading: peopleLoading,
    signalsError: peopleError,
    mutateSignals: mutatePeople,
  } = useGetSignalsByAccount(accountId, "people", sharedOptions);

  const {
    signals: painSignals,
    signalsLoading: painLoading,
    signalsError: painError,
    mutateSignals: mutatePain,
  } = useGetSignalsByAccount(accountId, "pain", sharedOptions);

  const {
    signals: objectiveSignals,
    signalsLoading: objectiveLoading,
    signalsError: objectiveError,
    mutateSignals: mutateObjective,
  } = useGetSignalsByAccount(accountId, "objective", sharedOptions);

  const {
    signals: techSignals,
    signalsLoading: techLoading,
    signalsError: techError,
    mutateSignals: mutateTech,
  } = useGetSignalsByAccount(accountId, "tech-stack", sharedOptions);

  const { choices, choicesLoading } = useGetSignalChoices();

  // ==============================|| DERIVED ||============================== //

  /** Revalidate all 4 lists — called after any write */
  const mutateAll = useCallback(() => {
    mutatePeople();
    mutatePain();
    mutateObjective();
    mutateTech();
  }, [mutatePeople, mutatePain, mutateObjective, mutateTech]);

  /** Counts per type — shown as badges in the section toggle */
  const counts = useMemo(
    () => ({
      people: peopleSignals.length,
      pain: painSignals.length,
      objective: objectiveSignals.length,
      "tech-stack": techSignals.length,
    }),
    [peopleSignals, painSignals, objectiveSignals, techSignals],
  );

  /** Active section data */
  const activeData = useMemo(() => {
    switch (activeType) {
      case "people":
        return {
          signals: peopleSignals,
          loading: peopleLoading,
          error: peopleError,
        };
      case "pain":
        return {
          signals: painSignals,
          loading: painLoading,
          error: painError,
        };
      case "objective":
        return {
          signals: objectiveSignals,
          loading: objectiveLoading,
          error: objectiveError,
        };
      case "tech-stack":
        return {
          signals: techSignals,
          loading: techLoading,
          error: techError,
        };
      default:
        return { signals: [], loading: false, error: null };
    }
  }, [
    activeType,
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

  // ==============================|| FILTER HANDLERS ||============================== //

  const handleTypeChange = useCallback((_e, newValue) => {
    if (newValue !== null) setActiveType(newValue);
  }, []);

  const handleStatusChange = useCallback((e) => {
    setStatusFilter(e.target.value);
  }, []);

  // ==============================|| ACTION HANDLERS ||============================== //

  const handleWizardOpen = useCallback(() => {
    setWizardOpen(true);
  }, []);

  const handleWizardClose = useCallback(() => {
    setWizardOpen(false);
  }, []);

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

  /** Open dialog in CREATE mode — attach a new impact to a specific pain. */
  const handleAddImpact = useCallback((painSignalId) => {
    setImpactDialog({
      open: true,
      mode: "create",
      painSignalId,
      initialImpact: null,
    });
  }, []);

  /** Open dialog in EDIT mode — pre-fill from an existing impact. */
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
    // Revalidate Pain lists — the nested `impacts` array changed.
    // painImpacts.js already invalidates the Pain cache tag, but we mutate
    // the local SWR cache explicitly so the refresh is immediate without
    // waiting for the next focus.
    mutatePain();
    displaySuccessSnackbar("Impact saved");
  }, [mutatePain]);

  /**
   * Delete an impact — called by PainCard after its inline confirm dialog
   * already confirmed the action. No additional confirm here.
   */
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
      {/* ==================== TOOLBAR ==================== */}
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={1.5}
        alignItems={{ xs: "stretch", sm: "center" }}
        justifyContent="space-between"
        sx={{ mb: 2 }}
      >
        {/* Left: section toggle + status filter */}
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={1.5}
          alignItems="center"
        >
          {/* Section toggle */}
          <ToggleButtonGroup
            value={activeType}
            exclusive
            onChange={handleTypeChange}
            size="small"
            aria-label="Signal section"
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

          {/* Status filter */}
          <Select
            value={statusFilter}
            onChange={handleStatusChange}
            size="small"
            displayEmpty
            sx={{ minWidth: 140, fontSize: "0.82rem" }}
          >
            {STATUS_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
        </Stack>

        {/* Right: add button — opens wizard on the active section */}
        <Button
          variant="contained"
          size="small"
          startIcon={<PlusOutlined />}
          onClick={handleWizardOpen}
        >
          Add Signal
        </Button>
      </Stack>

      <Divider sx={{ mb: 2 }} />

      {/* ==================== ACTIVE SECTION LIST ==================== */}
      <SignalList
        signals={activeData.signals}
        signalType={activeType}
        loading={activeData.loading}
        error={activeData.error}
        onValidate={handleValidate}
        onReject={handleRejectOpen}
        onEdit={handleEdit}
        onDelete={handleDelete}
        // Pain-specific — SignalList only forwards these to PainCard.
        // Harmless for the 3 other types (the generic SignalCard ignores them).
        choices={choices}
        onAddImpact={handleAddImpact}
        onEditImpact={handleEditImpact}
        onDeleteImpact={handleDeleteImpact}
        emptyMessage={
          statusFilter
            ? `No ${activeType} signals match this status`
            : `No ${activeType} signals yet for this account`
        }
        emptyDescription={
          !statusFilter
            ? "Open the wizard to capture signals from a conversation"
            : undefined
        }
      />

      {/* ==================== MODALS / DRAWERS ==================== */}

      {/* Signal capture wizard */}
      <WizardSignalAdd
        open={wizardOpen}
        onClose={handleWizardClose}
        onSuccess={handleWizardSuccess}
        accountId={accountId}
        choices={choices}
        choicesLoading={choicesLoading}
        defaultSection={activeType}
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
        accountId={accountId}
        choices={choices}
        choicesLoading={choicesLoading}
      />

      {/* PainImpact dialog — dual create/edit */}
      <AddPainImpactDialog
        open={impactDialog.open}
        onClose={handleImpactDialogClose}
        onSuccess={handleImpactDialogSuccess}
        painSignalId={impactDialog.painSignalId}
        accountId={accountId}
        initialImpact={impactDialog.initialImpact}
      />
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

AccountSignalsTab.propTypes = {
  accountId: PropTypes.string.isRequired,
  account: PropTypes.object,
};
