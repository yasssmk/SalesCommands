// frontend/src/views/accounts/decisionSteps/index.jsx

'use client';

import { useParams, useRouter, useSearchParams } from 'next/navigation';

// MUI
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// Project imports
import MainCard from 'components/MainCard';
import { useGetDecisionStep, updateDecisionStep } from 'api/accounts/decisionCycles';
import { useGetAccount } from 'api/admin/accounts';
import { displaySuccessSnackbar, displayErrorSnackbar } from 'utils/displayError';

// Section imports
import DecisionStepHeader from 'sections/accounts/decision-cycles/Decision-steps/DecisionStepHeader';
import DecisionStepTabs, { DEFAULT_TAB } from 'sections/accounts/decision-cycles/Decision-steps/DecisionStepTabs';
import DecisionStepOverviewTab from 'sections/accounts/decision-cycles/Decision-steps/DecisionStepOverviewTab';
import DecisionStepActivitiesTab from 'sections/accounts/decision-cycles/Decision-steps/DecisionStepActivitiesTab';
import DecisionStepContactsTab from 'sections/accounts/decision-cycles/Decision-steps/DecisionStepContactsTab';
import DecisionStepSignalsTab from 'sections/accounts/decision-cycles/Decision-steps/DecisionStepSignalsTab';
import DecisionStepAIPrepTab from 'sections/accounts/decision-cycles/Decision-steps/DecisionStepAIPrepTab';

// Icons
import { ArrowLeftOutlined } from '@ant-design/icons';

// ==============================|| DECISION STEP WORKSPACE PAGE ||============================== //

export default function DecisionStepWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();

  // Extract route params
  const accountId = params?.id;
  const stepId = params?.stepId;
  const currentTab = searchParams.get('tab') || DEFAULT_TAB;

  // Fetch step data
  const { step, stepLoading, stepError, mutateStep } = useGetDecisionStep(stepId);

  // Fetch account data for breadcrumb/context
  const { account, accountLoading } = useGetAccount(accountId);

  // Derived data
  const cycleId = step?.cycle_id || step?.cycle;
  const isLoading = stepLoading || accountLoading;

  // Handle tab change via URL
  const handleTabChange = (newTab) => {
    const urlParams = new URLSearchParams(searchParams.toString());
    urlParams.set('tab', newTab);
    router.push(`?${urlParams.toString()}`, { scroll: false });
  };

  // Handle inline field save
  const handleSaveField = async (fieldKey, newValue) => {
    try {
      const result = await updateDecisionStep(stepId, { [fieldKey]: newValue }, cycleId);
      if (result.success) {
        displaySuccessSnackbar('Step updated');
        mutateStep();
        return true;
      } else {
        displayErrorSnackbar(result.error || 'Failed to update');
        return false;
      }
    } catch (error) {
      displayErrorSnackbar('An error occurred');
      return false;
    }
  };

  // Handle back navigation
  const handleBack = () => {
    if (accountId) {
      router.push(`/accounts/${accountId}?tab=decision-cycle`);
    } else {
      router.back();
    }
  };

  // Render tab content
  const renderTabContent = () => {
    switch (currentTab) {
      case 'overview':
        return (
          <DecisionStepOverviewTab 
            step={step} 
            account={account}
            onSave={handleSaveField}
            onUpdate={mutateStep}
          />
        );
      case 'activities':
        return (
          <DecisionStepActivitiesTab 
            step={step}
            accountId={accountId}
            onUpdate={mutateStep}
          />
        );
      case 'contacts':
        return (
          <DecisionStepContactsTab 
            step={step}
            accountId={accountId}
          />
        );
      case 'signals':
        return <DecisionStepSignalsTab step={step} />;
      case 'ai-prep':
        return <DecisionStepAIPrepTab step={step} />;
      default:
        return (
          <DecisionStepOverviewTab 
            step={step}
            account={account}
            onSave={handleSaveField}
            onUpdate={mutateStep}
          />
        );
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  // Error state
  if (stepError || !step) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <Stack spacing={2} alignItems="center">
          <Typography color="error">Decision step not found</Typography>
          <Button variant="outlined" onClick={() => router.back()}>
            Go Back
          </Button>
        </Stack>
      </Box>
    );
  }

  return (
    <Box>
      {/* Back Navigation */}
      <Button
        startIcon={<ArrowLeftOutlined />}
        onClick={handleBack}
        sx={{ mb: 2 }}
        color="secondary"
      >
        Back to {account?.company_name || 'Account'}
      </Button>

      {/* Header */}
      <DecisionStepHeader 
        step={step}
        account={account}
        cycleId={cycleId}
        onSave={handleSaveField}
        onUpdate={mutateStep}
      />

      {/* Tabs */}
      <DecisionStepTabs 
        activeTab={currentTab} 
        onTabChange={handleTabChange}
        step={step}
      />

      {/* Tab Content */}
      <MainCard sx={{ mt: 0, borderTopLeftRadius: 0, borderTopRightRadius: 0 }}>
        {renderTabContent()}
      </MainCard>
    </Box>
  );
}
