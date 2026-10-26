// frontend/src/sections/activities/workspace/ActivityNextStepsTab.jsx

"use client";

import PropTypes from "prop-types";
import { useState, useCallback } from "react";
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
import {
  useGetSignalChoices,
  rejectSignal,
  reopenSignal,
} from "api/signals/signals";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

import SignalsValidationList from "components/signals/SignalsValidationList";
import NextStepSuggestionDrawer from "sections/activities/nextSteps/NextStepSuggestionDrawer";
import NextStepActivityLine, {
  getResolvedActivity,
} from "sections/activities/nextSteps/NextStepActivityLine";
import UpcomingActivitiesSection from "sections/activities/nextSteps/UpcomingActivitiesSection";
import ActivityModal from "sections/accounts/activities/ActivityModal";
import SignalEditDrawer from "components/signals/SignalEditDrawer";

// The next steps of the activity, all 3 statuses (To validate / Validated /
// Rejected), in one page — the same aggregated query shape as the Signals band.
const NEXT_STEP_TYPES = ["next-steps"];
const STATUSES = ["PENDING", "VALIDATED", "REJECTED"];
const PAGE_SIZE = 100;

// ==============================|| ACTIVITY NEXT STEPS TAB ||============================== //

// The "Next steps" band, in 4 parts (Sprint Next steps 5.x):
//   1. the next planned step (activity.next_planned_step);
//   2. the next steps to validate and 3. the validated (resolved, with their
//      activity on the row's 3rd line) and rejected ones — the generic
//      SignalsValidationList, DC-only;
//   4. "Set a next step manually" (ActivityModal).
export default function ActivityNextStepsTab({
  activity,
  isLocked,
  mutateCounts,
}) {
  const router = useRouter();
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
  const { choices, choicesLoading } = useGetSignalChoices();

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerSignal, setDrawerSignal] = useState(null);

  // Activity modal state (convert from signal OR manual add OR campaign conversion)
  const [activityModalOpen, setActivityModalOpen] = useState(false);
  const [convertSignal, setConvertSignal] = useState(null);
  const [manualActivityType, setManualActivityType] = useState(null);
  const [convertFromCampaign, setConvertFromCampaign] = useState(false);

  // Edit dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editSignal, setEditSignal] = useState(null);

  // ==============================|| HANDLERS ||============================== //

  const handleSelect = useCallback((signal) => {
    setDrawerSignal(signal);
    setDrawerOpen(true);
  }, []);

  const handleCloseDrawer = useCallback(() => {
    setDrawerOpen(false);
    setDrawerSignal(null);
  }, []);

  const handleConvert = useCallback((signal) => {
    setConvertSignal(signal);
    setActivityModalOpen(true);
  }, []);

  const handleAddManually = useCallback(() => {
    setConvertSignal(null);
    setActivityModalOpen(true);
  }, []);

  const handleEdit = useCallback((signal) => {
    setEditSignal(signal);
    setEditDialogOpen(true);
  }, []);

  const handleReject = useCallback(
    async (signal) => {
      const result = await rejectSignal("next-steps", signal.id);
      if (result.success) {
        displaySuccessSnackbar("Suggestion rejected");
        mutateAll();
        mutateCounts?.();
        handleCloseDrawer();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll, mutateCounts, handleCloseDrawer],
  );

  const handleReopen = useCallback(
    async (signal) => {
      const result = await reopenSignal("next-steps", signal.id);
      if (result.success) {
        displaySuccessSnackbar("Signal reopened — now pending");
        mutateAll();
        mutateCounts?.();
        handleCloseDrawer();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll, mutateCounts, handleCloseDrawer],
  );

  // The row ✓ validates NOTHING: a next step is validated only with its
  // activity (rule 2.1) — it opens the detail drawer, where the flow starts.
  const handleValidate = handleSelect;

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

  const handleViewActivity = useCallback(
    (linkedActivity) => {
      if (linkedActivity?.id) {
        router.push(`/activities/${linkedActivity.id}/workspace?tab=overview`);
      }
    },
    [router],
  );

  const handleConvertSuccess = useCallback(() => {
    mutateAll();
    mutateCounts?.();
  }, [mutateAll, mutateCounts]);

  const handleEditSuccess = useCallback(() => {
    mutateAll();
    mutateCounts?.();
  }, [mutateAll, mutateCounts]);

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
              onSelect={handleSelect}
              onValidate={handleValidate}
              onReject={handleReject}
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

      {/* Suggestion Drawer */}
      <NextStepSuggestionDrawer
        open={drawerOpen}
        signal={drawerSignal}
        onClose={handleCloseDrawer}
        onConvert={handleConvert}
        onReject={handleReject}
        onEdit={handleEdit}
        onReopen={handleReopen}
        onViewActivity={handleViewActivity}
        isLocked={isLocked}
      />

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

      {/* Signal edit dialog */}
      <SignalEditDrawer context="activity"
        open={editDialogOpen}
        onClose={() => {
          setEditDialogOpen(false);
          setEditSignal(null);
        }}
        onSuccess={handleEditSuccess}
        signal={editSignal}
        signalType="next-steps"
        accountId={accountId || ""}
        choices={choices}
        choicesLoading={choicesLoading}
      />
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
  isLocked: PropTypes.bool,
  mutateCounts: PropTypes.func,
};
