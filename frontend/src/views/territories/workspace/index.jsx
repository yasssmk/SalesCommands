// frontend/src/views/territories/workspace/index.jsx

'use client';

import { useMemo } from 'react';
import { useParams, useSearchParams, useRouter } from 'next/navigation';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project imports
import MainCard from 'components/MainCard';
import TerritoryHeader from 'sections/territories/workspace/TerritoryHeader';
import TerritoryTabs, { DEFAULT_TAB } from 'sections/territories/workspace/TerritoryTabs';
import TerritoryAccountsTab from 'sections/territories/workspace/TerritoryAccountsTab';
import TerritoryContactsTab from 'sections/territories/workspace/TerritoryContactsTab';
import { TERRITORY_TYPES } from 'api/territories/territories';
import { useGetTerritoryWorkspace } from 'api/territories/territories';

// assets
import ArrowLeftOutlined from '@ant-design/icons/ArrowLeftOutlined';

// ==============================|| TERRITORY WORKSPACE PAGE ||============================== //

/**
 * Territory Workspace Page
 * 
 * Main workspace for viewing territory details with tabbed navigation.
 * Sales-facing page for exploring account segments.
 * 
 * Tabs:
 * - Summary: Territory description and filter summary
 * - List: Accounts belonging to this territory
 * - Activities: Activity history (placeholder)
 */
export default function TerritoryWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  
  const territoryId = params?.id;
  const currentTab = searchParams.get('tab') || DEFAULT_TAB;

  // ==============================|| DATA FETCHING ||============================== //

  const { 
    territory, 
    stats, 
    loading, 
    error,
    mutate
  } = useGetTerritoryWorkspace(territoryId);

  // ==============================|| HANDLERS ||============================== //

  const handleTabChange = (newTab) => {
    router.push(`/territories/${territoryId}?tab=${newTab}`, { scroll: false });
  };

  const handleBack = () => {
    router.push('/territories');
  };

  // ==============================|| RENDER - ERROR ||============================== //

  if (error || (!loading && !territory)) {
    return (
      <Box>
        <Button
          startIcon={<ArrowLeftOutlined />}
          onClick={handleBack}
          sx={{ mb: 2 }}
          color="inherit"
        >
          Back to Territories
        </Button>
        <MainCard>
          <Stack spacing={2} alignItems="center" py={4}>
            <Typography variant="h5" color="error">
              Territory not found
            </Typography>
            <Typography color="text.secondary">
              The territory you are looking for does not exist or you don&apos;t have access.
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
        Back to Territories
      </Button>

      {/* Territory Header */}
      <TerritoryHeader 
        territory={territory} 
        stats={stats} 
        loading={loading}
      />

      {/* Tabs Navigation */}
      <TerritoryTabs 
        activeTab={currentTab} 
        onTabChange={handleTabChange} 
        loading={loading} 
      />

      {/* Tab Content */}
      <MainCard>
        <TabContent 
          tab={currentTab} 
          territoryId={territoryId} 
          territory={territory} 
        />
      </MainCard>
    </Box>
  );
}

// ==============================|| TAB CONTENT COMPONENT ||============================== //

/**
 * Tab Content - Renders the appropriate tab component
 */
function TabContent({ tab, territoryId, territory }) {
  const content = useMemo(() => {
    switch (tab) {
      case 'summary':
        return (
          <TabPlaceholder 
            title="Summary" 
            description="Territory description and filter details will be displayed here." 
          />
        );
      case 'list':
        // Display accounts or contacts based on territory type
        if (territory?.type === TERRITORY_TYPES.CONTACT) {
          return (
            <TerritoryContactsTab 
              territoryId={territoryId} 
              territory={territory} 
            />
          );
        }
        return (
          <TerritoryAccountsTab 
            territoryId={territoryId} 
            territory={territory} 
          />
        );
      case 'activities':
        return (
          <TabPlaceholder 
            title="Activities" 
            description="Territory activity history will be displayed here." 
          />
        );
      default:
        return (
          <TabPlaceholder 
            title="Summary" 
            description="Territory description and filter details will be displayed here." 
          />
        );
    }
  }, [tab, territoryId, territory]);

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