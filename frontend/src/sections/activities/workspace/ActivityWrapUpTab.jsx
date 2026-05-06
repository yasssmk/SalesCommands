// frontend/src/sections/activities/workspace/ActivityWrapUpTab.jsx
/**
 * ActivityWrapUpTab — orchestrator for the Activity Wrap-up tab.
 *
 * Replaces three legacy tabs (Outcome / Signals / Transcript) with a single
 * vertical flow that mirrors the SDR's mental model post-call:
 *   1. Capture  : notes, transcript, signals (manual + AI-extraction CTAs)
 *   2. Next     : follow-up activities planning
 *
 * Result lives at the header (ActivityHeader.jsx) — Complete / Cancel /
 * Reopen / outcome chip are all surfaced there, so this tab no longer
 * carries a Result column.
 *
 * The orchestrator is intentionally thin:
 *   - WrapUpCaptureSection owns notes/transcript editing, signal hooks,
 *     and all related modal state.
 *   - NextStepsSection owns sequence display.
 *   - ActivityWrapUpTab only owns the follow-up creation modal —
 *     because that modal is triggered from NextStepsSection but should
 *     be rendered at the tab level (avoids the modal living in a
 *     section component that may unmount on prop changes).
 */

"use client";

import { useState } from "react";
import PropTypes from "prop-types";

// material-ui
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";

// project imports
import ActivityModal from "sections/accounts/activities/ActivityModal";
import { displaySuccessSnackbar } from "utils/displayError";

import WrapUpCaptureSection from "sections/activities/workspace/outcomeTab/WrapUpCaptureSection";
import NextStepsSection from "sections/activities/workspace/outcomeTab/NextStepsSection";

// ==============================|| ACTIVITY WRAP-UP TAB ||============================== //

/**
 * ActivityWrapUpTab
 *
 * @param {Object}   activity  - Full activity object from useGetActivity
 * @param {Function} onSave    - (fieldKey, newValue) => Promise<boolean>.
 *                               Persists Notes / Transcript via parent's
 *                               handleSaveField → updateActivity.
 * @param {Function} onUpdate  - Mutates the activity SWR cache. Called after
 *                               follow-up creation so the next_activities
 *                               in sequence_context refresh.
 * @param {boolean}  isLocked  - Activity is COMPLETED or CANCELLED →
 *                               disables editing / creation surfaces.
 */
export default function ActivityWrapUpTab({
  activity,
  onSave,
  onUpdate,
  isLocked = false,
}) {
  // ==============================|| FOLLOW-UP MODAL STATE ||============================== //

  const [activityModalOpen, setActivityModalOpen] = useState(false);
  const [activityModalType, setActivityModalType] = useState(null);
  const [convertFromCampaign, setConvertFromCampaign] = useState(false);

  /**
   * Triggered by NextStepsSection when the user clicks one of the quick-
   * create CTAs (Meeting / Call / Email / Task) or the campaign → DC
   * conversion CTA. The optional `options.convertFromCampaign` flag
   * routes the campaign-to-cycle attribution through `sourceActivityId`.
   */
  const handleCreateActivity = (activityType, options = {}) => {
    setActivityModalType(activityType);
    setConvertFromCampaign(Boolean(options.convertFromCampaign));
    setActivityModalOpen(true);
  };

  const handleActivityModalClose = () => {
    setActivityModalOpen(false);
    setActivityModalType(null);
    setConvertFromCampaign(false);
  };

  const handleActivitySuccess = () => {
    handleActivityModalClose();
    onUpdate?.();
    displaySuccessSnackbar("Follow-up activity created");
  };

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      <Stack spacing={3}>
        {/* SECTION 1 — Capture (notes + transcript + signals) */}
        <WrapUpCaptureSection
          activity={activity}
          onSave={onSave}
          isLocked={isLocked}
        />

        {/* SECTION 2 — Next steps */}
        <NextStepsSection
          activity={activity}
          onCreateActivity={handleCreateActivity}
          onUpdate={onUpdate}
          isLocked={isLocked}
        />
      </Stack>

      {/* Follow-up creation modal — triggered from NextStepsSection */}
      <ActivityModal
        open={activityModalOpen}
        onClose={handleActivityModalClose}
        activity={null}
        accountId={activity?.account}
        decisionStepId={activity?.decision_step || null}
        decisionCycleId={activity?.decision_cycle || null}
        defaultActivityType={activityModalType}
        previousActivityId={activity?.id}
        sourceActivityId={convertFromCampaign ? activity?.id : null}
        onSuccess={handleActivitySuccess}
      />
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

ActivityWrapUpTab.propTypes = {
  activity: PropTypes.object.isRequired,
  onSave: PropTypes.func.isRequired,
  onUpdate: PropTypes.func,
  isLocked: PropTypes.bool,
};
