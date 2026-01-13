'use client';

import PropTypes from 'prop-types';

// MUI
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// Icons
import { RocketOutlined } from '@ant-design/icons';

// ==============================|| ACTIVITY PREPARATION TAB ||============================== //

export default function ActivityPreparationTab({ activity }) {
  return (
    <Box
      display="flex"
      justifyContent="center"
      alignItems="center"
      minHeight="300px"
    >
      <Stack spacing={2} alignItems="center" textAlign="center">
        <RocketOutlined style={{ fontSize: 48, color: '#8c8c8c' }} />
        <Typography variant="h5" color="text.secondary">
          AI Preparation
        </Typography>
        <Typography variant="body2" color="text.secondary" maxWidth={400}>
          Coming soon — AI-powered meeting preparation with context from signals, 
          account history, and decision cycle insights.
        </Typography>
      </Stack>
    </Box>
  );
}

ActivityPreparationTab.propTypes = {
  activity: PropTypes.object
};
