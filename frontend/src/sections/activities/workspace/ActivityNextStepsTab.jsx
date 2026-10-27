// frontend/src/sections/activities/workspace/ActivityNextStepsTab.jsx

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";

// MUI
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Divider from "@mui/material/Divider";
import Typography from "@mui/material/Typography";

// Icons
import { PlusOutlined, RocketOutlined } from "@ant-design/icons";

// Project imports
import useAggregatedSignals from "api/signals/aggregatedSignals";
import { getSignal, rejectSignal, reopenSignal } from "api/signals/signals";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

import SignalsValidationList from "components/signals/SignalsValidationList";
import SignalDetailPanel from "components/signals/SignalDetailPanel";
import { SIGNAL_STATUS_PILL } from "components/signals/signalStatusPill";
import { getSignalTypeLabel } from "utils/signalTypes";
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import NextStepActivityLine, {
  getResolvedActivity,
} from "sections/activities/nextSteps/NextStepActivityLine";
import UpcomingActivitiesSection from "sections/activities/nextSteps/UpcomingActivitiesSection";
import { ACTIVITY_STATUSES } from "api/accounts/activities";
import ActivityModal from "sections/accounts/activities/ActivityModal";
import EditNextStepContent from "sections/activities/workspace/EditNextStepContent";
import NextStepValidateFlow from "sections/activities/nextSteps/NextStepValidateFlow";

// The next steps of the activity, all 3 statuses (To validate / Validated /
// Rejected), in one page — the same aggregated query shape as the Signals band.
const NEXT_STEP_TYPES = ["next-steps"];
const STATUSES = ["PENDING", "VALIDATED", "REJECTED"];
const PAGE_SIZE = 100;

// The band's own lock (PO decision): it IGNORES the read-only state of a
// COMPLETED activity — the conversation is over and its next steps are handled
// now — and stays read-only only for these statuses.
export const NEXT_STEPS_LOCKED_STATUSES = [ACTIVITY_STATUSES.CANCELLED];

export function isNextStepsBandLocked(activity) {
  return NEXT_STEPS_LOCKED_STATUSES.includes(activity?.status);
}

// ==============================|| ACTIVITY NEXT STEPS TAB ||============================== //

