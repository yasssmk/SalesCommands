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
import { useState, useCallback, useEffect, useRef } from "react";

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
import { SIGNAL_STATUS_PILL } from "components/signals/signalStatusPill";
import { getSignalTypeLabel } from "utils/signalTypes";
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import SignalEditDrawer from "components/signals/SignalEditDrawer";
import EditObjectiveContent from "sections/activities/workspace/EditObjectiveContent";
import EditPainContent from "sections/activities/workspace/EditPainContent";

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

  // Re-open the detail in the coque after a status change so the drawer stays
  // OPEN and RETURNS to the (refreshed) detail instead of showing the stale
  // pre-action content. The lifecycle handlers are read from a ref to avoid a
  // circular useCallback dependency (they in turn call this to re-open).
  const detailHandlersRef = useRef(null);
  const openSignalDetail = useCallback(
    (signal, signalType) => {
      const h = detailHandlersRef.current;
      // Standard-chassis types (Objective, Pain) have their header (title +
      // status pill + ×) owned by the COQUE (UI-1): pass title + status + the
      // shared status map, and tell the panel to suppress its in-content header.
      // Other types keep the panel's own (flush) header.
      const coqueOwnsHeader =
        signalType === "objective" || signalType === "pain" || signalType === "impact";
      openDrawer(
        <SignalDetailPanel
          signal={signal}
          signalType={signalType}
          onValidate={h.onValidate}
          onReject={h.onReject}
          onEdit={h.onEdit}
          onReopen={h.onReopen}
          isLocked={isLocked}
          currentActivityId={activityId}
          headerInCoque={coqueOwnsHeader}
        />,
        coqueOwnsHeader
          ? { title: getSignalTypeLabel(signalType), status: signal.status, statusMap: SIGNAL_STATUS_PILL }
          : undefined,
      );
    },
    [openDrawer, isLocked, activityId],
  );

  // Handlers
  const handleValidate = useCallback(
    async (signal, signalType) => {
      const result = await validateSignal(signalType, signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal validated");
        mutateAll();
        mutateCounts?.();
        openSignalDetail({ ...signal, status: "VALIDATED" }, signalType);
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll, mutateCounts, openSignalDetail],
  );

  const handleReject = useCallback(
    async (signal, signalType) => {
      const result = await rejectSignal(signalType, signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal rejected");
        mutateAll();
        mutateCounts?.();
        openSignalDetail({ ...signal, status: "REJECTED" }, signalType);
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll, mutateCounts, openSignalDetail],
  );

  const handleReopen = useCallback(
    async (signal, signalType) => {
      const result = await reopenSignal(signalType, signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal reopened — now pending");
        mutateAll();
        mutateCounts?.();
        openSignalDetail({ ...signal, status: "PENDING" }, signalType);
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll, mutateCounts, openSignalDetail],
  );

  const handleEdit = useCallback(
    (signal, signalType) => {
      // SIG-5d: Objective edits go to the new drawer (DrawerContentLayout +
      // scope pill + editable source_quote) via the single coque. Every other
      // type keeps the legacy SignalEditDrawer dialog untouched.
      if (signalType === "objective") {
        openDrawer(
          <EditObjectiveContent
            objective={signal}
            accountId={accountId}
            onSaved={(updated) => {
              mutateAll();
              mutateCounts?.();
              // Return to the detail (updated), keeping the coque open.
              openSignalDetail(updated ?? signal, "objective");
            }}
            onCancel={() => openSignalDetail(signal, "objective")}
          />,
          { title: "Edit objective" },
        );
        return;
      }
      // S3: Pain edits go to the new chassis drawer (mirror of Objective) — the
      // M2M department multi-select lives inside. Other types stay on the legacy
      // SignalEditDrawer dialog below.
      if (signalType === "pain") {
        openDrawer(
          <EditPainContent
            pain={signal}
            accountId={accountId}
            onSaved={(updated) => {
              mutateAll();
              mutateCounts?.();
              // Return to the detail (updated), keeping the coque open.
              openSignalDetail(updated ?? signal, "pain");
            }}
            onCancel={() => openSignalDetail(signal, "pain")}
          />,
          { title: "Edit pain" },
        );
        return;
      }
      setEditSignal(signal);
      setEditType(signalType);
      setEditDialogOpen(true);
    },
    [openDrawer, accountId, mutateAll, mutateCounts, openSignalDetail],
  );

  // Keep the ref pointing at the latest lifecycle handlers so openSignalDetail
  // (which re-opens the detail after a status change) always wires the current
  // callbacks without depending on them.
  detailHandlersRef.current = {
    onValidate: handleValidate,
    onReject: handleReject,
    onEdit: handleEdit,
    onReopen: handleReopen,
  };

  // Inject the signal detail into the single coque. Clicking another signal
  // replaces the content (React reconciles the panel in place); the coque owns
  // the close button.
  const handleSelect = useCallback(
    (signal, signalType) => openSignalDetail(signal, signalType),
    [openSignalDetail],
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
