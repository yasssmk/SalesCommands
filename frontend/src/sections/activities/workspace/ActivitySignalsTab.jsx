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

// Icons
import { ThunderboltOutlined } from "@ant-design/icons";

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
  const [statusFilter, setStatusFilter] = useState("all");

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
  const filteredQualification = useMemo(() => {
    if (statusFilter === "all") return qualificationSignals;
    return qualificationSignals.filter((s) => s.status === statusFilter);
  }, [qualificationSignals, statusFilter]);

  const filteredBlockers = useMemo(() => {
    if (statusFilter === "all") return blockerSignals;
    return blockerSignals.filter((s) => s.status === statusFilter);
  }, [blockerSignals, statusFilter]);

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
          signals={displayableSignals}
        />
        <SignalsViewToggle
          view={view}
          onChange={setView}
          activityId={activityId}
        />
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
        <Box
          display="flex"
          justifyContent="center"
          alignItems="center"
          minHeight="200px"
        >
          <Stack spacing={1} alignItems="center" textAlign="center">
            <ThunderboltOutlined style={{ fontSize: 36, color: "#8c8c8c" }} />
            <Typography variant="body2" color="text.secondary">
              Flat view coming soon
            </Typography>
          </Stack>
        </Box>
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
