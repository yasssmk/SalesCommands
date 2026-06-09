// frontend/src/views/activities/workspace/index.jsx

"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";

import { useMemo } from "react";

// MUI
import Badge from "@mui/material/Badge";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Project imports
import WorkspaceLayout from "components/WorkspaceLayout";
import { buildActivityBreadcrumbs } from "components/WorkspaceBreadcrumb";
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
import {
  ACTIVITY_TABS,
  DEFAULT_TAB,
} from "sections/activities/workspace/ActivityTabs";
import ActivityOverviewTab from "sections/activities/workspace/ActivityOverviewTab";
import ActivityPreparationTab from "sections/activities/workspace/ActivityPreparationTab";
import ActivityNotesTab from "sections/activities/workspace/ActivityNotesTab";
import ActivitySignalsTab from "sections/activities/workspace/ActivitySignalsTab";
import ActivityNextStepsTab from "sections/activities/workspace/ActivityNextStepsTab";

// ==============================|| ACTIVITY WORKSPACE PAGE ||============================== //

export default function ActivityWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();

  const activityId = params?.id;
  const currentTab = searchParams.get("tab") || DEFAULT_TAB;

  const { activity, activityLoading, activityError, mutateActivity } =
    useGetActivity(activityId);

  // Last extraction run metadata (per-pipeline breakdown for wizard Step 1)
  const { lastRun, latestRun, runsByPipeline, mutateLastRun } =
    useGetLastExtractionRun(activityId);

  // Signal counts for header pending badge
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

  // Handle tab change via URL
  const handleTabChange = (newTab) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", newTab);
    router.push(`?${params.toString()}`, { scroll: false });
  };

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

  const handlePendingClick = () => {
    handleTabChange("signals");
  };

  const headerProps = useActivityHeaderProps({
    activity,
    onSave: handleSaveField,
    onUpdate: mutateActivity,
    isLocked,
    pipelineState: pipelineRunner.state,
    lastRun,
    counts,
    onPendingClick: handlePendingClick,
  });

  // ==============================|| TAB BADGES ||============================== //

  const signalsPending = counts?.by_type
    ? (counts.by_type.pain?.pending || 0) +
      (counts.by_type.objective?.pending || 0) +
      (counts.by_type.impact?.pending || 0) +
      (counts.by_type.tech_stack?.pending || 0) +
      (counts.by_type.blocker?.pending || 0)
    : 0;

  const nextStepsPending = counts?.by_type?.next_step?.pending || 0;

  const tabsWithBadges = useMemo(() => {
    return ACTIVITY_TABS.map((tab) => {
      let badgeCount = 0;
      if (tab.id === "signals") badgeCount = signalsPending;
      if (tab.id === "next-steps") badgeCount = nextStepsPending;

      if (badgeCount > 0) {
        return {
          ...tab,
          label: (
            <Badge badgeContent={badgeCount} color="warning" max={99}>
              {tab.label}
            </Badge>
          ),
        };
      }
      return tab;
    });
  }, [signalsPending, nextStepsPending]);

  // ==============================|| RENDER - ERROR ||============================== //

  // Render tab content
  const renderTabContent = () => {
    switch (currentTab) {
      case "overview":
        return (
          <ActivityOverviewTab
            activity={activity}
            onSave={handleSaveField}
            isLocked={isLocked}
          />
        );
      case "preparation":
        return (
          <ActivityPreparationTab activity={activity} isLocked={isLocked} />
        );
      case "notes":
        return (
          <ActivityNotesTab
            activity={activity}
            onSave={handleSaveField}
            isLocked={isLocked}
            pipelineRunner={pipelineRunner}
            lastRun={lastRun}
            latestRun={latestRun}
            runsByPipeline={runsByPipeline}
          />
        );
      case "signals":
        return (
          <ActivitySignalsTab
            activity={activity}
            isLocked={isLocked}
            mutateCounts={mutateCounts}
          />
        );
      case "next-steps":
        return (
          <ActivityNextStepsTab
            activity={activity}
            isLocked={isLocked}
            mutateCounts={mutateCounts}
          />
        );
      default:
        return (
          <ActivityOverviewTab
            activity={activity}
            onSave={handleSaveField}
            isLocked={isLocked}
          />
        );
    }
  };

  // Loading state
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

  // Error state
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

  // No data state (should not happen if no error, but safety check)
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

  // Build breadcrumb items
  const breadcrumbItems = activity
    ? buildActivityBreadcrumbs({
        accountId: activity.account,
        accountName: activity.account_detail?.company_name,
        cycleId: activity.decision_cycle || null,
        stepId: activity.decision_step || null,
        stepName: activity.decision_step_detail?.name || null,
        activityTitle: activity.title,
      })
    : [];

  return (
    <>
      <WorkspaceLayout
        breadcrumbs={breadcrumbItems}
        {...headerProps}
        tabs={tabsWithBadges}
        activeTab={currentTab}
        onTabChange={handleTabChange}
        loading={activityLoading}
      >
        {renderTabContent()}
      </WorkspaceLayout>

      {/* Modals (Complete, Cancel, Reopen, Delete) */}
      {headerProps.modals}
    </>
  );
}
