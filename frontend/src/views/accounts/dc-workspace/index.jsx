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
import { useGetDecisionCyclesByAccount } from "api/accounts/decisionCycles";

// Section imports
import useDCWorkspaceHeaderProps from "sections/accounts/dc-workspace/DCWorkspaceHeader";
import {
  DC_WORKSPACE_TABS,
  DEFAULT_TAB,
} from "sections/accounts/dc-workspace/DCWorkspaceTabs";
import TimelineTab from "sections/accounts/dc-workspace/TimelineTab";
import SignalsTab from "sections/accounts/dc-workspace/SignalsTab";
import QualificationGroupedView from "sections/accounts/signals/QualificationGroupedView";
import ProductsTab from "sections/accounts/dc-workspace/ProductsTab";
import PeopleTab from "sections/accounts/dc-workspace/PeopleTab";
import StrategicTab from "sections/accounts/dc-workspace/StrategicTab";
import OverviewTab from "sections/accounts/dc-workspace/OverviewTab";

// ==============================|| DC WORKSPACE PAGE ||============================== //

export default function DCWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();

  const accountId = params?.id;
  const cycleId = params?.cycleId;
  const currentTab = searchParams.get("tab") || DEFAULT_TAB;

  const { cycles, cyclesLoading, cyclesError, mutateCycles } =
    useGetDecisionCyclesByAccount(accountId);
  const cycle = cycles?.find((c) => c.id === cycleId) || null;

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
    onUpdate: mutateCycles,
  });

  // ==============================|| TAB CONTENT ||============================== //

  const renderTabContent = () => {
    switch (currentTab) {
      case "overview":
        return <OverviewTab cycleId={cycleId} />;
      case "timeline":
        return (
          <TimelineTab
            cycle={cycle}
            accountId={accountId}
            onRefresh={mutateCycles}
          />
        );
      case "signals":
        return <SignalsTab cycleId={cycleId} accountId={accountId} />;
      case "qualification":
        return (
          <QualificationGroupedView
            surface="dc"
            accountId={accountId}
            decisionCycleId={cycleId}
          />
        );
      case "products":
        return <ProductsTab cycleId={cycleId} cycle={cycle} />;
      case "people":
        return <PeopleTab cycleId={cycleId} accountId={accountId} />;
      case "strategic":
        return (
          <StrategicTab
            cycleId={cycleId}
            accountId={accountId}
            cycle={cycle}
          />
        );
      default:
        return (
          <TimelineTab
            cycle={cycle}
            accountId={accountId}
            onRefresh={mutateCycles}
          />
        );
    }
  };

  // ==============================|| LOADING ||============================== //

  if (cyclesLoading) {
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

  if (cyclesError) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="400px"
      >
        <Stack spacing={2} alignItems="center">
          <Typography color="text.secondary">
            Failed to load decision cycle
          </Typography>
          <Stack direction="row" spacing={2}>
            <Button variant="contained" onClick={() => mutateCycles()}>
              Retry
            </Button>
            <Button variant="outlined" onClick={() => router.back()}>
              Go Back
            </Button>
          </Stack>
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
        <Stack spacing={2} alignItems="center">
          <Typography color="error">Decision cycle not found</Typography>
          <Button variant="outlined" onClick={() => router.back()}>
            Go Back
          </Button>
        </Stack>
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
        loading={cyclesLoading}
      >
        {renderTabContent()}
      </WorkspaceLayout>

      {headerProps.modals}
    </>
  );
}
