// frontend/src/sections/activities/workspace/ActivityNextStepsTab.jsx

'use client';

import PropTypes from 'prop-types';

// MUI
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// Icons
import { ScheduleOutlined } from '@ant-design/icons';

// ==============================|| ACTIVITY NEXT STEPS TAB (PLACEHOLDER) ||============================== //

export default function ActivityNextStepsTab({ activity, isLocked }) {
  return (
    <Box
      display="flex"
      justifyContent="center"
      alignItems="center"
      minHeight="300px"
    >
      <Stack spacing={2} alignItems="center" textAlign="center">
        <ScheduleOutlined style={{ fontSize: 48, color: '#8c8c8c' }} />
        <Typography variant="h5" color="text.secondary">
          Next Steps
        </Typography>
        <Typography variant="body2" color="text.secondary" maxWidth={400}>
          Coming in Sprint F6 — Wizard for materializing AI-suggested next
          steps into concrete Activities, with title, due date, contact
          assignment, and activity type.
        </Typography>
      </Stack>
    </Box>
  );
}

ActivityNextStepsTab.propTypes = {
  activity: PropTypes.object,
  isLocked: PropTypes.bool,
};
