// frontend/src/sections/accounts/workspace/AccountSignalsTab.jsx
/**
 * AccountSignalsTab — operational view of individual signals.
 *
 * Renders all 4 signal types (Pain, Objective, Impact, Tech Stack) as
 * uniform flat lists of cards with full CRUD: validate / reject / edit
 * / delete.
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
 *   - Own modal/drawer states (edit, reject, signal detail drawer)
 *   - Dispatch validate / reject / reopen to the API layer
 *   - Render the active type's signals as compact SignalLine rows via
 *     the shared SignalsFlatView (20/page), same component as Activity/DC
 *   - Status filter applied server-side via SWR filters — universal
 *     across all 4 types
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo } from "react";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Divider from "@mui/material/Divider";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";

// project imports
import SignalsFlatView from "sections/activities/signals/SignalsFlatView";
import SignalQuickDrawer from "sections/activities/signals/SignalQuickDrawer";
import AlertSignalReject from "../signals/AlertSignalReject";
import SignalEditDialog from "sections/activities/signals/SignalEditDialog";

import {
  useGetSignalChoices,
  validateSignal,
  reopenSignal,
  deleteSignal,
} from "api/signals/signals";
import useAggregatedSignals from "api/signals/aggregatedSignals";
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
  const [page, setPage] = useState(1);

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

  // Signal detail drawer (opened by clicking a signal line).
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedSignal, setSelectedSignal] = useState(null);
  const [selectedType, setSelectedType] = useState(null);

  // ==============================|| DATA FETCHING ||============================== //

  // One aggregated call for the active type, server-paginated (20/page).
  // The type toggle drives signal_type; the status Select drives status.
  const statuses = useMemo(
    () => (statusFilter ? [statusFilter] : undefined),
    [statusFilter],
  );

  const {
    signals: flatSignals,
    pageCount,
    loading,
    error,
    mutate: mutateAll,
  } = useAggregatedSignals({
    accountId,
    signalTypes: [activeType],
    statuses,
    ordering: "date-desc",
    page,
    pageSize: 20,
  });

  const { choices, choicesLoading } = useGetSignalChoices();

  // ==============================|| FILTER HANDLERS ||============================== //

  // Reset to page 1 whenever the type or status narrows the result set.
  const handleTypeChange = useCallback((_e, newValue) => {
    if (newValue !== null) {
      setActiveType(newValue);
      setPage(1);
    }
  }, []);

  const handleStatusChange = useCallback((e) => {
    setStatusFilter(e.target.value);
    setPage(1);
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

  const handleReopen = useCallback(
    async (signal, signalType) => {
      const result = await reopenSignal(signalType, signal.id);
      if (result.success) {
        mutateAll();
        displaySuccessSnackbar("Signal reopened — now pending");
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll],
  );

  // Drawer open/close — clicking a signal line shows its detail.
  const handleSelect = useCallback((signal, signalType) => {
    setSelectedSignal(signal);
    setSelectedType(signalType);
    setDrawerOpen(true);
  }, []);

  const handleCloseDrawer = useCallback(() => {
    setDrawerOpen(false);
    setSelectedSignal(null);
    setSelectedType(null);
  }, []);

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

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      {/* ==================== TOOLBAR ==================== */}
      {/*
        Read-only operational view: signal creation now happens exclusively
        from the Activity Workspace (ActivitySignalsTab), where the source
        activity context is available for auto-propagation. This tab keeps
        full lifecycle control (validate / reject / edit / delete).
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
        The active type's signals render as compact SignalLine rows via the
        shared SignalsFlatView (same component as Activity / DC flat), fed by
        the aggregated endpoint with true server pagination (20/page). Clicking
        a line opens the signal drawer. There is no delete on this surface.
      */}
      {error ? (
        <Box
          display="flex"
          justifyContent="center"
          alignItems="center"
          minHeight="200px"
        >
          <Typography color="error">Failed to load signals</Typography>
        </Box>
      ) : (
        <SignalsFlatView
          signals={flatSignals}
          serverPaginated
          page={page}
          pageCount={pageCount}
          onPageChange={setPage}
          loading={loading}
          onSelect={handleSelect}
          onValidate={handleValidate}
          onReject={handleRejectOpen}
          onEdit={handleEdit}
          onReopen={handleReopen}
          emptyMessage={
            statusFilter
              ? `No ${activeType} signals match this status`
              : `No ${activeType} signals yet for this account`
          }
        />
      )}

      {/* ==================== MODALS ==================== */}

      {/* Signal detail drawer (opened by clicking a line) */}
      <SignalQuickDrawer
        open={drawerOpen}
        signal={selectedSignal}
        signalType={selectedType}
        onClose={handleCloseDrawer}
        onValidate={handleValidate}
        onReject={handleRejectOpen}
        onEdit={handleEdit}
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
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

AccountSignalsTab.propTypes = {
  accountId: PropTypes.string.isRequired,
  account: PropTypes.object,
};
