// frontend/src/sections/activities/workspace/ActivityNextStepsTab.jsx

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useRef } from "react";
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

import CollapsibleStrip from "components/display/CollapsibleStrip";
import SignalsValidationList from "components/signals/SignalsValidationList";
import SignalDetailPanel from "components/signals/SignalDetailPanel";
import { SIGNAL_STATUS_PILL } from "components/signals/signalStatusPill";
import { getSignalTypeLabel } from "utils/signalTypes";
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import NextStepActivityLine, {
  getResolvedActivity,
} from "sections/activities/nextSteps/NextStepActivityLine";
import UpcomingActivitiesSection from "sections/activities/nextSteps/UpcomingActivitiesSection";
import { ACTIVITY_TYPES, ACTIVITY_TYPE_LABELS } from "api/accounts/activities";
import ClickablePill from "components/chips/ClickablePill";
import ActivityModal from "sections/accounts/activities/ActivityModal";
import EditNextStepContent from "sections/activities/workspace/EditNextStepContent";
import EditActivityContent from "sections/activities/workspace/EditActivityContent";
import NextStepValidateFlow from "sections/activities/nextSteps/NextStepValidateFlow";
import { NEXT_STEPS_BAND_QUERY, hasSuggestedNextSteps } from "utils/nextStepsBand";
// The band's own lock — the rule shared with the Signals band (5.11): only a
// CANCELLED activity locks, a COMPLETED one stays workable.
import { isActivitySignalsLocked } from "utils/activitySignalsLock";


// ==============================|| ACTIVITY NEXT STEPS TAB ||============================== //

