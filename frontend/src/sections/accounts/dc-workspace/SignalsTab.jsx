// frontend/src/sections/accounts/dc-workspace/SignalsTab.jsx

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
import { validateSignal, rejectSignal, reopenSignal } from "api/signals/signals";
import { useGetContactChoices } from "api/businessData/contacts";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// Section imports — reuse Activity signal components
import SignalsFilterPanel from "sections/activities/signals/SignalsFilterPanel";
import SignalsFlatView from "sections/activities/signals/SignalsFlatView";
import SignalsSortSelect from "sections/activities/signals/SignalsSortSelect";
import SignalQuickDrawer from "sections/activities/signals/SignalQuickDrawer";
import SignalEditDialog from "sections/activities/signals/SignalEditDialog";

// The DC flat list covers every signal type captured in a decision cycle.
const DC_TYPES = [
  "pain",
  "objective",
  "impact",
  "tech-stack",
  "blockers",
  "next-steps",
  "people",
  "constraints",
];

// Types supported by SignalEditDialog (inline forms exist only for these)
const EDITABLE_TYPES = new Set([
  "pain",
  "objective",
  "impact",
  "tech-stack",
  "blockers",
  "next-steps",
]);

// ==============================|| DC SIGNALS TAB ||============================== //

export default function SignalsTab({ cycleId, accountId }) {
  const { choices, choicesLoading } = useGetSignalChoices();

  // Filter state (standard filter drawer)
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

  // Sort state
  const [sortKey, setSortKey] = useState("date-desc");

  // Pagination
  const [page, setPage] = useState(1);

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedSignal, setSelectedSignal] = useState(null);
  const [selectedType, setSelectedType] = useState(null);

  // Edit dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editSignal, setEditSignal] = useState(null);
  const [editType, setEditType] = useState(null);

  // The filter drawer drives signal_type (a subset; none selected = all DC
  // types) and status (default pending+validated, +rejected when opted in).
  const signalTypes = useMemo(
    () => (activeTypes.length ? activeTypes : undefined),
    [activeTypes],
  );

  const {
    signals: filteredSignals,
    pageCount,
    loading,
    error,
    mutate: mutateAll,
  } = useAggregatedSignals({
    decisionCycleId: cycleId,
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
  const handleValidate = useCallback(
    async (signal, signalType) => {
      const result = await validateSignal(signalType, signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal validated");
        mutateAll();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll],
  );

  const handleReject = useCallback(
    async (signal, signalType) => {
      const result = await rejectSignal(signalType, signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal rejected");
        mutateAll();
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
        displaySuccessSnackbar("Signal reopened — now pending");
        mutateAll();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll],
  );

  const handleEdit = useCallback((signal, signalType) => {
    if (!EDITABLE_TYPES.has(signalType)) return;
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
  }, [mutateAll]);

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

  // Reset to page 1 whenever a control changes the result set.
  const onSortChange = (v) => { setSortKey(v); setPage(1); };
  const handleOpenFilters = () => { syncPending(); setFilterPanelOpen(true); };
  const handleApplyFilters = () => { apply(); setPage(1); };
  const handleClearFilters = () => { clear(); setPage(1); };

  // A page fetch can fail while a previous page is still shown (SWR keeps the
  // last data). Keep the list and surface the transient failure through the
  // standard error snackbar instead of blanking the view.
  useEffect(() => {
    if (error && filteredSignals.length) displayErrorSnackbar(error);
  }, [error, filteredSignals.length]);

  // Technical failure with nothing to show → standard error surface.
  if (error && !filteredSignals.length) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="300px"
      >
        <Typography color="error">Failed to load signals</Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Toolbar: sort + filter icon (drawer) */}
      <Stack
        direction="row"
        justifyContent="flex-end"
        alignItems="center"
        gap={1}
        sx={{ mb: 2.5 }}
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

      {/* Signal list — flat view only (grouped view = Strategic/Themes tab) */}
      <SignalsFlatView
        signals={filteredSignals}
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
        isLocked={false}
        emptyMessage="No signals match these filters"
      />

      {/* Filter drawer */}
      <SignalsFilterPanel
        open={filterPanelOpen}
        onClose={() => setFilterPanelOpen(false)}
        availableTypes={DC_TYPES}
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
        onReopen={handleReopen}
        isLocked={false}
      />

      {/* Edit Dialog (6 original types only — people/constraints forms deferred) */}
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

SignalsTab.propTypes = {
  cycleId: PropTypes.string.isRequired,
  accountId: PropTypes.string.isRequired,
};
