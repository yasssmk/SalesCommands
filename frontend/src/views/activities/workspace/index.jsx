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
import { useGetActivity, updateActivity } from 'api/accounts/activities';
import { displaySuccessSnackbar, displayErrorSnackbar } from 'utils/displayError';

// Section imports
import ActivityHeader from 'sections/activities/workspace/ActivityHeader';
import ActivityTabs, { DEFAULT_TAB } from 'sections/activities/workspace/ActivityTabs';
import ActivityOverviewTab from 'sections/activities/workspace/ActivityOverviewTab';
import ActivityPreparationTab from 'sections/activities/workspace/ActivityPreparationTab';
import ActivityOutcomeTab from 'sections/activities/workspace/ActivityOutcomeTab';
import ActivityTranscriptTab from 'sections/activities/workspace/ActivityTranscriptTab';
import ActivitySignalsTab from 'sections/activities/workspace/ActivitySignalsTab';


// Icons
import { ArrowLeftOutlined } from '@ant-design/icons';

// ==============================|| ACTIVITY WORKSPACE PAGE ||============================== //

export default function ActivityWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();

  const activityId = params?.id;
  const currentTab = searchParams.get('tab') || DEFAULT_TAB;

  const { activity, activityLoading, activityError, mutateActivity } = useGetActivity(activityId);

  // Handle tab change via URL
  const handleTabChange = (newTab) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', newTab);
    router.push(`?${params.toString()}`, { scroll: false });
  };

  // Handle inline field save
  const handleSaveField = async (fieldKey, newValue) => {
    try {
      const result = await updateActivity(activityId, { [fieldKey]: newValue });
      if (result.success) {
        displaySuccessSnackbar('Activity updated');
        mutateActivity();
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
    if (activity?.account) {
      router.push(`/accounts/${activity.account}?tab=activities`);
    } else {
      router.back();
    }
  };

  // Render tab content
  const renderTabContent = () => {
    switch (currentTab) {
      case 'overview':
        return <ActivityOverviewTab activity={activity} onSave={handleSaveField} />;
      case 'preparation':
        return <ActivityPreparationTab activity={activity} />;
      case 'outcome':
        return <ActivityOutcomeTab activity={activity} onSave={handleSaveField} onUpdate={mutateActivity} />;  
      case 'transcript':
        return <ActivityTranscriptTab activity={activity} />;
      case 'signals':
      return <ActivitySignalsTab activity={activity} />;
      default:
        return <ActivityOverviewTab activity={activity} onSave={handleSaveField} />;
    }
  };

  // Loading state
  if (activityLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  // Error state
  if (activityError) {
    const isTimeout = activityError?.response?.status === 408;
    const isNotFound = activityError?.response?.status === 404;
    
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
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
                {isTimeout ? 'Request timed out' : 'Failed to load activity'}
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
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {/* Back Navigation TO DO: if coming from territorie get back to territory/actvities */}
      <Button
        startIcon={<ArrowLeftOutlined />}
        onClick={handleBack}
        sx={{ mb: 2 }}
        color="secondary"
      >
        Back to {activity.account_detail?.company_name || 'Account'}
      </Button>

      {/* Header */}
      <ActivityHeader 
        activity={activity} 
        onSave={handleSaveField} 
        onUpdate={mutateActivity}
      />

      {/* Tabs */}
      <ActivityTabs 
        activeTab={currentTab} 
        onTabChange={handleTabChange} 
      />

      {/* Tab Content */}
      <MainCard sx={{ mt: 0, borderTopLeftRadius: 0, borderTopRightRadius: 0 }}>
        {renderTabContent()}
      </MainCard>
    </Box>
  );
}
