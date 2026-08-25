// frontend/src/sections/accounts/dc-workspace/SignalsTab.jsx

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo } from "react";

// MUI
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Project imports
import useAggregatedSignals from "api/signals/aggregatedSignals";
import { useGetSignalChoices } from "api/signals/signals";
import { validateSignal, rejectSignal, reopenSignal } from "api/signals/signals";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// Section imports — reuse Activity signal components
import SignalsFilterBar from "sections/activities/signals/SignalsFilterBar";
import SignalsFlatView from "sections/activities/signals/SignalsFlatView";
import SignalsSortSelect from "sections/activities/signals/SignalsSortSelect";
import SignalQuickDrawer from "sections/activities/signals/SignalQuickDrawer";
import SignalEditDialog from "sections/activities/signals/SignalEditDialog";

// ==============================|| SIGNAL TYPE FILTER ||============================== //

const TYPE_FILTERS = [
  { value: "all", label: "All" },
  { value: "pain", label: "Pain" },
  { value: "objective", label: "Objective" },
  { value: "impact", label: "Impact" },
  { value: "tech-stack", label: "Tech Stack" },
  { value: "blockers", label: "Blocker" },
  { value: "next-steps", label: "Next Step" },
  { value: "people", label: "People" },
  { value: "constraints", label: "Constraint" },
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

// ==============================|| TYPE FILTER BAR ||============================== //

import Chip from "@mui/material/Chip";

function TypeFilterBar({ activeType, onChange }) {
  return (
    <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap">
      <Typography variant="caption" color="text.secondary" sx={{ mr: 0.5 }}>
        Type:
      </Typography>
      {TYPE_FILTERS.map((f) => (
        <Chip
          key={f.value}
          label={f.label}
          size="small"
          variant={activeType === f.value ? "filled" : "outlined"}
          color={activeType === f.value ? "primary" : "default"}
          onClick={() => onChange(f.value)}
          clickable
        />
      ))}
    </Stack>
  );
}

TypeFilterBar.propTypes = {
  activeType: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired,
};

// ==============================|| DC SIGNALS TAB ||============================== //

export default function SignalsTab({ cycleId, accountId }) {
  const { choices, choicesLoading } = useGetSignalChoices();

  // Status filter state
  const [statusFilter, setStatusFilter] = useState("all-active");
  const [includeRejected, setIncludeRejected] = useState(false);

  // Type filter state
  const [typeFilter, setTypeFilter] = useState("all");

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

  // --- Map the toolbar controls to aggregated-endpoint params ---
  // Status: "all-active" = PENDING + VALIDATED; a concrete status narrows;
  // "Include rejected" adds REJECTED to whichever base set is active.
  const statuses = useMemo(() => {
    const base =
      statusFilter === "all-active"
        ? ["PENDING", "VALIDATED"]
        : [statusFilter];
    if (includeRejected && !base.includes("REJECTED")) base.push("REJECTED");
    return base;
  }, [statusFilter, includeRejected]);

  const signalTypes = useMemo(
    () => (typeFilter === "all" ? undefined : [typeFilter]),
    [typeFilter],
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

  // Reset to page 1 whenever any control changes the result set.
  const onStatusChange = (v) => { setStatusFilter(v); setPage(1); };
  const onToggleRejected = (v) => { setIncludeRejected(v); setPage(1); };
  const onTypeChange = (v) => { setTypeFilter(v); setPage(1); };
  const onSortChange = (v) => { setSortKey(v); setPage(1); };

  // Technical failure → standard error surface.
  if (error) {
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
      {/* Toolbar: status filter + type filter + sort (all server-driven) */}
      <Stack spacing={1.5} sx={{ mb: 2.5 }}>
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
          flexWrap="wrap"
          gap={1}
        >
          <SignalsFilterBar
            activeFilter={statusFilter}
            onChange={onStatusChange}
            includeRejected={includeRejected}
            onToggleRejected={onToggleRejected}
            hideCounts
          />
          <SignalsSortSelect value={sortKey} onChange={onSortChange} />
        </Stack>
        <TypeFilterBar activeType={typeFilter} onChange={onTypeChange} />
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
        emptyMessage="No signals for this decision cycle"
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
