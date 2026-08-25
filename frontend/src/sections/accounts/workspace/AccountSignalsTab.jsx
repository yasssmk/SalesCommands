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
import { useState, useCallback, useMemo, useEffect } from "react";

// material-ui
import Badge from "@mui/material/Badge";
import Box from "@mui/material/Box";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// icons
import FilterOutlined from "@ant-design/icons/FilterOutlined";

// project imports
import SignalsFlatView from "sections/activities/signals/SignalsFlatView";
import SignalsFilterPanel from "sections/activities/signals/SignalsFilterPanel";
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
import useSignalFilters from "hooks/useSignalFilters";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// ==============================|| CONSTANTS ||============================== //

// The Account flat list covers the four durable, account-level signal types
// (blockers / next-steps / people / constraints are deal- or cycle-scoped).
const ACCOUNT_TYPES = ["pain", "objective", "impact", "tech-stack"];

// ==============================|| ACCOUNT SIGNALS TAB ||============================== //

/**
 * AccountSignalsTab
 *
 * @param {string} accountId - Account UUID (required)
 * @param {Object} account   - Full account object (optional, for form context)
 */
export default function AccountSignalsTab({ accountId, account }) {
  // ==============================|| FILTER STATE ||============================== //

  const [page, setPage] = useState(1);
  const [filterPanelOpen, setFilterPanelOpen] = useState(false);
  const {
    pending,
    updatePending,
    apply,
    clear,
    syncPending,
    statuses,
    activeTypes,
    activeCount,
    hasPendingChanges,
  } = useSignalFilters();

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

  // One aggregated call, server-paginated (20/page). The filter drawer drives
  // signal_type (a subset of the account types; none selected = all four) and
  // status (default pending+validated, +rejected when opted in).
  const signalTypes = useMemo(
    () => (activeTypes.length ? activeTypes : ACCOUNT_TYPES),
    [activeTypes],
  );

  const {
    signals: flatSignals,
    pageCount,
    loading,
    error,
    mutate: mutateAll,
  } = useAggregatedSignals({
    accountId,
    signalTypes,
    statuses,
    ordering: "date-desc",
    page,
    pageSize: 20,
  });

  const { choices, choicesLoading } = useGetSignalChoices();

  // A page fetch can fail while a previous page is still shown (SWR keeps the
  // last data). Don't blank the list — keep it and surface the transient
  // failure through the standard error snackbar instead.
  useEffect(() => {
    if (error && flatSignals.length) displayErrorSnackbar(error);
  }, [error, flatSignals.length]);

  // ==============================|| FILTER HANDLERS ||============================== //

  const handleOpenFilters = useCallback(() => {
    syncPending();
    setFilterPanelOpen(true);
  }, [syncPending]);

  // Applying filters narrows the result set → reset to page 1.
  const handleApplyFilters = useCallback(() => {
    apply();
    setPage(1);
  }, [apply]);

  const handleClearFilters = useCallback(() => {
    clear();
    setPage(1);
  }, [clear]);

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
        direction="row"
        justifyContent="flex-end"
        alignItems="center"
        sx={{ mb: 2 }}
      >
        <Tooltip title="Filters">
          <IconButton onClick={handleOpenFilters} aria-label="Open filters">
            <Badge badgeContent={activeCount} color="primary">
              <FilterOutlined />
            </Badge>
          </IconButton>
        </Tooltip>
      </Stack>

      <Divider sx={{ mb: 2 }} />

      {/* ==================== ACTIVE SECTION ==================== */}
      {/*
        The active type's signals render as compact SignalLine rows via the
        shared SignalsFlatView (same component as Activity / DC flat), fed by
        the aggregated endpoint with true server pagination (20/page). Clicking
        a line opens the signal drawer. There is no delete on this surface.
      */}
      {error && !flatSignals.length ? (
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
          emptyMessage="No signals match these filters"
        />
      )}

      {/* Filter drawer */}
      <SignalsFilterPanel
        open={filterPanelOpen}
        onClose={() => setFilterPanelOpen(false)}
        availableTypes={ACCOUNT_TYPES}
        pendingFilters={pending}
        onFilterChange={updatePending}
        onApply={handleApplyFilters}
        onClear={handleClearFilters}
        hasPendingChanges={hasPendingChanges}
      />

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
