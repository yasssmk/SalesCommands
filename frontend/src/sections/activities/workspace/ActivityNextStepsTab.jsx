// frontend/src/sections/activities/workspace/ActivityNextStepsTab.jsx

"use client";

import PropTypes from "prop-types";
import { useCallback, useRef } from "react";
import { useRouter } from "next/navigation";

// MUI
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

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
import CampaignConversionCta from "sections/activities/nextSteps/CampaignConversionCta";
import RunAIAnalysisButton, {
  RUN_AI_TRIGGER_VARIANTS,
} from "sections/activities/workspace/RunAIAnalysisButton";
import { formatShortDate } from "components/signals/SignalLine";
import { ACTIVITY_TYPES, ACTIVITY_TYPE_LABELS } from "api/accounts/activities";
import ClickablePill from "components/chips/ClickablePill";
import EditNextStepContent from "sections/activities/workspace/EditNextStepContent";
import EditActivityContent from "sections/activities/workspace/EditActivityContent";
import NextStepValidateFlow from "sections/activities/nextSteps/NextStepValidateFlow";
import {
  NEXT_STEPS_BAND_QUERY,
  hasSuggestedNextSteps,
  nextStepsCycleId,
  showsCampaignConversion,
} from "utils/nextStepsBand";
// The band's own lock — the rule shared with the Signals band (5.11): only a
// CANCELLED activity locks, a COMPLETED one stays workable.
import { isActivitySignalsLocked } from "utils/activitySignalsLock";


// The extraction of the band checks the next steps only (5.12 B, PO).
const NEXT_STEPS_ONLY_OBJECTIVES = { qualification: false, nextSteps: true };

// ==============================|| ACTIVITY NEXT STEPS TAB ||============================== //