// The "Next steps" band, in 4 parts (Sprint Next steps 5.x), as TWO sub-blocks
// (5.8f) with the Signals band's section header (CollapsibleStrip):
// "Next planned step" (part 1 + its "+ Add next step" pill) then "Suggested
// next steps" (parts 2-3):
//   1. the next planned step (activity.next_planned_step);
//   2. the next steps to validate and 3. the validated (resolved, with their
//      activity on the row's 3rd line) and rejected ones — the generic
//      SignalsValidationList, DC-only;
//   4. "+ Add next step" (5.8e): a pill of part 1's header → a row of the 7
//      ActivityType pills → the creation with that type.
// Every activity creation of the band opens in the coque (EditActivityContent,
// create mode — Sprint Next steps 5.8d); ActivityModal stays only for "Start
// Decision Cycle" (a campaign activity converted into a new cycle).
export default function ActivityNextStepsTab({ activity, mutateCounts }) {
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

  // Activity modal state (convert from signal OR manual add OR campaign conversion)
  // "Start Decision Cycle" (campaign → new cycle) — the one ActivityModal left.
  const [startCycleOpen, setStartCycleOpen] = useState(false);
  // "+ Add next step" — the row of type pills is shown; the "Next planned
  // step" sub-block is open (controlled: the pill unfolds it, 5.8g).
  const [typesOpen, setTypesOpen] = useState(false);
  const [plannedOpen, setPlannedOpen] = useState(true);

  // On a folded sub-block the pill unfolds it and shows the type row (which
  // lives in its body); on an open one it toggles the type row.
  const handleAddNextStep = useCallback(() => {
    if (!plannedOpen) {
      setPlannedOpen(true);
      setTypesOpen(true);
      return;
    }
    setTypesOpen((open) => !open);
  }, [plannedOpen]);

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

  // An activity creation in the coque (5.8d). From a next step: pre-filled
  // from it; on success the next step — now resolved — is read back (5.6),
  // Cancel returns to where the creation started. Otherwise (a manual next
  // step): the standard behaviour — the list refreshes and the coque closes.
  const openCreate = useCallback(
    ({ nextStep = null, activityType, onCancel } = {}) => {
      openDrawer(
        <EditActivityContent
          mode="create"
          accountId={accountId}
          decisionCycleId={activity?.decision_cycle || null}
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
        { title: "New activity" },
      );
    },
    [openDrawer, accountId, activity?.decision_cycle, showFromServer, mutateAll, mutateCounts, closeDrawer],
  );

  // The validation flow (5.6), in the coque: step 1 = Create or Link. Opened by
  // the row ✓ and the detail's Validate; Back returns to the detail. Create
  // opens the creation in the coque — its Cancel returns to step 1.
  const openFlow = useCallback(
    (signal) => {
      openDrawer(
        <NextStepValidateFlow
          nextStep={signal}
          onCreate={(ns) => openCreate({ nextStep: ns, onCancel: () => openFlow(ns) })}
          onBack={() => openDetail(signal)}
          onLinked={showFromServer}
        />,
        { title: "Validate next step" },
      );
    },
    [openDrawer, openCreate, openDetail, showFromServer],
  );


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

  const handleStartCycleSuccess = useCallback(() => {
    mutateAll();
    mutateCounts?.();
  }, [mutateAll, mutateCounts]);

  // Part 1's creation buttons: a type → the creation in the coque; "Start
  // Decision Cycle" (campaign → new cycle) → ActivityModal (debt: not migrated).
  const handleCreateActivity = useCallback(
    (activityType, options = {}) => {
      if (options.convertFromCampaign) {
        setStartCycleOpen(true);
        return;
      }
      openCreate({ activityType });
    },
    [openCreate],
  );

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      <Stack spacing={1.5}>
        {/* Sub-block 1 — the next planned step; "+ Add next step" on the right
            of its header (5.8e). The pill never folds the sub-block (its
            click / key stop at it). */}
        <Box data-testid="next-planned-step-block">
          {/* The pill sits in `meta` — CollapsibleStrip has no action slot
              (debt, traced at closure). */}
          <CollapsibleStrip
            title="Next planned step"
            expanded={plannedOpen}
            onExpandedChange={setPlannedOpen}
            meta={
              isLocked ? undefined : (
                <Box
                  component="span"
                  onClick={(e) => e.stopPropagation()}
                  onKeyDown={(e) => e.stopPropagation()}
                >
                  <ClickablePill
                    label="+ Add next step"
                    active
                    onClick={handleAddNextStep}
                  />
                </Box>
              )
            }
          >
            {!isLocked && typesOpen && (
              <Stack
                direction="row"
                spacing={0.75}
                flexWrap="wrap"
                useFlexGap
                sx={{ mb: 1.5 }}
                data-testid="add-next-step-types"
              >
                {Object.values(ACTIVITY_TYPES).map((type) => (
                  <ClickablePill
                    key={type}
                    label={ACTIVITY_TYPE_LABELS[type] || type}
                    onClick={() => {
                      setTypesOpen(false);
                      openCreate({ activityType: type });
                    }}
                  />
                ))}
              </Stack>
            )}
            <UpcomingActivitiesSection
              activity={activity}
              onCreateActivity={handleCreateActivity}
              isLocked={isLocked}
            />
          </CollapsibleStrip>
        </Box>

        {/* Sub-block 2 — the suggested next steps: to validate / validated /
            rejected. DC-only: extracted next-step suggestions are not proposed
            in a campaign context (activity without a decision_cycle). Mirrors
            the backend guard. One type only → no type-group header. */}
        {hasSuggestedNextSteps(activity) && (
          <Box data-testid="suggested-next-steps-block">
            <CollapsibleStrip title="Suggested next steps" defaultExpanded>
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
                />
              )}
            </CollapsibleStrip>
          </Box>
        )}
      </Stack>

      {/* "Start Decision Cycle" — the one ActivityModal left in the band (a
          campaign activity converted into a new cycle; debt: not migrated). */}
      {accountId && (
        <ActivityModal
          open={startCycleOpen}
          onClose={() => setStartCycleOpen(false)}
          activity={null}
          accountId={accountId}
          decisionStepId={activity?.decision_step || null}
          decisionCycleId={null}
          defaultActivityType="MEETING"
          previousActivityId={activity?.id}
          sourceActivityId={activity?.id}
          onSuccess={handleStartCycleSuccess}
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
