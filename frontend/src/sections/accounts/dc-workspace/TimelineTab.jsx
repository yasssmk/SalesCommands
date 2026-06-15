"use client";

import PropTypes from "prop-types";
import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";

// Project imports
import DecisionCycleTimeline from "sections/accounts/decision-cycles/DecisionCycleTimeline";
import ActivityModal from "sections/accounts/activities/ActivityModal";
import StepDetailDrawer from "./StepDetailDrawer";

// ==============================|| DC WORKSPACE - TIMELINE TAB ||============================== //

export default function TimelineTab({ cycle, accountId, onRefresh }) {
  const router = useRouter();

  // Step detail drawer state
  const [drawerStep, setDrawerStep] = useState(null);

  // Activity Modal state (create within step)
  const [activityModalOpen, setActivityModalOpen] = useState(false);
  const [activityTargetStep, setActivityTargetStep] = useState(null);

  const isCycleClosed = ["WON", "LOST", "NOT_QUALIFIED"].includes(
    cycle?.outcome,
  );

  const handleStepClick = useCallback((step) => {
    setDrawerStep(step);
  }, []);

  const handleGoToStep = useCallback(
    (step) => {
      if (accountId) {
        router.push(`/accounts/${accountId}/decisionSteps/${step.id}`);
      }
    },
    [accountId, router],
  );

  const handleActivityClick = useCallback(
    (activity) => {
      router.push(`/activities/${activity.id}`);
    },
    [router],
  );

  const handleAddActivity = useCallback(
    (step) => {
      if (isCycleClosed) return;
      setActivityTargetStep(step);
      setActivityModalOpen(true);
    },
    [isCycleClosed],
  );

  const handleActivityModalClose = useCallback(() => {
    setActivityModalOpen(false);
    setActivityTargetStep(null);
  }, []);

  const handleActivitySuccess = useCallback(() => {
    onRefresh?.();
    handleActivityModalClose();
  }, [onRefresh, handleActivityModalClose]);

  return (
    <>
      <DecisionCycleTimeline
        cycle={cycle}
        accountId={accountId}
        onStepClick={handleStepClick}
        onActivityClick={handleActivityClick}
        onAddActivity={handleAddActivity}
        onRefresh={onRefresh}
      />

      <StepDetailDrawer
        open={Boolean(drawerStep)}
        step={drawerStep}
        onClose={() => setDrawerStep(null)}
        onGoToStep={handleGoToStep}
      />

      <ActivityModal
        open={activityModalOpen}
        onClose={handleActivityModalClose}
        activity={null}
        accountId={accountId}
        decisionCycleId={cycle?.id}
        decisionStepId={activityTargetStep?.id}
        onSuccess={handleActivitySuccess}
      />
    </>
  );
}

TimelineTab.propTypes = {
  cycle: PropTypes.object,
  accountId: PropTypes.string,
  onRefresh: PropTypes.func,
};
