'use client';

import PropTypes from 'prop-types';

// MUI
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// Icons
import { ThunderboltOutlined } from '@ant-design/icons';

// ==============================|| ACTIVITY SIGNALS TAB ||============================== //

export default function ActivitySignalsTab({ activity }) {
  return (
    <Box
      display="flex"
      justifyContent="center"
      alignItems="center"
      minHeight="300px"
    >
      <Stack spacing={2} alignItems="center" textAlign="center">
        <ThunderboltOutlined style={{ fontSize: 48, color: '#8c8c8c' }} />
        <Typography variant="h5" color="text.secondary">
          Signals & Insights
        </Typography>
        <Typography variant="body2" color="text.secondary" maxWidth={400}>
          Coming soon — View and manage signals extracted from transcripts 
          or add them manually. Qualify accounts, track tech stack, 
          and feed decision cycle insights.
        </Typography>
      </Stack>
    </Box>
  );
}

ActivitySignalsTab.propTypes = {
  activity: PropTypes.object
};
