// frontend/src/views/activities/workspace/index.jsx

"use client";

import { useParams, useRouter } from "next/navigation";

import { useEffect, useMemo } from "react";

// MUI
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons — section markers for the collapsible bands.
import ExperimentOutlined from "@ant-design/icons/ExperimentOutlined";
import FileTextOutlined from "@ant-design/icons/FileTextOutlined";
import RadarChartOutlined from "@ant-design/icons/RadarChartOutlined";
import RightCircleOutlined from "@ant-design/icons/RightCircleOutlined";

// Project imports
import WorkspaceLayout from "components/WorkspaceLayout";
import CollapsibleStrip from "components/display/CollapsibleStrip";
import { buildActivityBreadcrumbs } from "components/WorkspaceBreadcrumb";
import { useBreadcrumb } from "contexts/BreadcrumbContext";
import { useGetActivity, updateActivity } from "api/accounts/activities";
import { useGetLastExtractionRun } from "api/aiPipelines/lastRun";
import { useActivitySignalCounts } from "api/signals/signalCounts";
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
import ActivityOverviewTab from "sections/activities/workspace/ActivityOverviewTab";
import ActivityPreparationTab from "sections/activities/workspace/ActivityPreparationTab";
import ActivityNotesTab from "sections/activities/workspace/ActivityNotesTab";
import ActivitySignalsTab from "sections/activities/workspace/ActivitySignalsTab";
import ActivityNextStepsTab from "sections/activities/workspace/ActivityNextStepsTab";

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

  // Pipeline runner — owned here so pipelineState is accessible to header (F4)
  const pipelineRunner = usePipelineRunner({
    onSuccess: () => {
      mutateLastRun();
      mutateCounts();
    },
  });

  // Activity is locked when completed or cancelled — workspace becomes read-only
  const isLocked =
    activity?.status === "COMPLETED" || activity?.status === "CANCELLED";

  // Handle inline field save — blocked when activity is locked
  const handleSaveField = async (fieldKey, newValue) => {
    if (isLocked) return false;

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
      <WorkspaceLayout {...headerProps} loading={activityLoading}>
        <Stack spacing={2}>
          {/* Context — fixed, always visible (interim: the former Overview tab) */}
          <ActivityOverviewTab
            activity={activity}
            onSave={handleSaveField}
            isLocked={isLocked}
          />

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

          {/* Source — transcript / notes (interim: the former Notes tab) */}
          <CollapsibleStrip
            title="Source"
            icon={FileTextOutlined}
            defaultExpanded={false}
          >
            <ActivityNotesTab
              activity={activity}
              onSave={handleSaveField}
              isLocked={isLocked}
              pipelineRunner={pipelineRunner}
              lastRun={lastRun}
              latestRun={latestRun}
              runsByPipeline={runsByPipeline}
            />
          </CollapsibleStrip>

          {/* Signals — open when analysed */}
          <CollapsibleStrip
            title="Signals"
            icon={RadarChartOutlined}
            defaultExpanded={analyzed}
          >
            <ActivitySignalsTab
              activity={activity}
              isLocked={isLocked}
              mutateCounts={mutateCounts}
            />
          </CollapsibleStrip>

          {/* Next step — open when analysed */}
          <CollapsibleStrip
            title="Next step"
            icon={RightCircleOutlined}
            defaultExpanded={analyzed}
          >
            <ActivityNextStepsTab
              activity={activity}
              isLocked={isLocked}
              mutateCounts={mutateCounts}
            />
          </CollapsibleStrip>
        </Stack>
      </WorkspaceLayout>

      {/* Modals (Complete, Cancel, Reopen, Delete) */}
      {headerProps.modals}
    </>
  );
}
