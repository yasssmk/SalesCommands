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
import SignalsFlatView from "components/signals/SignalsFlatView";
import SignalsFilterPanel from "components/signals/SignalsFilterPanel";
import SignalsViewToggle from "sections/activities/signals/SignalsViewToggle";
import QualificationGroupedView from "sections/accounts/signals/QualificationGroupedView";
import SignalsGroupedFilterPanel from "sections/accounts/signals/SignalsGroupedFilterPanel";
import SignalQuickDrawer from "components/signals/SignalQuickDrawer";
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
import { useGetContactChoices } from "api/businessData/contacts";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// ==============================|| CONSTANTS ||============================== //

// The Account flat list covers the four durable, account-level signal types
// (blockers / next-steps / people / constraints are deal- or cycle-scoped).
const ACCOUNT_TYPES = ["pain", "objective", "impact", "tech-stack"];

// Grouped (cluster) default status set — pending + validated.
const GROUPED_DEFAULT_STATUSES = ["PENDING", "VALIDATED"];
const emptyGroupedFilters = () => ({
  perimeter: [],
  contacts: [], // contact objects (Autocomplete value); ids derived for fetch
  whats: [],
  dimensions: [],
  statuses: GROUPED_DEFAULT_STATUSES,
});

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
  // Flat / Grouped view toggle — Grouped (the synthesis) is the default. React
  // state only, no browser storage.
  const [view, setView] = useState("grouped");
  const {
    pending,
    updatePending,
    apply,
    clear,
    syncPending,
    statuses,
    activeTypes,
    department,
    contactId,
    scope,
    activeCount,
    hasPendingChanges,
  } = useSignalFilters();

  // Controlled department list + contact-search scope for the filter drawer.
  const { standardDepartments } = useGetContactChoices();
  const departmentOptions = useMemo(
    () =>
      (standardDepartments ?? []).map((d) => ({
        value: d.value ?? d.id,
        label: d.label ?? d.name,
      })),
    [standardDepartments],
  );
  const contactFilters = useMemo(() => ({ account_id: accountId }), [accountId]);

  // ---- Grouped (cluster) filter state — the unified perimeter model. Kept
  // separate from the flat filters (useSignalFilters) so the flat view stays
  // untouched. Applied on change (the grouped sections have no pending/Apply).
  const [groupedFilters, setGroupedFilters] = useState(emptyGroupedFilters);
  const handleGroupedChange = useCallback(
    (field, newValue) =>
      setGroupedFilters((prev) => ({ ...prev, [field]: newValue })),
    [],
  );
  const handleGroupedClear = useCallback(
    () => setGroupedFilters(emptyGroupedFilters()),
    [],
  );
  const perimeterOptions = useMemo(
    () => [{ value: "BUSINESS", label: "Business" }, ...departmentOptions],
    [departmentOptions],
  );
  const groupedContactIds = useMemo(
    () => groupedFilters.contacts.map((c) => c.id),
    [groupedFilters.contacts],
  );
  const groupedActiveCount =
    groupedFilters.perimeter.length +
    groupedFilters.contacts.length +
    groupedFilters.whats.length +
    groupedFilters.dimensions.length +
    (groupedFilters.statuses.includes("REJECTED") ? 1 : 0);

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
    department,
    contact: contactId,
    scope,
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
        justifyContent="space-between"
        alignItems="center"
        sx={{ mb: 2 }}
      >
        <SignalsViewToggle view={view} onChange={setView} />
        <Tooltip title="Filters">
          <IconButton onClick={handleOpenFilters} aria-label="Open filters">
            <Badge
              badgeContent={view === "grouped" ? groupedActiveCount : activeCount}
              color="primary"
            >
              <FilterOutlined />
            </Badge>
          </IconButton>
        </Tooltip>
      </Stack>

      <Divider sx={{ mb: 2 }} />

      {/* ==================== ACTIVE SECTION ==================== */}
      {/*
        Grouped (default) = the Qualification synthesis (clusters). Flat = the
        SignalLine list with server pagination. Both honor the Type filter;
        Flat additionally honors status/department/contact/scope.
      */}
      {view === "grouped" ? (
        <QualificationGroupedView
          surface="account"
          accountId={accountId}
          perimeter={groupedFilters.perimeter}
          whats={groupedFilters.whats}
          dimensions={groupedFilters.dimensions}
          contacts={groupedContactIds}
          statuses={groupedFilters.statuses}
        />
      ) : error && !flatSignals.length ? (
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

      {/* Filter drawer. Grouped uses the accordion-sectioned panel (perimeter /
          contact / domain / dimension / status on the cluster endpoint); Flat
          keeps its own unchanged SignalsFilterPanel. */}
      {view === "grouped" ? (
        <SignalsGroupedFilterPanel
          open={filterPanelOpen}
          onClose={() => setFilterPanelOpen(false)}
          perimeterOptions={perimeterOptions}
          contactFilters={contactFilters}
          value={groupedFilters}
          onChange={handleGroupedChange}
          onClear={handleGroupedClear}
          activeCount={groupedActiveCount}
        />
      ) : (
        <SignalsFilterPanel
          open={filterPanelOpen}
          onClose={() => setFilterPanelOpen(false)}
          availableTypes={ACCOUNT_TYPES}
          departmentOptions={departmentOptions}
          contactFilters={contactFilters}
          pendingFilters={pending}
          onFilterChange={updatePending}
          onApply={handleApplyFilters}
          onClear={handleClearFilters}
          hasPendingChanges={hasPendingChanges}
          mode="flat"
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
        onReopen={handleReopen}
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
