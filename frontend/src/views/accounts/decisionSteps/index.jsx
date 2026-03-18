// frontend/src/views/accounts/decisionSteps/index.jsx
/**
 * Decision Step Workspace Page
 *
 * Uses WorkspaceLayout with useDecisionStepHeaderProps hook.
 * Same pattern as Account and Activity workspace pages.
 */

"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";

// MUI
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Project imports
import WorkspaceLayout from "components/WorkspaceLayout";
import { useGetDecisionStep } from "api/accounts/decisionCycles";
import { useGetAccount } from "api/admin/accounts";
import { buildStepBreadcrumbs } from "components/WorkspaceBreadcrumb";

// Header hook + Tab config
import useDecisionStepHeaderProps from "sections/accounts/decision-cycles/Decision-steps/DecisionStepHeader";
import {
  DECISION_STEP_TABS,
  DEFAULT_TAB,
} from "sections/accounts/decision-cycles/Decision-steps/DecisionStepTabs";

// Tab content components
import DecisionStepOverviewTab from "sections/accounts/decision-cycles/Decision-steps/DecisionStepOverviewTab";
import DecisionStepActivitiesTab from "sections/accounts/decision-cycles/Decision-steps/DecisionStepActivitiesTab";
import DecisionStepContactsTab from "sections/accounts/decision-cycles/Decision-steps/DecisionStepContactsTab";
import DecisionStepSignalsTab from "sections/accounts/decision-cycles/Decision-steps/DecisionStepSignalsTab";
import DecisionStepAIPrepTab from "sections/accounts/decision-cycles/Decision-steps/DecisionStepAIPrepTab";

// ==============================|| DECISION STEP WORKSPACE PAGE ||============================== //

export default function DecisionStepWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();

  // Extract route params
  const accountId = params?.id;
  const stepId = params?.stepId;
  const currentTab = searchParams.get("tab") || DEFAULT_TAB;

  // Fetch data
  const { step, stepLoading, stepError, mutateStep } =
    useGetDecisionStep(stepId);
  const { account, accountLoading } = useGetAccount(accountId);

  const isLoading = stepLoading || accountLoading;

  // ==============================|| HANDLERS ||============================== //

  const handleTabChange = (newTab) => {
    const urlParams = new URLSearchParams(searchParams.toString());
    urlParams.set("tab", newTab);
    router.push(`?${urlParams.toString()}`, { scroll: false });
  };

  // Derive cycle ID from step data
  const cycleId = step?.cycle_id || step?.cycle?.id || step?.cycle || null;

  const handleAccountClick = () => {
    if (accountId) {
      const cycleParam = cycleId ? `&cycle=${cycleId}` : "";
      router.push(`/accounts/${accountId}?tab=decision-cycle${cycleParam}`);
    }
  };

  const handleCycleClick = () => {
    if (accountId) {
      const cycleParam = cycleId ? `&cycle=${cycleId}` : "";
      router.push(`/accounts/${accountId}?tab=decision-cycle${cycleParam}`);
    }
  };

  // ==============================|| ERROR STATE ||============================== //

  if (!isLoading && (stepError || !step)) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="400px"
      >
        <Stack spacing={2} alignItems="center">
          <Typography color="error">Decision step not found</Typography>
          <Button variant="outlined" onClick={() => router.back()}>
            Go Back
          </Button>
        </Stack>
      </Box>
    );
  }

  // ==============================|| HEADER PROPS (from hook) ||============================== //

  const headerProps = useDecisionStepHeaderProps({
    step,
    account,
    onAccountClick: handleAccountClick,
    onCycleClick: handleCycleClick,
  });

  // Breadcrumbs
  const breadcrumbItems = step
    ? buildStepBreadcrumbs({
        accountId,
        accountName: account?.company_name,
        cycleId,
        cycleName: step?.cycle_detail?.name || step?.cycle_name || null,
        stepName: headerProps.title,
      })
    : [];

  // ==============================|| TAB CONTENT ||============================== //

  const renderTabContent = () => {
    switch (currentTab) {
      case "overview":
        return (
          <DecisionStepOverviewTab
            step={step}
            account={account}
            onUpdate={mutateStep}
          />
        );
      case "activities":
        return (
          <DecisionStepActivitiesTab
            step={step}
            accountId={accountId}
            onUpdate={mutateStep}
          />
        );
      case "contacts":
        return <DecisionStepContactsTab step={step} accountId={accountId} />;
      case "signals":
        return <DecisionStepSignalsTab step={step} />;
      case "ai-prep":
        return <DecisionStepAIPrepTab step={step} />;
      default:
        return (
          <DecisionStepOverviewTab
            step={step}
            account={account}
            onUpdate={mutateStep}
          />
        );
    }
  };

  // ==============================|| RENDER ||============================== //

  return (
    <>
      <WorkspaceLayout
        breadcrumbs={breadcrumbItems}
        {...headerProps}
        tabs={DECISION_STEP_TABS}
        activeTab={currentTab}
        onTabChange={handleTabChange}
        loading={isLoading}
      >
        {renderTabContent()}
      </WorkspaceLayout>
      {headerProps.modals}
    </>
  );
}
