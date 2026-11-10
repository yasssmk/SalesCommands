// frontend/src/views/activities/workspace/index.jsx

"use client";

import { useParams, useRouter } from "next/navigation";

import { useEffect, useMemo, useState } from "react";

// MUI
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons — section markers for the collapsible bands.
import ExperimentOutlined from "@ant-design/icons/ExperimentOutlined";
import FileTextOutlined from "@ant-design/icons/FileTextOutlined";
import { SIGNAL_ICON } from "utils/signalTypes";

// Project imports
import WorkspaceHeader from "components/WorkspaceHeader";
import CollapsibleStrip from "components/display/CollapsibleStrip";
import { buildActivityBreadcrumbs } from "components/WorkspaceBreadcrumb";
import { useBreadcrumb } from "contexts/BreadcrumbContext";
import { useGetActivity, updateActivity } from "api/accounts/activities";
import { useGetLastExtractionRun } from "api/aiPipelines/lastRun";
import { useActivitySignalCounts } from "api/signals/signalCounts";
import useAggregatedSignals from "api/signals/aggregatedSignals";
import usePipelineRunner from "hooks/usePipelineRunner";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// Section imports
import useActivityHeaderProps from "sections/activities/workspace/ActivityHeader";
// getVisibleTabs is the single source of truth for the Preparation eligibility
// gate (activity_type ∈ CALL/MEETING/DEMO). Reused here as the eligibility
// oracle for the Preparation band — the tab selector itself is gone.
import { getVisibleTabs } from "sections/activities/workspace/ActivityTabs";
import ActivityContextSection from "sections/activities/workspace/ActivityContextSection";
import ActivityPreparationTab from "sections/activities/workspace/ActivityPreparationTab";
import ActivityNotesTab from "sections/activities/workspace/ActivityNotesTab";
import RunAIAnalysisButton from "sections/activities/workspace/RunAIAnalysisButton";
import ActivitySignalsTab, {
  ACTIVITY_FLAT_TYPES,
} from "sections/activities/workspace/ActivitySignalsTab";
import ActivityNextStepsBand from "sections/activities/workspace/ActivityNextStepsBand";
import SignalsHaloBox from "components/signals/SignalsHaloBox";
import {
  NEXT_STEPS_BAND_QUERY,
  hasSuggestedNextSteps,
  hasNextStepsBand,
  showsCampaignConversion,
} from "utils/nextStepsBand";
import { isActivitySignalsLocked, SOURCE_LOCKED_FIELDS } from "utils/activitySignalsLock";

// The Signals band halo reads the COMPLETE validable set (all 3 statuses).
const HALO_STATUSES = ["PENDING", "VALIDATED", "REJECTED"];

// ==============================|| ACTIVITY WORKSPACE PAGE ||============================== //

