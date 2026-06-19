// frontend/src/sections/activities/workspace/ActivityPreparationTab.jsx
'use client';

import PropTypes from 'prop-types';
import { useState, useCallback } from 'react';

// MUI
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// Icons
import { StopOutlined } from '@ant-design/icons';

// Project imports
import { runPrepCall, useGetPrepCallSnapshot } from 'api/aiPipelines/prepCall';
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from 'utils/displayError';

// Section imports
import PrepCallEmptyState from 'sections/activities/workspace/PrepCallEmptyState';
import PrepCallBrief from 'sections/activities/workspace/PrepCallBrief';

// ==============================|| ELIGIBLE ACTIVITY TYPES ||============================== //

const ELIGIBLE_TYPES = new Set(['CALL', 'MEETING', 'DEMO']);

// ==============================|| ACTIVITY PREPARATION TAB ||============================== //

export default function ActivityPreparationTab({ activity }) {
  const activityId = activity?.id;
  const activityType = activity?.activity_type;

  const { snapshot, snapshotLoading, snapshotError, mutateSnapshot } =
    useGetPrepCallSnapshot(activityId);

  const [isGenerating, setIsGenerating] = useState(false);
  const [generateError, setGenerateError] = useState(null);

  // MVP: target_contact selection deferred to V2
  const handleGenerate = useCallback(async () => {
    setIsGenerating(true);
    setGenerateError(null);
    try {
      const result = await runPrepCall(activityId, null);
      if (result.success) {
        displaySuccessSnackbar('Brief generated');
        mutateSnapshot();
      } else {
        const msg = result.error || 'Failed to generate brief';
        setGenerateError(msg);
        displayErrorSnackbar(result);
      }
    } catch {
      setGenerateError('Unexpected error');
    } finally {
      setIsGenerating(false);
    }
  }, [activityId, mutateSnapshot]);

  // Ineligible activity type
  if (!ELIGIBLE_TYPES.has(activityType)) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="300px"
      >
        <Stack spacing={2} alignItems="center" textAlign="center">
          <StopOutlined style={{ fontSize: 48, color: '#8c8c8c' }} />
          <Typography variant="h5" color="text.secondary">
            Not available
          </Typography>
          <Typography variant="body2" color="text.secondary" maxWidth={400}>
            AI preparation is only available for calls, meetings, and demos.
          </Typography>
        </Stack>
      </Box>
    );
  }

  // Loading
  if (snapshotLoading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="300px"
      >
        <CircularProgress />
      </Box>
    );
  }

  // SWR error
  if (snapshotError) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="300px"
      >
        <Typography color="error">Failed to load preparation brief</Typography>
      </Box>
    );
  }

  // No snapshot yet — empty state
  if (!snapshot) {
    return (
      <PrepCallEmptyState
        onGenerate={handleGenerate}
        isGenerating={isGenerating}
        error={generateError}
      />
    );
  }

  // Snapshot exists — display brief
  return (
    <PrepCallBrief
      snapshot={snapshot}
      onRegenerate={handleGenerate}
      isRegenerating={isGenerating}
    />
  );
}

ActivityPreparationTab.propTypes = {
  activity: PropTypes.shape({
    id: PropTypes.string,
    activity_type: PropTypes.string,
  }),
};
