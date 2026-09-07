// frontend/src/sections/activities/workspace/ActivitySignalsTab.jsx
//
// Activity "Signals" tab — FLAT-FORCED validation worklist (SIG-2 / SIG-2-fix).
// No toggle, NO filter, NO sort: the tab is just the flat SignalsValidationList,
// which splits the activity's signals into 3 status sections (To validate /
// Validated / Rejected), each grouped by type behind a coloured type header.
//
// The list is fed by the aggregated endpoint (useAggregatedSignals) scoped by
// activity_id. It loads ALL 3 statuses (the Rejected section is part of the
// worklist) and the whole matching set in one page (pageSize 100, the endpoint's
// max) — no server pager. Clicking a row injects the signal detail into the
// single workspace drawer coque.

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useEffect } from "react";

// MUI
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";

// Project imports
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
import SignalsValidationList from "components/signals/SignalsValidationList";
import SignalDetailPanel from "components/signals/SignalDetailPanel";
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import SignalEditDrawer from "components/signals/SignalEditDrawer";

// The activity flat view shows qualification (pain/objective/impact) plus
// tech-stack, blockers, constraints, competitors and people — next-steps live
// in their own tab and are excluded.
export const ACTIVITY_FLAT_TYPES = [
  "pain",
  "objective",
  "impact",
  "tech-stack",
  "blockers",
  "constraints",
  "competitors",
  "people",
];

// The validation worklist always loads all 3 statuses — the Rejected section is
// part of it (no "include rejected" opt-in anymore).
const STATUSES = ["PENDING", "VALIDATED", "REJECTED"];

// The aggregated endpoint caps page_size at 100 (core StandardResultsSetPagination).
// One activity's signal set sits well under that, so we fetch it all in one page.
const PAGE_SIZE = 100;

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

  // The single workspace drawer coque (B3.5.3): clicking a signal injects its
  // detail via openDrawer; the coque owns open state + close.
  const { openDrawer } = useWorkspaceDrawer();

  // Edit dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editSignal, setEditSignal] = useState(null);
  const [editType, setEditType] = useState(null);

  // One aggregated call: all flat types, all 3 statuses, whole set in one page,
  // ordered newest-first (the endpoint default). No filter / sort controls.
  const {
    signals: flatSignals,
    loading,
    error,
    mutate: mutateAll,
  } = useAggregatedSignals({
    activityId,
    statuses: STATUSES,
    signalTypes: ACTIVITY_FLAT_TYPES,
    ordering: "date-desc",
    page: 1,
    pageSize: PAGE_SIZE,
  });

  // Handlers
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

  // Inject the signal detail into the single coque. Clicking another signal
  // replaces the content (React reconciles the panel in place); the coque owns
  // the close button. Declared after the action handlers it captures.
  const handleSelect = useCallback(
    (signal, signalType) => {
      openDrawer(
        <SignalDetailPanel
          signal={signal}
          signalType={signalType}
          onValidate={handleValidate}
          onReject={handleReject}
          onEdit={handleEdit}
          onReopen={handleReopen}
          isLocked={isLocked}
        />,
      );
    },
    [openDrawer, handleValidate, handleReject, handleEdit, handleReopen, isLocked],
  );

  const handleEditClose = useCallback(() => {
    setEditDialogOpen(false);
    setEditSignal(null);
    setEditType(null);
  }, []);

  const handleEditSuccess = useCallback(() => {
    mutateAll();
    mutateCounts?.();
  }, [mutateAll, mutateCounts]);

  // A fetch can fail while previous data is still shown (SWR keeps the last
  // data). Keep the list and surface the transient failure via the standard
  // error snackbar instead of blanking the view.
  useEffect(() => {
    if (error && flatSignals.length) displayErrorSnackbar(error);
  }, [error, flatSignals.length]);

  return (
    <Box>
      {/* The flat validation list: 3 status sections × type groups. */}
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
        <SignalsValidationList
          signals={flatSignals}
          loading={loading}
          onSelect={handleSelect}
          onValidate={handleValidate}
          onReject={handleReject}
          emptyMessage="No signals for this activity"
        />
      )}

      {/* Edit Dialog */}
      <SignalEditDrawer
        context="activity"
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
