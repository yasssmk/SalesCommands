// frontend/src/sections/activities/workspace/ActivityQualificationTab.jsx
//
// Activity "Qualification" tab — the grouped synthesis view for one activity
// (qualification themes + tech + blockers), mirroring the two-tab architecture
// used on the Account and Decision-Cycle workspaces. This is the existing
// Activity grouped view (SignalsGroupedView), moved under its own tab; the
// exhaustive flat list lives in the sibling "Signals" tab.

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo } from "react";

// MUI
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Typography from "@mui/material/Typography";

// Project imports
import useActivityAllSignals from "hooks/useActivityAllSignals";
import { applyGroupedFilters } from "utils/groupedSignalFilter";
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
import SignalsGroupedView from "sections/activities/signals/SignalsGroupedView";
import SignalQuickDrawer from "sections/activities/signals/SignalQuickDrawer";
import SignalEditDialog from "sections/activities/signals/SignalEditDialog";

// ==============================|| ACTIVITY QUALIFICATION TAB (GROUPED) ||============================== //

export default function ActivityQualificationTab({
  activity,
  isLocked,
  mutateCounts,
  groupedFilters = {},
}) {
  const activityId = activity?.id;
  const accountId = activity?.account;

  const {
    qualificationSignals,
    techStackSignals,
    blockerSignals,
    constraintSignals,
    competitorSignals,
    peopleSignals,
    loading,
    error,
    mutateAll,
  } = useActivityAllSignals(activityId);

  const { choices, choicesLoading } = useGetSignalChoices();

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedSignal, setSelectedSignal] = useState(null);
  const [selectedType, setSelectedType] = useState(null);

  // Edit dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editSignal, setEditSignal] = useState(null);
  const [editType, setEditType] = useState(null);

  // Apply the Qualification filters CLIENT-SIDE (single-activity view, no
  // cluster endpoint) before grouping — same perimeter/what/dimension/contact/
  // status model Account/DC apply server-side. Status defaults to pending +
  // validated inside applyGroupedFilters, so REJECTED never shows unless
  // explicitly selected. A tech-stack / blocker signal (no what/dimension/scope)
  // is excluded when a Qualification-only filter is active — mirrors backend.
  const filteredQualification = useMemo(
    () => applyGroupedFilters(qualificationSignals, groupedFilters),
    [qualificationSignals, groupedFilters],
  );
  const filteredTechStack = useMemo(
    () => applyGroupedFilters(techStackSignals, groupedFilters),
    [techStackSignals, groupedFilters],
  );
  const filteredBlockers = useMemo(
    () => applyGroupedFilters(blockerSignals, groupedFilters),
    [blockerSignals, groupedFilters],
  );
  const filteredConstraints = useMemo(
    () => applyGroupedFilters(constraintSignals, groupedFilters),
    [constraintSignals, groupedFilters],
  );
  const filteredCompetitors = useMemo(
    () => applyGroupedFilters(competitorSignals, groupedFilters),
    [competitorSignals, groupedFilters],
  );
  const filteredPeople = useMemo(
    () => applyGroupedFilters(peopleSignals, groupedFilters),
    [peopleSignals, groupedFilters],
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

  // Loading
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
      {/* Grouped content — no filter chips; only pending + validated shown */}
      <SignalsGroupedView
        qualificationSignals={filteredQualification}
        techStackSignals={filteredTechStack}
        blockerSignals={filteredBlockers}
        constraintSignals={filteredConstraints}
        competitorSignals={filteredCompetitors}
        peopleSignals={filteredPeople}
        onSelect={handleSelect}
        onValidate={handleValidate}
        onReject={handleReject}
        isLocked={isLocked}
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

ActivityQualificationTab.propTypes = {
  activity: PropTypes.shape({
    id: PropTypes.string,
    account: PropTypes.string,
  }),
  isLocked: PropTypes.bool,
  mutateCounts: PropTypes.func,
  /** Qualification filters (client-side): { perimeter, whats, dimensions,
      contacts, statuses }. Empty object = no filter (default statuses apply). */
  groupedFilters: PropTypes.object,
};