export default function ActivityWorkspacePage() {
  const params = useParams();
  const router = useRouter();

  const activityId = params?.id;

  const { activity, activityLoading, activityError, mutateActivity } =
    useGetActivity(activityId);

  // Last extraction run metadata. `lastRun` is the most recent SUCCESS|PARTIAL
  // run (backend-filtered) — its presence is the "activity has been analysed"
  // predicate that drives the spotlight (default-open) below.
  const { lastRun, latestRun, runsByPipeline, mutateLastRun } =
    useGetLastExtractionRun(activityId);

  // Signal counts for the header pending badge.
  const { counts, mutateCounts } = useActivitySignalCounts(activityId);

  // Signals band HALO (SIG-HALO). The halo must show even when the band is
  // COLLAPSED, so the count is fetched HERE (always mounted) — not inside
  // ActivitySignalsTab, which CollapsibleStrip unmounts while collapsed. The
  // by-activity /counts/ endpoint only covers 6 types (it excludes people /
  // constraint / competitor), so it would MIS-state "pending"; the halo instead
  // reads the COMPLETE aggregate — the same 8 validable types the validation
  // list shows, all 3 statuses — SWR-deduped with the list's own fetch.
  const { signals: bandSignals } = useAggregatedSignals({
    activityId,
    statuses: HALO_STATUSES,
    signalTypes: ACTIVITY_FLAT_TYPES,
    ordering: "date-desc",
    page: 1,
    pageSize: 100,
  });
  const bandPendingCount = useMemo(
    () => bandSignals.filter((s) => s.status === "PENDING").length,
    [bandSignals],
  );
  const bandTotalSignals = bandSignals.length;

  // Next steps band HALO + their share of the header counter (5.8f): fetched
  // HERE too (the band body unmounts while collapsed), with the band's own
  // query (utils/nextStepsBand — the same SWR key as its list). DC-only: outside
  // a decision cycle the suggestions are neither proposed nor counted.
  const { signals: nextStepSignals } = useAggregatedSignals({
    activityId,
    ...NEXT_STEPS_BAND_QUERY,
  });
  const hasSuggestions = hasSuggestedNextSteps(activity);
  const bandNextSteps = useMemo(
    () => (hasSuggestions ? nextStepSignals : []),
    [hasSuggestions, nextStepSignals],
  );
  const nextStepsPendingCount = useMemo(
    () => bandNextSteps.filter((s) => s.status === "PENDING").length,
    [bandNextSteps],
  );
  // 8f-1 (PO): « Start Decision Cycle » shown (showsCampaignConversion — the
  // CTA's OWN condition, one source) is an action to take: the band halo
  // reads it as one more item to validate — the SAME SignalsHaloBox, no new
  // style; the DC born, the CTA (and the highlight) go. The header counter
  // is unchanged (next steps only).
  const conversionToTake = showsCampaignConversion(activity) ? 1 : 0;

  // Pipeline runner — owned here so pipelineState is accessible to header (F4)
  const pipelineRunner = usePipelineRunner({
    onSuccess: () => {
      mutateLastRun();
      mutateCounts();
    },
  });

  // The Source band's Run AI wizard — opened by the band's header pill and by
  // the band body's "Try again" (lot 3 / 11, TD-302).
  const [sourceWizardOpen, setSourceWizardOpen] = useState(false);

  // Activity is locked when completed or cancelled — workspace becomes read-only
  const isLocked =
    activity?.status === "COMPLETED" || activity?.status === "CANCELLED";

  // Handle inline field save — blocked when activity is locked. The Source
  // band's transcript AND notes follow the signal bands' lock instead
  // (CANCELLED only — 5.12d, « Source / Notes » 1.5).
  const handleSaveField = async (fieldKey, newValue) => {
    const fieldLocked = SOURCE_LOCKED_FIELDS.includes(fieldKey)
      ? isActivitySignalsLocked(activity)
      : isLocked;
    if (fieldLocked) return false;

    try {
      const result = await updateActivity(activityId, { [fieldKey]: newValue });
      if (result.success) {
        displaySuccessSnackbar("Activity updated");
        mutateActivity();
        return true;
      } else {
        displayErrorSnackbar(result);
        return false;
      }
    } catch (err) {
      displayErrorSnackbar(err);
      return false;
    }
  };

  // ==============================|| HEADER PROPS (from hook) ||============================== //

  const headerProps = useActivityHeaderProps({
    activity,
    onSave: handleSaveField,
    onUpdate: mutateActivity,
    isLocked,
    pipelineState: pipelineRunner.state,
    lastRun,
    counts,
    // The "N to validate" badge reads the COMPLETE pending count (8 validable
    // types, same aggregate as the Signals list + halo) so header = list; the
    // /counts/ badge source only covered 6 types. Plus the PENDING next steps
    // (5.8f) — what remains to validate on the whole page.
    pendingCount: bandPendingCount + nextStepsPendingCount,
    // The neutral "N signals" fallback (shown when 0 pending) reads the same
    // 8-type aggregate total — never counts (which totals only 6 types).
    totalCount: bandTotalSignals,
  });

  // ==============================|| ADAPTIVE BODY STATE ||============================== //

  // Spotlight predicate: the activity is "analysed" once a successful (or
  // partial) extraction run exists. Drives which bands open by default.
  const analyzed = Boolean(lastRun);

  // Preparation band is conditional on activity_type — reuse the existing gate
  // (getVisibleTabs), never a hardcoded type set.
  const showPreparation = getVisibleTabs(activity?.activity_type).some(
    (tab) => tab.id === "preparation",
  );

  // ==============================|| CONTEXTUAL BREADCRUMB (pilot — L0) ||============================== //

  const { setCrumbs } = useBreadcrumb();

  const breadcrumbItems = useMemo(
    () =>
      activity
        ? buildActivityBreadcrumbs({
            accountId: activity.account,
            accountName: activity.account_detail?.company_name,
            cycleId: activity.decision_cycle || null,
            stepId: activity.decision_step || null,
            stepName: activity.decision_step_detail?.name || null,
            activityTitle: activity.title,
          })
        : [],
    [activity],
  );

  useEffect(() => {
    setCrumbs(breadcrumbItems);
  }, [breadcrumbItems, setCrumbs]);

  // Clear on unmount so the trail doesn't bleed onto the next page.
  useEffect(() => () => setCrumbs([]), [setCrumbs]);

  // ==============================|| RENDER - LOADING / ERROR ||============================== //

  if (activityLoading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="400px"
      >
        <CircularProgress />
      </Box>
    );
  }

  if (activityError) {
    const isTimeout = activityError?.response?.status === 408;
    const isNotFound = activityError?.response?.status === 404;

    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="400px"
      >
        <Stack spacing={2} alignItems="center">
          {isNotFound ? (
            <>
              <Typography color="error">Activity not found</Typography>
              <Button variant="outlined" onClick={() => router.back()}>
                Go Back
              </Button>
            </>
          ) : (
            <>
              <Typography color="text.secondary">
                {isTimeout ? "Request timed out" : "Failed to load activity"}
              </Typography>
              <Stack direction="row" spacing={2}>
                <Button variant="contained" onClick={() => mutateActivity()}>
                  Retry
                </Button>
                <Button variant="outlined" onClick={() => router.back()}>
                  Go Back
                </Button>
              </Stack>
            </>
          )}
        </Stack>
      </Box>
    );
  }

  if (!activity) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="400px"
      >
        <CircularProgress />
      </Box>
    );
  }

  // ==============================|| RENDER - STACKED BODY (no tabs) ||============================== //

  return (
    <>
      {/* HEADER-1: the new shared WorkspaceHeader (Activity is the first surface
          migrated off WorkspaceLayout). The body cards are siblings of the header
          (no outer MainCard) so their left edge lines up with the header content
          — a single vertical column title → sections (HEADER-2 #4). */}
      <WorkspaceHeader {...headerProps} />
      <Stack spacing={2}>
          {/* Context — fixed, always visible; read-only aphoriQ display (S2a) */}
          <ActivityContextSection activity={activity} />

          {/* Preparation — conditional on activity_type; open when NOT analysed */}
          {showPreparation && (
            <CollapsibleStrip
              title="Preparation"
              icon={ExperimentOutlined}
              defaultExpanded={!analyzed}
            >
              <ActivityPreparationTab activity={activity} isLocked={isLocked} />
            </CollapsibleStrip>
          )}

          {/* Source — transcript / notes (interim: the former Notes tab). Its
              Run AI is a pill in the band header, as the other bands' actions
              (the Next steps band's « + Add next step », ActivityNextStepsBand:
              ClickablePill in `meta`, clicks kept off the header toggle) —
              lot 3 / 11, TD-302. Same lock (CANCELLED only) and wizard. */}
          <CollapsibleStrip
            title="Source"
            icon={FileTextOutlined}
            defaultExpanded={false}
            meta={
              <Box
                component="span"
                onClick={(e) => e.stopPropagation()}
                onKeyDown={(e) => e.stopPropagation()}
              >
                <RunAIAnalysisButton
                  activity={activity}
                  pipelineRunner={pipelineRunner}
                  lastRun={lastRun}
                  runsByPipeline={runsByPipeline}
                  open={sourceWizardOpen}
                  onOpenChange={setSourceWizardOpen}
                />
              </Box>
            }
          >
            <ActivityNotesTab
              activity={activity}
              onSave={handleSaveField}
              pipelineRunner={pipelineRunner}
              lastRun={lastRun}
              latestRun={latestRun}
              onOpenWizard={() => setSourceWizardOpen(true)}
            />
          </CollapsibleStrip>

          {/* Signals — open when analysed. Wrapped in the validation-state
              halo (SIG-HALO): amber when signals remain to validate, primary
              when all are processed, none when there are no signals. The halo
              sits on the wrapper so it shows even while the band is collapsed. */}
          <SignalsHaloBox
            pendingCount={bandPendingCount}
            totalSignals={bandTotalSignals}
          >
            <CollapsibleStrip
              title="Signals"
              icon={SIGNAL_ICON}
              defaultExpanded={analyzed}
            >
              {/* The band owns its lock (COMPLETED stays workable, 5.11). */}
              <ActivitySignalsTab
                activity={activity}
                mutateCounts={mutateCounts}
              />
            </CollapsibleStrip>
          </SignalsHaloBox>

          {/* Next steps — open when analysed. The same validation-state halo
              as the Signals band (SignalsHaloBox), on its own next steps.
              Rendered only when it has something to show (5.12 B: a DC
              activity, or the campaign conversion) — the Preparation model. */}
          {hasNextStepsBand(activity) && (
            <SignalsHaloBox
              pendingCount={nextStepsPendingCount + conversionToTake}
              totalSignals={bandNextSteps.length + conversionToTake}
              data-testid="next-steps-halo"
            >
              <ActivityNextStepsBand
                activity={activity}
                defaultExpanded={analyzed}
                mutateCounts={mutateCounts}
                pipelineRunner={pipelineRunner}
                lastRun={lastRun}
                runsByPipeline={runsByPipeline}
              />
            </SignalsHaloBox>
          )}
        </Stack>

      {/* Modals (Delete) */}
      {headerProps.modals}
    </>
  );
}
