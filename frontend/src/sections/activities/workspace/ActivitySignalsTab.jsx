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
import { useGetSignalChoices } from "api/signals/signals";
import {
  validateSignal,
  rejectSignal,
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

// ==============================|| ACTIVITY SIGNALS TAB ||============================== //

export default function ActivitySignalsTab({
  activity,
  isLocked,
  mutateCounts,
}) {
  const activityId = activity?.id;
  const accountId = activity?.account;

  // Signals data
  const {
    qualificationSignals,
    blockerSignals,
    loading,
    error,
    mutateAll,
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

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedSignal, setSelectedSignal] = useState(null);
  const [selectedType, setSelectedType] = useState(null);

  // Edit dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editSignal, setEditSignal] = useState(null);
  const [editType, setEditType] = useState(null);

  // All displayable signals (qualification + blockers, excluding next-steps)
  const displayableSignals = useMemo(
    () => [...qualificationSignals, ...blockerSignals],
    [qualificationSignals, blockerSignals],
  );

  // Filtered signals
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

  const filteredBlockers = useMemo(
    () => blockerSignals.filter(filterFn),
    [blockerSignals, filterFn],
  );

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

  // Loading state
  if (loading) {
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

  // Error state
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
      {/* Toolbar: view toggle + filter */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ mb: 2.5, flexWrap: "wrap", gap: 1 }}
      >
        <SignalsFilterBar
          activeFilter={statusFilter}
          onChange={setStatusFilter}
          includeRejected={includeRejected}
          onToggleRejected={setIncludeRejected}
          signals={displayableSignals}
        />
        <Stack direction="row" spacing={1} alignItems="center">
          {view === "flat" && (
            <SignalsSortSelect value={sortKey} onChange={setSortKey} />
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
          blockerSignals={filteredBlockers}
          onSelect={handleSelect}
          onValidate={handleValidate}
          onReject={handleReject}
          isLocked={isLocked}
        />
      ) : (
        <SignalsFlatView
          signals={[...filteredQualification, ...filteredBlockers]}
          sortKey={sortKey}
          onValidate={handleValidate}
          onReject={handleReject}
          onEdit={handleEdit}
          isLocked={isLocked}
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
