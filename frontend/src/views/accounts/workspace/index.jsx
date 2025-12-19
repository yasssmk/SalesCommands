// src/views/accounts/workspace/index.jsx

'use client';

import { useMemo, useCallback } from 'react';
import { useParams, useSearchParams, useRouter } from 'next/navigation';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project imports
import MainCard from 'components/MainCard';
import AccountHeader from 'sections/accounts/workspace/AccountHeader';
import AccountTabs, { DEFAULT_TAB } from 'sections/accounts/workspace/AccountTabs';
import { useGetAccountWorkspace, useGetAccountChoices, updateAccount } from 'api/admin/accounts';
import { displaySuccessSnackbar, displayErrorSnackbar } from 'utils/displayError';

// assets
import ArrowLeftOutlined from '@ant-design/icons/ArrowLeftOutlined';

// ==============================|| ACCOUNT WORKSPACE PAGE ||============================== //

/**
 * Account Workspace Page
 * 
 * Main workspace for viewing account details with tabbed navigation.
 * Sales-facing page (not admin CRUD).
 */
export default function AccountWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  
  const accountId = params?.id;
  const currentTab = searchParams.get('tab') || DEFAULT_TAB;

  // ==============================|| DATA FETCHING ||============================== //

  const { 
    account, 
    stats, 
    workspaceLoading, 
    workspaceError,
    mutateWorkspace
  } = useGetAccountWorkspace(accountId);

  const {
    industries,
    choicesLoading
  } = useGetAccountChoices();

  // ==============================|| INDUSTRY OPTIONS ||============================== //

  const industryOptions = useMemo(() => {
    if (!industries || industries.length === 0) return [];
    return industries.map(industry => ({
      value: industry.value || industry,
      label: industry.label || industry
    }));
  }, [industries]);

  // ==============================|| HANDLERS ||============================== //

  const handleTabChange = (newTab) => {
    router.push(`/accounts/${accountId}?tab=${newTab}`, { scroll: false });
  };

  const handleBack = () => {
    router.back();
  };

  /**
   * Handle inline field save
   * 
   * @param {string} fieldKey - Field name to update
   * @param {string|null} newValue - New value for the field
   */
  const handleSaveField = useCallback(async (fieldKey, newValue) => {
    if (!accountId) return;

    try {
      const payload = { [fieldKey]: newValue };
      const result = await updateAccount(accountId, payload);

      if (result.success) {
        // Revalidate workspace data
        if (mutateWorkspace) {
          mutateWorkspace();
        }
        displaySuccessSnackbar('Account updated successfully');
      } else {
        throw new Error(result.error || 'Failed to update account');
      }
    } catch (error) {
      displayErrorSnackbar(error.message || 'Failed to update account');
      throw error; // Re-throw to keep edit mode open
    }
  }, [accountId, mutateWorkspace]);

  // ==============================|| RENDER - ERROR ||============================== //

  if (workspaceError || (!workspaceLoading && !account)) {
    return (
      <Box>
        <Button
          startIcon={<ArrowLeftOutlined />}
          onClick={handleBack}
          sx={{ mb: 2 }}
          color="inherit"
        >
          Back
        </Button>
        <MainCard>
          <Stack spacing={2} alignItems="center" py={4}>
            <Typography variant="h5" color="error">
              Account not found
            </Typography>
            <Typography color="text.secondary">
              The account you are looking for does not exist or you don&apos;t have access.
            </Typography>
            <Button variant="contained" onClick={handleBack}>
              Go Back
            </Button>
          </Stack>
        </MainCard>
      </Box>
    );
  }

  // ==============================|| RENDER - MAIN ||============================== //

  return (
    <Box>
      {/* Back Navigation */}
      <Button
        startIcon={<ArrowLeftOutlined />}
        onClick={handleBack}
        sx={{ mb: 2 }}
        color="inherit"
      >
        Back
      </Button>

      {/* Account Header */}
      <AccountHeader 
        account={account} 
        stats={stats} 
        loading={workspaceLoading || choicesLoading}
        onSave={handleSaveField}
        industryOptions={industryOptions}
      />

      {/* Tabs Navigation */}
      <AccountTabs 
        activeTab={currentTab} 
        onTabChange={handleTabChange} 
        loading={workspaceLoading} 
      />

      {/* Tab Content */}
      <MainCard>
        <TabContent tab={currentTab} accountId={accountId} />
      </MainCard>
    </Box>
  );
}

// ==============================|| TAB CONTENT COMPONENT ||============================== //

/**
 * Tab Content - Renders the appropriate tab component
 * 
 * Placeholder components for now, will be replaced with actual implementations.
 */
function TabContent({ tab, accountId }) {
  const content = useMemo(() => {
    switch (tab) {
      case 'summary':
        return <TabPlaceholder title="Summary" description="Account summary and key information will be displayed here." />;
      case 'qualification':
        return <TabPlaceholder title="Qualification" description="Account qualification data and signals will be displayed here." />;
      case 'buying-process':
        return <TabPlaceholder title="Buying Process" description="Buying process steps and stakeholders will be displayed here." />;
      case 'activities':
        return <TabPlaceholder title="Activities" description="Account activities and history will be displayed here." />;
      case 'contacts':
        return <TabPlaceholder title="Contacts" description="Account contacts will be displayed here." />;
      case 'signals':
        return <TabPlaceholder title="Signals" description="Account signals and alerts will be displayed here." />;
      default:
        return <TabPlaceholder title="Summary" description="Account summary and key information will be displayed here." />;
    }
  }, [tab]);

  return content;
}

// ==============================|| TAB PLACEHOLDER ||============================== //

/**
 * Placeholder component for tabs not yet implemented
 */
function TabPlaceholder({ title, description }) {
  return (
    <Stack spacing={2} alignItems="center" py={6}>
      <Typography variant="h5" color="text.secondary">
        {title}
      </Typography>
      <Typography color="text.secondary" textAlign="center">
        {description}
      </Typography>
      <Chip label="Coming Soon" color="info" variant="outlined" />
    </Stack>
  );
}