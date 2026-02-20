// frontend/src/views/campaigns/workspace/index.jsx
/**
 * Campaign Workspace Page
 *
 * Uses WorkspaceLayout with tabs: Summary, Accounts, Activities, Members.
 * KeepAlive pattern for heavy tabs (accounts, activities).
 *
 * Pattern: views/accounts/workspace/index.jsx
 */

'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';

// MUI
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project imports
import MainCard from 'components/MainCard';
import WorkspaceLayout from 'components/WorkspaceLayout';
import { buildCampaignBreadcrumbs } from 'sections/campaigns/workspace/CampaignBreadcrumbs';
import useCampaignHeaderProps from 'sections/campaigns/workspace/CampaignHeader';
import { CAMPAIGN_TABS, DEFAULT_TAB } from 'sections/campaigns/workspace/CampaignTabs';
import CampaignOverviewTab from 'sections/campaigns/workspace/CampaignOverviewTab';
import CampaignAccountsTab from 'sections/campaigns/workspace/CampaignAccountsTab';
import CampaignActivitiesTab from 'sections/campaigns/workspace/CampaignActivitiesTab';
import CampaignMembersTab from 'sections/campaigns/workspace/CampaignMembersTab';

// api
import { useGetCampaignWorkspace } from 'api/campaigns/campaigns';

// icons
import ArrowLeftOutlined from '@ant-design/icons/ArrowLeftOutlined';

// ==============================|| CAMPAIGN WORKSPACE PAGE ||============================== //

export default function CampaignWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();

  const campaignId = params?.id;
  const currentTab = searchParams.get('tab') || DEFAULT_TAB;

  // ==============================|| DATA ||============================== //

  const {
    campaign,
    stats,
    loading: campaignLoading,
    error: campaignError,
    mutate: mutateCampaign
  } = useGetCampaignWorkspace(campaignId);

  // ==============================|| NAVIGATION ||============================== //

  const handleBack = () => {
    router.push('/campaigns');
  };

  const handleTabChange = (newTab) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', newTab);
    router.push(`?${params.toString()}`, { scroll: false });
  };

  // ==============================|| HEADER PROPS ||============================== //

  const headerProps = useCampaignHeaderProps({ campaign, stats });

  const breadcrumbItems = campaign
    ? buildCampaignBreadcrumbs({ campaignName: campaign.name })
    : [];

  // ==============================|| ERROR STATE ||============================== //

  if (!campaignLoading && (campaignError || !campaign)) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <MainCard>
          <Stack spacing={2} alignItems="center" sx={{ p: 3 }}>
            <Typography variant="h5" color="error">
              Campaign not found
            </Typography>
            <Typography variant="body2" color="text.secondary">
              The campaign you are looking for does not exist or has been deleted.
            </Typography>
            <Button variant="contained" onClick={handleBack}>
              Go Back
            </Button>
          </Stack>
        </MainCard>
      </Box>
    );
  }

  // ==============================|| RENDER ||============================== //

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

      {/* Workspace Layout */}
      <WorkspaceLayout
        breadcrumbs={breadcrumbItems}
        {...headerProps}
        tabs={CAMPAIGN_TABS}
        activeTab={currentTab}
        onTabChange={handleTabChange}
        loading={campaignLoading}
      >
        <TabContent
          tab={currentTab}
          campaignId={campaignId}
          campaign={campaign}
        />
      </WorkspaceLayout>
    </Box>
  );
}

// ==============================|| TAB CONTENT COMPONENT ||============================== //

/**
 * Tab Content — KeepAlive pattern for heavy tabs.
 *
 * Accounts and Activities tabs are kept mounted but hidden via CSS display:none
 * when inactive. This prevents unmount/remount cycles on tab switch.
 */
function TabContent({ tab, campaignId, campaign }) {
  const [mountedTabs, setMountedTabs] = useState(new Set());

   // DEBUG — remove after fix
  console.log('TabContent imports:', {
    CampaignOverviewTab: typeof CampaignOverviewTab,
    CampaignAccountsTab: typeof CampaignAccountsTab,
    CampaignActivitiesTab: typeof CampaignActivitiesTab,
    CampaignMembersTab: typeof CampaignMembersTab
  });

  useEffect(() => {
    if (['accounts', 'activities', 'members'].includes(tab)) {
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
      {/* Overview — lightweight, conditional render */}
      {tab === 'overview' && (
        <CampaignOverviewTab  campaign={campaign} />
      )}

      {/* Accounts — KeepAlive */}
      {mountedTabs.has('accounts') && (
        <Box sx={{ display: tab === 'accounts' ? 'block' : 'none' }}>
          <CampaignAccountsTab campaignId={campaignId} campaign={campaign} />
        </Box>
      )}

      {/* Activities — KeepAlive */}
      {mountedTabs.has('activities') && (
        <Box sx={{ display: tab === 'activities' ? 'block' : 'none' }}>
          <CampaignActivitiesTab campaignId={campaignId} campaign={campaign} />
        </Box>
      )}

      {/* Members — KeepAlive */}
      {mountedTabs.has('members') && (
        <Box sx={{ display: tab === 'members' ? 'block' : 'none' }}>
          <CampaignMembersTab campaignId={campaignId} campaign={campaign} />
        </Box>
      )}
    </>
  );
}