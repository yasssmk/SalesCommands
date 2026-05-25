// frontend/src/sections/accounts/workspace/AccountSignalsTab.jsx
/**
 * AccountSignalsTab — operational view of individual signals.
 *
 * Renders all 4 signal types (People, Pain, Objective, Tech Stack) as
 * uniform flat lists of cards with full CRUD: validate / reject / edit
 * / delete, plus type-specific extras (Pain has nested impacts CRUD).
 *
 * Strict separation of concerns
 * -----------------------------
 * This tab handles SIGNAL-LEVEL operations only. Cluster-level views
 * (priority aggregation across canonical_key) live in the
 * Qualification tab. There is no cluster surface here anymore.
 *
 * Responsibilities
 * ----------------
 *   - Fetch all 4 signal types for the account (4 SWR calls)
 *   - Own all modal/drawer states (wizard add, edit, reject, impact CRUD)
 *   - Dispatch validate / reject / delete to the API layer
 *   - Render one SignalList at a time based on the active section
 *   - Status filter applied server-side via SWR filters — universal
 *     across all 4 types
 *
 * Pain-specific add-on
 * --------------------
 * PainCard exposes 3 impact callbacks (onAddImpact / onEditImpact /
 * onDeleteImpact). They are wired to AddPainImpactDialog mounted at
 * tab level so impacts can be created, edited, or deleted directly
 * from the flat Pain list — same UX as when impacts were nested
 * inside the cluster drawer.
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

// project imports
import SignalList from "../signals/SignalList";
import AlertSignalReject from "../signals/AlertSignalReject";
import SignalEditDialog from "sections/activities/signals/SignalEditDialog";
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
/** Section toggle options — 4 signal types */
const TYPE_OPTIONS = [
  { value: "pain", label: "Pain" },
  { value: "objective", label: "Objective" },
  { value: "impact", label: "Impact" },
  { value: "tech-stack", label: "Tech Stack" },
];

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
   * Pain impact dialog state. Mounted at tab level (not gated on
   * activeType) so it stays available even if the user has briefly
   * switched type while the dialog is open.
   */
  const [impactDialog, setImpactDialog] = useState({
    open: false,
    mode: null,
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
    signals: impactSignals,
    signalsLoading: impactLoading,
    signalsError: impactError,
    mutateSignals: mutateImpact,
  } = useGetSignalsByAccount(accountId, "impact", sharedOptions);

  const {
    signals: techSignals,
    signalsLoading: techLoading,
    signalsError: techError,
    mutateSignals: mutateTech,
  } = useGetSignalsByAccount(accountId, "tech-stack", sharedOptions);

  const { choices, choicesLoading } = useGetSignalChoices();

  // ==============================|| DERIVED ||============================== //

  /**
   * Revalidate all 4 sections — called after any signal-level write.
   * Pain mutations also implicitly invalidate the cluster cache via
   * the API layer's revalidateMultiple — that's the Qualification tab's
   * responsibility, not ours.
   */
  const mutateAll = useCallback(() => {
    mutatePain();
    mutateObjective();
    mutateImpact();
    mutateTech();
  }, [mutatePain, mutateObjective, mutateImpact, mutateTech]);

  /**
   * Counts per type — shown as badges in the section toggle.
   * All 4 types share the same flat-list semantics, so each count
   * is the number of individual signals in the current view (after
   * status filter).
   */
  const counts = useMemo(
    () => ({
      pain: painSignals.length,
      objective: objectiveSignals.length,
      impact: impactSignals.length,
      "tech-stack": techSignals.length,
    }),
    [painSignals, objectiveSignals, impactSignals, techSignals],
  );

  /** Active section data — uniform shape across all 4 types. */
  const activeData = useMemo(() => {
    switch (activeType) {
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
      case "impact":
        return {
          signals: impactSignals,
          loading: impactLoading,
          error: impactError,
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

  // ==============================|| FILTER HANDLERS ||============================== //

  const handleTypeChange = useCallback((_e, newValue) => {
    if (newValue !== null) setActiveType(newValue);
  }, []);

  const handleStatusChange = useCallback((e) => {
    setStatusFilter(e.target.value);
  }, []);

  // ==============================|| LIFECYCLE HANDLERS (universal) ||============================== //

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

  // ==============================|| IMPACT HANDLERS — Pain-only ||============================== //
  //
  // PainCard exposes 3 impact callbacks. They are passed down through
  // SignalList to PainCard only when activeType === 'pain' (SignalList
  // ignores them otherwise). The dialog itself is mounted at tab level.

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
    // Pain list needs refresh because impacts are nested inline in
    // PainSignalListSerializer. The cluster cache also gets bust by
    // the API layer — that's transparent to this tab.
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
      {/* ==================== TOOLBAR ==================== */}
      {/*
        Read-only operational view: signal creation now happens exclusively
        from the Activity Workspace (ActivitySignalsTab), where the source
        activity context is available for auto-propagation. This tab keeps
        full lifecycle control (validate / reject / edit / delete) plus
        Pain impact CRUD via PainCard.
      */}
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={1.5}
        alignItems="center"
        sx={{ mb: 2 }}
      >
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

      <Divider sx={{ mb: 2 }} />

      {/* ==================== ACTIVE SECTION ==================== */}
      {/*
        SignalList routes signalType='pain' to PainCard internally and
        forwards the impact callbacks (onAddImpact / onEditImpact /
        onDeleteImpact) only to PainCard. The other 3 types ignore them.
        `choices` is needed by PainCard (impact labels) and by
        ObjectiveCard (canonical axis + scope labels).
      */}
      <SignalList
        signals={activeData.signals}
        signalType={activeType}
        loading={activeData.loading}
        error={activeData.error}
        choices={choices}
        onValidate={handleValidate}
        onReject={handleRejectOpen}
        onEdit={handleEdit}
        onDelete={handleDelete}
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

      {/* ==================== MODALS ==================== */}

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

      {/* Pain impact dialog — Pain-only by nature; mounted always so it
          can be opened from any PainCard regardless of pending tab switch */}
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
