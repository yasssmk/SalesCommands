"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";

// MUI
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Project imports
import WorkspaceLayout from "components/WorkspaceLayout";
import { buildDCWorkspaceBreadcrumbs } from "components/WorkspaceBreadcrumb";
import { useGetDecisionCycle } from "api/accounts/decisionCycles";

// Section imports
import useDCWorkspaceHeaderProps from "sections/accounts/dc-workspace/DCWorkspaceHeader";
import {
  DC_WORKSPACE_TABS,
  DEFAULT_TAB,
} from "sections/accounts/dc-workspace/DCWorkspaceTabs";
import DCTimelineTab from "sections/accounts/dc-workspace/DCTimelineTab";

// ==============================|| DC WORKSPACE PAGE ||============================== //

export default function DCWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();

  const accountId = params?.id;
  const cycleId = params?.cycleId;
  const currentTab = searchParams.get("tab") || DEFAULT_TAB;

  const { cycle, cycleLoading, cycleError, mutateCycle } =
    useGetDecisionCycle(cycleId);

  // Handle tab change via URL
  const handleTabChange = (newTab) => {
    const p = new URLSearchParams(searchParams.toString());
    p.set("tab", newTab);
    router.push(`?${p.toString()}`, { scroll: false });
  };

  // ==============================|| HEADER PROPS ||============================== //

  const headerProps = useDCWorkspaceHeaderProps({
    cycle,
    accountId,
    onUpdate: mutateCycle,
  });

  // ==============================|| TAB CONTENT ||============================== //

  const renderTabContent = () => {
    switch (currentTab) {
      case "timeline":
        return (
          <DCTimelineTab
            cycle={cycle}
            accountId={accountId}
            onRefresh={mutateCycle}
          />
        );
      case "people":
      case "products":
      case "strategic":
      case "signals":
        return (
          <Box sx={{ p: 3, textAlign: "center" }}>
            <Typography color="text.secondary">
              This tab is under construction.
            </Typography>
          </Box>
        );
      default:
        return (
          <DCTimelineTab
            cycle={cycle}
            accountId={accountId}
            onRefresh={mutateCycle}
          />
        );
    }
  };

  // ==============================|| LOADING ||============================== //

  if (cycleLoading) {
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

  // ==============================|| ERROR ||============================== //

  if (cycleError) {
    const isNotFound = cycleError?.response?.status === 404;

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
              <Typography color="error">Decision cycle not found</Typography>
              <Button variant="outlined" onClick={() => router.back()}>
                Go Back
              </Button>
            </>
          ) : (
            <>
              <Typography color="text.secondary">
                Failed to load decision cycle
              </Typography>
              <Stack direction="row" spacing={2}>
                <Button variant="contained" onClick={() => mutateCycle()}>
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

  // ==============================|| NO DATA ||============================== //

  if (!cycle) {
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

  // ==============================|| BREADCRUMBS ||============================== //

  const breadcrumbItems = buildDCWorkspaceBreadcrumbs({
    accountId,
    accountName: cycle.account_name,
    cycleName: cycle.name,
  });

  // ==============================|| RENDER ||============================== //

  return (
    <>
      <WorkspaceLayout
        breadcrumbs={breadcrumbItems}
        {...headerProps}
        tabs={DC_WORKSPACE_TABS}
        activeTab={currentTab}
        onTabChange={handleTabChange}
        loading={cycleLoading}
      >
        {renderTabContent()}
      </WorkspaceLayout>

      {headerProps.modals}
    </>
  );
}
