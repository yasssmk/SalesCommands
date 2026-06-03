// frontend/src/sections/activities/workspace/ActivityNotesTab.jsx

'use client';

import PropTypes from 'prop-types';

// MUI
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// Icons
import { FormOutlined } from '@ant-design/icons';

// ==============================|| ACTIVITY NOTES TAB (PLACEHOLDER) ||============================== //

export default function ActivityNotesTab({ activity, isLocked }) {
  return (
    <Box
      display="flex"
      justifyContent="center"
      alignItems="center"
      minHeight="300px"
    >
      <Stack spacing={2} alignItems="center" textAlign="center">
        <FormOutlined style={{ fontSize: 48, color: '#8c8c8c' }} />
        <Typography variant="h5" color="text.secondary">
          Notes &amp; Transcript
        </Typography>
        <Typography variant="body2" color="text.secondary" maxWidth={400}>
          Coming in Sprint F2 — Transcript capture, free-form notes,
          and AI analysis trigger for post-call signal extraction.
        </Typography>
      </Stack>
    </Box>
  );
}

ActivityNotesTab.propTypes = {
  activity: PropTypes.object,
  isLocked: PropTypes.bool,
};
