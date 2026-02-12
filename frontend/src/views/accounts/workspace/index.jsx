// src/views/accounts/workspace/index.jsx

'use client';

import { useMemo, useCallback, useState, useEffect } from 'react';
import { useParams, useSearchParams, useRouter } from 'next/navigation';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project imports
import MainCard from 'components/MainCard';
import WorkspaceLayout from 'components/WorkspaceLayout';
import useAccountHeaderProps from 'sections/accounts/workspace/AccountHeader';
import { WORKSPACE_TABS, DEFAULT_TAB } from 'sections/accounts/workspace/AccountTabs';
import { useGetAccountWorkspace, useGetAccountChoices, updateAccount } from 'api/admin/accounts';
import AccountContactsTab from 'sections/accounts/contacts/AccountContactsTab';
import DecisionCycleTab from 'sections/accounts/workspace/DecisionCycleTab';
import AccountActivitiesTab from 'sections/accounts/activities/AccountActivitiesTab';
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

  // ==============================|| HEADER PROPS (from hook) ||============================== //

  const headerProps = useAccountHeaderProps({
    account,
    stats,
    onSave: handleSaveField,
    industryOptions
  });

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

      {/* Workspace Layout: Header + Tabs + Content */}
      <WorkspaceLayout
        {...headerProps}
        tabs={WORKSPACE_TABS}
        activeTab={currentTab}
        onTabChange={handleTabChange}
        loading={workspaceLoading || choicesLoading}
      >
        <TabContent tab={currentTab} accountId={accountId} account={account} />
      </WorkspaceLayout>
    </Box>
  );
}

// ==============================|| TAB CONTENT COMPONENT ||============================== //

/**
 * Tab Content - KeepAlive pattern for heavy tabs
 * 
 * DecisionCycleTab and AccountActivitiesTab are kept mounted but hidden
 * via CSS display:none when inactive. This prevents unmount/remount cycles
 * that trigger redundant API fetches and SWR cache misses on tab switch.
 * 
 * Lightweight tabs (placeholders) use conditional rendering as before.
 */
function TabContent({ tab, accountId, account }) {
  // Track which heavy tabs have been visited (lazy mount)
  const [mountedTabs, setMountedTabs] = useState(new Set());

  useEffect(() => {
    if (['decision-cycle', 'activities', 'contacts'].includes(tab)) {
      setMountedTabs((prev) => {
        if (prev.has(tab)) return prev;
        const next = new Set(prev);
        next.add(tab);
        return next;
      });
    }
  }, [tab]);

  return (
    <>
      {/* KeepAlive tabs: mounted once, hidden with CSS when inactive */}
      {mountedTabs.has('decision-cycle') && (
        <Box sx={{ display: tab === 'decision-cycle' ? 'block' : 'none' }}>
          <DecisionCycleTab accountId={accountId} accountName={account?.company_name} />
        </Box>
      )}
      {mountedTabs.has('activities') && (
        <Box sx={{ display: tab === 'activities' ? 'block' : 'none' }}>
          <AccountActivitiesTab accountId={accountId} account={account} />
        </Box>
      )}
      {mountedTabs.has('contacts') && (
        <Box sx={{ display: tab === 'contacts' ? 'block' : 'none' }}>
          <AccountContactsTab accountId={accountId} account={account} />
        </Box>
      )}

      {/* Lightweight tabs: conditional rendering (no SWR hooks) */}
      {tab === 'overview' && (
        <TabPlaceholder title="Overview" description="Account overview and key information will be displayed here." />
      )}
      {tab === 'qualification' && (
        <TabPlaceholder title="Qualification" description="Account qualification data and signals will be displayed here." />
      )}
      {tab === 'signals' && (
        <TabPlaceholder title="Signals" description="Account signals and alerts will be displayed here." />
      )}
    </>
  );
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