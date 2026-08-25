// frontend/src/sections/activities/workspace/ActivitySignalsTab.jsx
//
// Activity "Signals" tab — the flat, exhaustive list of the activity's
// signals (SignalLine rows via the aggregated endpoint scoped by activity_id,
// server-paginated 20/page). The grouped synthesis lives in its own
// "Qualification" tab (ActivityQualificationTab), mirroring Account / DC.

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo, useEffect } from "react";

// MUI
import Badge from "@mui/material/Badge";
import Box from "@mui/material/Box";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// icons
import FilterOutlined from "@ant-design/icons/FilterOutlined";

// Project imports
import useAggregatedSignals from "api/signals/aggregatedSignals";
import useSignalFilters from "hooks/useSignalFilters";
import { useGetSignalChoices } from "api/signals/signals";
import {
  validateSignal,
  rejectSignal,
  reopenSignal,
} from "api/signals/signals";
import { useGetContactChoices } from "api/businessData/contacts";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// Section imports
import SignalsFilterPanel from "sections/activities/signals/SignalsFilterPanel";
import SignalQuickDrawer from "sections/activities/signals/SignalQuickDrawer";
import SignalEditDialog from "sections/activities/signals/SignalEditDialog";
import SignalsFlatView from "sections/activities/signals/SignalsFlatView";
import SignalsSortSelect from "sections/activities/signals/SignalsSortSelect";

// The activity flat view shows qualification (pain/objective/impact) plus
// tech-stack and blockers — next-steps live in their own tab and are excluded.
const ACTIVITY_FLAT_TYPES = [
  "pain",
  "objective",
  "impact",
  "tech-stack",
  "blockers",
];

// ==============================|| ACTIVITY SIGNALS TAB (FLAT) ||============================== //

export default function ActivitySignalsTab({
  activity,
  isLocked,
  mutateCounts,
}) {
  const activityId = activity?.id;
  const accountId = activity?.account;

  // Choices for edit forms
  const { choices, choicesLoading } = useGetSignalChoices();

  // Filter / sort / pagination state
  const [filterPanelOpen, setFilterPanelOpen] = useState(false);
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

  const [sortKey, setSortKey] = useState("date-desc");
  const [page, setPage] = useState(1);

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedSignal, setSelectedSignal] = useState(null);
  const [selectedType, setSelectedType] = useState(null);

  // Edit dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editSignal, setEditSignal] = useState(null);
  const [editType, setEditType] = useState(null);

  // One aggregated call, server-driven filter / sort / paginate. The filter
  // drawer drives signal_type (a subset; none selected = all activity types)
  // and status (default pending+validated, +rejected when opted in).
  const signalTypes = useMemo(
    () => (activeTypes.length ? activeTypes : ACTIVITY_FLAT_TYPES),
    [activeTypes],
  );

  const {
    signals: flatSignals,
    pageCount,
    loading,
    error,
    mutate: mutateAll,
  } = useAggregatedSignals({
    activityId,
    statuses,
    signalTypes,
    department,
    contact: contactId,
    scope,
    ordering: sortKey,
    page,
    pageSize: 20,
  });

  // Handlers
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

  const handleValidate = useCallback(
    async (signal, signalType) => {
      const result = await validateSignal(signalType, signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal validated");
        mutateAll();
        mutateCounts?.();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll, mutateCounts],
  );

  const handleReject = useCallback(
    async (signal, signalType) => {
      const result = await rejectSignal(signalType, signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal rejected");
        mutateAll();
        mutateCounts?.();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll, mutateCounts],
  );

  const handleReopen = useCallback(
    async (signal, signalType) => {
      const result = await reopenSignal(signalType, signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal reopened — now pending");
        mutateAll();
        mutateCounts?.();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll, mutateCounts],
  );

  const handleEdit = useCallback((signal, signalType) => {
    setEditSignal(signal);
    setEditType(signalType);
    setEditDialogOpen(true);
  }, []);

  const handleEditClose = useCallback(() => {
    setEditDialogOpen(false);
    setEditSignal(null);
    setEditType(null);
  }, []);

  const handleEditSuccess = useCallback(() => {
    mutateAll();
    mutateCounts?.();
  }, [mutateAll, mutateCounts]);

  // Reset to page 1 whenever a control changes the result set.
  const onSortChange = (v) => {
    setSortKey(v);
    setPage(1);
  };
  const handleOpenFilters = () => {
    syncPending();
    setFilterPanelOpen(true);
  };
  const handleApplyFilters = () => {
    apply();
    setPage(1);
  };
  const handleClearFilters = () => {
    clear();
    setPage(1);
  };

  // A page fetch can fail while a previous page is still shown (SWR keeps the
  // last data). Keep the list and surface the transient failure via the
  // standard error snackbar instead of blanking the view.
  useEffect(() => {
    if (error && flatSignals.length) displayErrorSnackbar(error);
  }, [error, flatSignals.length]);

  return (
    <Box>
      {/* Toolbar: sort + filter icon (drawer) */}
      <Stack
        direction="row"
        justifyContent="flex-end"
        alignItems="center"
        sx={{ mb: 2.5, flexWrap: "wrap", gap: 1 }}
      >
        <SignalsSortSelect value={sortKey} onChange={onSortChange} />
        <Tooltip title="Filters">
          <IconButton onClick={handleOpenFilters} aria-label="Open filters">
            <Badge badgeContent={activeCount} color="primary">
              <FilterOutlined />
            </Badge>
          </IconButton>
        </Tooltip>
      </Stack>

      {/* Technical failure with nothing to show → standard error surface. */}
      {error && !flatSignals.length ? (
        <Box
          display="flex"
          justifyContent="center"
          alignItems="center"
          minHeight="300px"
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
          onReject={handleReject}
          onEdit={handleEdit}
          onReopen={handleReopen}
          isLocked={isLocked}
          emptyMessage="No signals match these filters"
        />
      )}

      {/* Filter drawer */}
      <SignalsFilterPanel
        open={filterPanelOpen}
        onClose={() => setFilterPanelOpen(false)}
        availableTypes={ACTIVITY_FLAT_TYPES}
        departmentOptions={departmentOptions}
        contactFilters={contactFilters}
        pendingFilters={pending}
        onFilterChange={updatePending}
        onApply={handleApplyFilters}
        onClear={handleClearFilters}
        hasPendingChanges={hasPendingChanges}
      />

      {/* Quick Drawer */}
      <SignalQuickDrawer
        open={drawerOpen}
        signal={selectedSignal}
        signalType={selectedType}
        onClose={handleCloseDrawer}
        onValidate={handleValidate}
        onReject={handleReject}
        onEdit={handleEdit}
        isLocked={isLocked}
      />

      {/* Edit Dialog */}
      <SignalEditDialog
        open={editDialogOpen}
        onClose={handleEditClose}
        onSuccess={handleEditSuccess}
        signal={editSignal}
        signalType={editType}
        accountId={accountId}
        choices={choices}
        choicesLoading={choicesLoading}
      />
    </Box>
  );
}

ActivitySignalsTab.propTypes = {
  activity: PropTypes.shape({
    id: PropTypes.string,
    account: PropTypes.string,
  }),
  isLocked: PropTypes.bool,
  mutateCounts: PropTypes.func,
};