// The "Next steps" band (Sprint Next steps 5.x), top to bottom (5.12 B):
//   1. the campaign → Decision Cycle conversion block, when it applies
//      (showsCampaignConversion — a campaign activity, no DC born yet: never
//      with « + Add next step »);
//   2. the suggested next steps — to validate, validated (resolved, with their
//      activity on the row's 3rd line), rejected: the generic
//      SignalsValidationList — a DC activity, or a SUCCESSFUL campaign
//      activity (hasSuggestedNextSteps, 5.14b); the latter shows with the
//      conversion block until a DC is born from it;
//   3. in the list's empty state (EmptyState `action`, 5.12e), the AI action:
//      only without any next step — the shared Run AI action as a pill
//      (RunAIAnalysisButton, the Source's label, the page's pipelineRunner),
//      next steps only pre-checked, while the NEXT STEPS extraction never
//      ran; « AI already ran · <date> » after;
//   « + Add next step » (5.8e) sits on the right of the BAND's title
//   (ActivityNextStepsBand, 5.12e): it opens the row of the 7 ActivityType
//   pills, at the TOP of this body (typesOpen) → the creation with that type
//   — only with a cycle to create in (nextStepsCycleId).
// The cycle of the band's creations (5.14b): the activity's own, else the one
// born from the campaign activity; with none (a campaign activity, no DC born
// yet), the row ✓'s Create converts — the creation drawer in conversion mode
// (5.13), pre-filled from the next step, a NEW cycle inline.
// The next planned step is shown in Context (5.12 A-bis), not here. The page
// renders the band only when it has something to show (hasNextStepsBand).
// Every activity creation of the band opens in the coque (EditActivityContent,
// create mode — Sprint Next steps 5.8d), "Start Decision Cycle" included
// (5.13: its conversion mode — a NEW cycle only). No modal any more.
export default function ActivityNextStepsTab({
  activity,
  mutateCounts,
  pipelineRunner,
  lastRun,
  runsByPipeline,
  typesOpen = false,
  onTypesOpenChange,
}) {
  const router = useRouter();
  // The single lock predicate of the band (parts 1-4, row actions, drawer).
  const isLocked = isActivitySignalsLocked(activity);
  const activityId = activity?.id;
  const accountId = activity?.account;

  // Data
  const {
    signals: nextStepSignals,
    loading,
    error,
    mutate: mutateAll,
  } = useAggregatedSignals({ activityId, ...NEXT_STEPS_BAND_QUERY });

  // The single workspace drawer coque: the next step detail is injected there,
  // as the detail of every other signal type (ActivitySignalsTab).
  const { openDrawer, closeDrawer } = useWorkspaceDrawer();

  const hasNextSteps = hasSuggestedNextSteps(activity);
  const cycleId = nextStepsCycleId(activity);
  // The AI action (5.12c): only without any next step (the band's own list —
  // no new query), and once that list is known (loaded, no error).
  const nextStepsRun = runsByPipeline?.NEXT_STEPS || null;
  const showsAIAction =
    Boolean(pipelineRunner) && !loading && !error && nextStepSignals.length === 0;
  // 3. The AI action, IN the list's empty state (the shared EmptyState's
  // `action`: centred, under its text — 5.12e): the NEXT STEPS extraction
  // never ran → the Source band's Run AI action as a pill (same label,
  // predicate, wizard, runner, "Analyzing…"), next steps only; it already
  // ran → « AI already ran · <date> », no action.
  const aiAction = showsAIAction ? (
    <Box data-testid="next-steps-extraction">
      {nextStepsRun ? (
        <Typography variant="caption" color="text.secondary">
          {`AI already ran · ${formatShortDate(nextStepsRun.last_run_at)}`}
        </Typography>
      ) : (
        <RunAIAnalysisButton
          activity={activity}
          pipelineRunner={pipelineRunner}
          lastRun={lastRun}
          runsByPipeline={runsByPipeline}
          defaultObjectives={NEXT_STEPS_ONLY_OBJECTIVES}
          variant={RUN_AI_TRIGGER_VARIANTS.PILL}
        />
      )}
    </Box>
  ) : null;

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

  // An activity creation in the coque (5.8d), in the band's cycle (cycleId).
  // From a next step: pre-filled from it; on success the next step — now
  // resolved — is read back (5.6), Cancel returns to where the creation
  // started. Without a cycle (5.14b: a campaign activity, no DC born yet) it
  // converts: the conversion mode of 5.13, from this activity, a NEW cycle
  // inline. Otherwise (a manual next step): the standard behaviour — the list
  // refreshes and the coque closes.
  const openCreate = useCallback(
    ({ nextStep = null, activityType, onCancel } = {}) => {
      const converts = !cycleId;
      openDrawer(
        <EditActivityContent
          mode="create"
          accountId={accountId}
          decisionCycleId={cycleId}
          conversion={converts}
          sourceActivityId={converts ? activityId : undefined}
          initialContacts={converts ? activity?.contacts_detail || [] : []}
          nextStep={nextStep}
          activityType={activityType}
          onCreated={() => {
            if (nextStep) {
              showFromServer(nextStep);
            } else {
              mutateAll();
              mutateCounts?.();
              closeDrawer();
            }
          }}
          onCancel={onCancel}
        />,
        { title: converts ? "Start Decision Cycle" : "New activity" },
      );
    },
    [openDrawer, accountId, cycleId, activityId, activity?.contacts_detail, showFromServer, mutateAll, mutateCounts, closeDrawer],
  );

  // The validation flow (5.6), in the coque: step 1 = Create or Link. Opened by
  // the row ✓ and the detail's Validate; Back returns to the detail. Create
  // opens the creation in the coque — its Cancel returns to step 1.
  const openFlow = useCallback(
    (signal) => {
      openDrawer(
        <NextStepValidateFlow
          nextStep={signal}
          hasCycle={Boolean(cycleId)}
          onCreate={(ns) => openCreate({ nextStep: ns, onCancel: () => openFlow(ns) })}
          onBack={() => openDetail(signal)}
          onLinked={showFromServer}
        />,
        { title: "Validate next step" },
      );
    },
    [openDrawer, cycleId, openCreate, openDetail, showFromServer],
  );


  // Edit in the coque (EditNextStepContent), then back to the detail —
  // the chassis edit of every other signal type.
  const handleEdit = useCallback(
    (signal) => {
      openDrawer(
        <EditNextStepContent
          nextStep={signal}
          decisionCycleId={cycleId}
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
    [openDrawer, cycleId, mutateAll, mutateCounts, openDetail],
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

  // "Start Decision Cycle" (5.13): the creation drawer in conversion mode — a
  // MEETING from this campaign activity (source_activity_id), a NEW cycle
  // created inline, the activity's contacts pre-filled. On success the
  // standard revalidation re-reads this activity: the born DC hides the CTA
  // and shows in Context.
  const openStartCycle = useCallback(() => {
    openDrawer(
      <EditActivityContent
        mode="create"
        conversion
        accountId={accountId}
        activityType="MEETING"
        sourceActivityId={activityId}
        initialContacts={activity?.contacts_detail || []}
        onCreated={() => {
          mutateAll();
          mutateCounts?.();
          closeDrawer();
        }}
      />,
      { title: "Start Decision Cycle" },
    );
  }, [openDrawer, accountId, activityId, activity?.contacts_detail, mutateAll, mutateCounts, closeDrawer]);


  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      <Stack spacing={1.5} data-testid="next-steps-band">
        {/* « + Add next step »'s row of the 7 ActivityType pills, at the TOP
            of the band (its pill is in the band header, 5.12e). Only with a
            cycle to create in. */}
        {cycleId && !isLocked && typesOpen && (
          <Stack
            direction="row"
            spacing={0.75}
            flexWrap="wrap"
            useFlexGap
            data-testid="add-next-step-types"
          >
            {Object.values(ACTIVITY_TYPES).map((type) => (
              <ClickablePill
                key={type}
                label={ACTIVITY_TYPE_LABELS[type] || type}
                onClick={() => {
                  onTypesOpenChange?.(false);
                  openCreate({ activityType: type });
                }}
              />
            ))}
          </Stack>
        )}

        {/* 1. The campaign → Decision Cycle conversion (when it applies):
            "Start Decision Cycle" opens the creation drawer in conversion
            mode (5.13). */}
        {showsCampaignConversion(activity) && (
          <CampaignConversionCta onStartCycle={openStartCycle} />
        )}

        {/* 2. The suggested next steps: to validate / validated / rejected,
            directly under the band — as the Signals band's list (5.12c: no
            sub-level title). A DC activity or a SUCCESSFUL campaign activity
            (hasSuggestedNextSteps — mirrors the backend predicate). One type
            only → no type-group header. */}
        {hasNextSteps && (
          <Box data-testid="suggested-next-steps-block">
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
                showTypeHeaders={false}
                emptyMessage="No next-step suggestions for this activity"
                emptyAction={aiAction}
              />
            )}
          </Box>
        )}

      </Stack>
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
    campaign_detail: PropTypes.object,
    transcript: PropTypes.string,
    outcome_notes: PropTypes.string,
  }),
  mutateCounts: PropTypes.func,
  /** « + Add next step »'s type row is shown (the band header's pill, 5.12e). */
  typesOpen: PropTypes.bool,
  /** Fired with the next type-row state (closed on a type pick). */
  onTypesOpenChange: PropTypes.func,
  /** The page's pipeline runner (usePipelineRunner) — the extraction. */
  pipelineRunner: PropTypes.object,
  lastRun: PropTypes.object,
  runsByPipeline: PropTypes.object,
};
