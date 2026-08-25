// frontend/src/sections/activities/workspace/ActivitySignalsTab.jsx

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo } from "react";

// MUI
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Project imports
import useActivityAllSignals from "hooks/useActivityAllSignals";
import useAggregatedSignals from "api/signals/aggregatedSignals";
import { useGetSignalChoices } from "api/signals/signals";
import {
  validateSignal,
  rejectSignal,
  reopenSignal,
} from "api/signals/signals";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// Section imports
import SignalsViewToggle, {
  getPersistedView,
} from "sections/activities/signals/SignalsViewToggle";
import SignalsFilterBar from "sections/activities/signals/SignalsFilterBar";
import SignalsGroupedView from "sections/activities/signals/SignalsGroupedView";
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

// ==============================|| ACTIVITY SIGNALS TAB ||============================== //

export default function ActivitySignalsTab({
  activity,
  isLocked,
  mutateCounts,
}) {
  const activityId = activity?.id;
  const accountId = activity?.account;

  // Grouped-view data (client-side; still per-type until the grouped step).
  const {
    qualificationSignals,
    techStackSignals,
    blockerSignals,
    loading: groupedLoading,
    error: groupedError,
    mutateAll: mutateGrouped,
  } = useActivityAllSignals(activityId);

  // Choices for edit forms
  const { choices, choicesLoading } = useGetSignalChoices();

  // View toggle state
  const [view, setView] = useState(() => getPersistedView(activityId));

  // Filter state
  const [statusFilter, setStatusFilter] = useState("all-active");
  const [includeRejected, setIncludeRejected] = useState(false);

  // Sort state (flat view only)
  const [sortKey, setSortKey] = useState("date-desc");

  // Pagination (flat view only)
  const [page, setPage] = useState(1);

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedSignal, setSelectedSignal] = useState(null);
  const [selectedType, setSelectedType] = useState(null);

  // Edit dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editSignal, setEditSignal] = useState(null);
  const [editType, setEditType] = useState(null);

  // --- Flat view: one aggregated call, server-driven filter/sort/paginate ---
  const statuses = useMemo(() => {
    const base =
      statusFilter === "all-active"
        ? ["PENDING", "VALIDATED"]
        : [statusFilter];
    if (includeRejected && !base.includes("REJECTED")) base.push("REJECTED");
    return base;
  }, [statusFilter, includeRejected]);

  const {
    signals: flatSignals,
    pageCount,
    loading: flatLoading,
    error: flatError,
    mutate: mutateFlat,
  } = useAggregatedSignals({
    activityId,
    statuses,
    signalTypes: ACTIVITY_FLAT_TYPES,
    ordering: sortKey,
    page,
    pageSize: 20,
  });

  // All displayable signals feed the grouped filter-bar counts.
  const displayableSignals = useMemo(
    () => [...qualificationSignals, ...techStackSignals, ...blockerSignals],
    [qualificationSignals, techStackSignals, blockerSignals],
  );

  // Grouped view keeps client-side filtering.
  const filterFn = useCallback(
    (s) => {
      const isRejected = s.status === "REJECTED";
      if (isRejected) return includeRejected;
      if (statusFilter === "all-active") return true;
      return s.status === statusFilter;
    },
    [statusFilter, includeRejected],
  );

  const filteredQualification = useMemo(
    () => qualificationSignals.filter(filterFn),
    [qualificationSignals, filterFn],
  );

  const filteredTechStack = useMemo(
    () => techStackSignals.filter(filterFn),
    [techStackSignals, filterFn],
  );

  const filteredBlockers = useMemo(
    () => blockerSignals.filter(filterFn),
    [blockerSignals, filterFn],
  );

  // Refresh both data sources so either view is fresh after a mutation.
  const mutateBoth = useCallback(() => {
    mutateGrouped();
    mutateFlat();
  }, [mutateGrouped, mutateFlat]);

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
        mutateBoth();
        mutateCounts?.();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateBoth, mutateCounts],
  );

  const handleReject = useCallback(
    async (signal, signalType) => {
      const result = await rejectSignal(signalType, signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal rejected");
        mutateBoth();
        mutateCounts?.();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateBoth, mutateCounts],
  );

  const handleReopen = useCallback(
    async (signal, signalType) => {
      const result = await reopenSignal(signalType, signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal reopened — now pending");
        mutateBoth();
        mutateCounts?.();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateBoth, mutateCounts],
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
    mutateBoth();
    mutateCounts?.();
  }, [mutateBoth, mutateCounts]);

  // Reset to page 1 whenever a control changes the flat result set.
  const onStatusChange = (v) => {
    setStatusFilter(v);
    setPage(1);
  };
  const onToggleRejected = (v) => {
    setIncludeRejected(v);
    setPage(1);
  };
  const onSortChange = (v) => {
    setSortKey(v);
    setPage(1);
  };

  // Loading state — grouped view only (flat view has its own inline spinner).
  if (view === "grouped" && groupedLoading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="300px"
      >
        <CircularProgress />
      </Box>
    );
  }

  // Error state — technical failure of whichever view is active.
  if ((view === "grouped" && groupedError) || (view === "flat" && flatError)) {
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
      {/* Toolbar: view toggle + filter */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ mb: 2.5, flexWrap: "wrap", gap: 1 }}
      >
        <SignalsFilterBar
          activeFilter={statusFilter}
          onChange={onStatusChange}
          includeRejected={includeRejected}
          onToggleRejected={onToggleRejected}
          signals={displayableSignals}
          hideCounts={view === "flat"}
        />
        <Stack direction="row" spacing={1} alignItems="center">
          {view === "flat" && (
            <SignalsSortSelect value={sortKey} onChange={onSortChange} />
          )}
          <SignalsViewToggle
            view={view}
            onChange={setView}
            activityId={activityId}
          />
        </Stack>
      </Stack>

      {/* Content */}
      {view === "grouped" ? (
        <SignalsGroupedView
          qualificationSignals={filteredQualification}
          techStackSignals={filteredTechStack}
          blockerSignals={filteredBlockers}
          onSelect={handleSelect}
          onValidate={handleValidate}
          onReject={handleReject}
          isLocked={isLocked}
        />
      ) : (
        <SignalsFlatView
          signals={flatSignals}
          serverPaginated
          page={page}
          pageCount={pageCount}
          onPageChange={setPage}
          loading={flatLoading}
          onSelect={handleSelect}
          onValidate={handleValidate}
          onReject={handleReject}
          onEdit={handleEdit}
          onReopen={handleReopen}
          isLocked={isLocked}
          emptyMessage="No signals for this activity"
        />
      )}

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