// The "Next steps" band, in 4 parts (Sprint Next steps 5.x):
//   1. the next planned step (activity.next_planned_step);
//   2. the next steps to validate and 3. the validated (resolved, with their
//      activity on the row's 3rd line) and rejected ones — the generic
//      SignalsValidationList, DC-only;
//   4. "Set a next step manually" (ActivityModal).
export default function ActivityNextStepsTab({ activity, mutateCounts }) {
  const router = useRouter();
  // The single lock predicate of the band (parts 1-4, row actions, drawer).
  const isLocked = isNextStepsBandLocked(activity);
  const activityId = activity?.id;
  const accountId = activity?.account;

  // Data
  const {
    signals: nextStepSignals,
    loading,
    error,
    mutate: mutateAll,
  } = useAggregatedSignals({
    activityId,
    statuses: STATUSES,
    signalTypes: NEXT_STEP_TYPES,
    ordering: "date-desc",
    page: 1,
    pageSize: PAGE_SIZE,
  });

  // The single workspace drawer coque: the next step detail is injected there,
  // as the detail of every other signal type (ActivitySignalsTab).
  const { openDrawer, closeDrawer } = useWorkspaceDrawer();

  // Activity modal state (convert from signal OR manual add OR campaign conversion)
  const [activityModalOpen, setActivityModalOpen] = useState(false);
  const [convertSignal, setConvertSignal] = useState(null);
  const [manualActivityType, setManualActivityType] = useState(null);
  const [convertFromCampaign, setConvertFromCampaign] = useState(false);

  // ==============================|| HANDLERS ||============================== //

  // Open (or re-open after a status change) the detail in the coque. The
  // lifecycle handlers are read from a ref (they in turn re-open the detail) —
  // the ActivitySignalsTab pattern.
  const detailHandlersRef = useRef(null);
  const openDetail = useCallback(
    (signal) => {
      const h = detailHandlersRef.current;
      openDrawer(
        <SignalDetailPanel
          signal={signal}
          signalType="next-steps"
          onValidate={h.onValidate}
          onReject={h.onReject}
          onEdit={h.onEdit}
          onReopen={h.onReopen}
          isLocked={isLocked}
          currentActivityId={activityId}
          headerInCoque
        />,
        {
          title: getSignalTypeLabel("next-steps"),
          status: signal.status,
          statusMap: SIGNAL_STATUS_PILL,
        },
      );
    },
    [openDrawer, isLocked, activityId],
  );

  const handleConvert = useCallback((signal) => {
    setConvertSignal(signal);
    setActivityModalOpen(true);
  }, []);

  // Read a next step back from the server once resolved (by its created OR
  // linked activity — now VALIDATED), refresh the list (3rd line) and re-open
  // its detail.
  const showFromServer = useCallback(
    async (signal) => {
      mutateAll();
      mutateCounts?.();
      const result = await getSignal("next-steps", signal.id);
      if (result.success) {
        openDetail({ ...result.data, _signalType: "next-steps" });
      } else {
        displayErrorSnackbar(result);
        closeDrawer();
      }
    },
    [mutateAll, mutateCounts, openDetail, closeDrawer],
  );

  // The validation flow (5.6), in the coque: step 1 = Create or Link. Opened by
  // the row ✓ and the detail's Validate; Back returns to the detail. Create
  // opens the pre-filled ActivityModal over it — a cancel leaves step 1 shown.
  const openFlow = useCallback(
    (signal) => {
      openDrawer(
        <NextStepValidateFlow
          nextStep={signal}
          onCreate={handleConvert}
          onBack={() => openDetail(signal)}
          onLinked={showFromServer}
        />,
        { title: "Validate next step" },
      );
    },
    [openDrawer, handleConvert, openDetail, showFromServer],
  );

  const handleAddManually = useCallback(() => {
    setConvertSignal(null);
    setActivityModalOpen(true);
  }, []);

  // Edit in the coque (EditNextStepContent), then back to the detail —
  // the chassis edit of every other signal type.
  const handleEdit = useCallback(
    (signal) => {
      openDrawer(
        <EditNextStepContent
          nextStep={signal}
          decisionCycleId={activity?.decision_cycle}
          onSaved={(updated) => {
            mutateAll();
            mutateCounts?.();
            openDetail(updated ?? signal);
          }}
          onCancel={() => openDetail(signal)}
        />,
        { title: "Edit next step" },
      );
    },
    [openDrawer, activity?.decision_cycle, mutateAll, mutateCounts, openDetail],
  );

  const handleReject = useCallback(
    async (signal) => {
      const result = await rejectSignal("next-steps", signal.id);
      if (result.success) {
        displaySuccessSnackbar("Suggestion rejected");
        mutateAll();
        mutateCounts?.();
        openDetail({ ...signal, status: "REJECTED" });
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll, mutateCounts, openDetail],
  );

  const handleReopen = useCallback(
    async (signal) => {
      const result = await reopenSignal("next-steps", signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal reopened — now pending");
        mutateAll();
        mutateCounts?.();
        openDetail({ ...signal, status: "PENDING" });
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll, mutateCounts, openDetail],
  );

  // Nothing here calls validateSignal: a next step is validated only with its
  // activity (rule 2.1) — the server validates it when the activity is created
  // from it. The detail's Validate opens the validation flow.
  detailHandlersRef.current = {
    onValidate: openFlow,
    onReject: handleReject,
    onEdit: handleEdit,
    onReopen: handleReopen,
  };

  const handleOpenActivity = useCallback(
    (id) => router.push(`/activities/${id}`),
    [router],
  );

  // SignalLine's 3rd line — only on a RESOLVED next step (its activity).
  const renderExtra = useCallback(
    (signal) => {
      const resolved = getResolvedActivity(signal);
      return resolved ? (
        <NextStepActivityLine activity={resolved} onOpen={handleOpenActivity} />
      ) : null;
    },
    [handleOpenActivity],
  );

  const handleConvertSuccess = useCallback(() => {
    if (convertSignal) {
      showFromServer(convertSignal);
      return;
    }
    // A manual next step: no next step to show.
    mutateAll();
    mutateCounts?.();
    closeDrawer();
  }, [convertSignal, showFromServer, mutateAll, mutateCounts, closeDrawer]);

  const handleCreateActivity = useCallback(
    (activityType, options = {}) => {
      setConvertSignal(null);
      setManualActivityType(activityType || null);
      setConvertFromCampaign(Boolean(options.convertFromCampaign));
      setActivityModalOpen(true);
    },
    [],
  );

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      {/* Part 1 — the next planned step */}
      <Typography variant="h6" sx={{ mb: 1.5 }}>
        <RocketOutlined style={{ fontSize: 18, marginRight: 8 }} />
        Next planned step
      </Typography>
      <UpcomingActivitiesSection
        activity={activity}
        onCreateActivity={handleCreateActivity}
        isLocked={isLocked}
      />

      {/* Parts 2-3 — to validate / validated / rejected. DC-only: extracted
          next-step suggestions are not proposed in a campaign context
          (activity without a decision_cycle). Mirrors the backend guard. */}
      {Boolean(activity?.decision_cycle) && (
        <>
          <Divider sx={{ my: 2 }} />
          {error && !nextStepSignals.length ? (
            <Box display="flex" justifyContent="center" py={4}>
              <Typography color="error">Failed to load next steps</Typography>
            </Box>
          ) : (
            <SignalsValidationList
              signals={nextStepSignals}
              loading={loading}
              onSelect={openDetail}
              onValidate={isLocked ? undefined : openFlow}
              onReject={isLocked ? undefined : handleReject}
              renderExtra={renderExtra}
              emptyMessage="No next-step suggestions for this activity"
            />
          )}
        </>
      )}

      {/* Part 4 — a next step typed by hand is an activity */}
      {!isLocked && (
        <Box mt={2}>
          <Button
            variant="outlined"
            size="small"
            startIcon={<PlusOutlined style={{ fontSize: 14 }} />}
            onClick={handleAddManually}
          >
            Set a next step manually
          </Button>
        </Box>
      )}

      {/* Activity modal (convert from signal or manual add) */}
      {accountId && (
        <ActivityModal
          open={activityModalOpen}
          onClose={() => {
            setActivityModalOpen(false);
            setConvertSignal(null);
            setManualActivityType(null);
            setConvertFromCampaign(false);
          }}
          activity={null}
          accountId={accountId}
          decisionStepId={activity?.decision_step || null}
          decisionCycleId={convertFromCampaign ? null : (activity?.decision_cycle || null)}
          defaultActivityType={convertSignal?.suggested_activity_type || manualActivityType || "MEETING"}
          previousActivityId={activity?.id}
          sourceActivityId={convertFromCampaign ? activity?.id : null}
          nextStepSignal={convertSignal}
          onSuccess={handleConvertSuccess}
        />
      )}

    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

ActivityNextStepsTab.propTypes = {
  activity: PropTypes.shape({
    id: PropTypes.string,
    account: PropTypes.string,
    status: PropTypes.string,
    decision_step: PropTypes.string,
    decision_cycle: PropTypes.string,
    sequence_context: PropTypes.object,
    campaign_detail: PropTypes.object,
  }),
  mutateCounts: PropTypes.func,
};
