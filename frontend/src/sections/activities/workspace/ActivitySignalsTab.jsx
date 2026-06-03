// frontend/src/sections/activities/workspace/ActivitySignalsTab.jsx

'use client';

import PropTypes from 'prop-types';

// MUI
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// Icons
import { ThunderboltOutlined } from '@ant-design/icons';

// ==============================|| ACTIVITY SIGNALS TAB (PLACEHOLDER) ||============================== //

export default function ActivitySignalsTab({ activity, isLocked }) {
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
          Signals
        </Typography>
        <Typography variant="body2" color="text.secondary" maxWidth={400}>
          Coming in Sprint F5 — Validation wizard for LLM-extracted signals
          (pain points, objectives, tech stack, blockers) with manual review
          and contact attribution.
        </Typography>
      </Stack>
    </Box>
  );
}

ActivitySignalsTab.propTypes = {
  activity: PropTypes.object,
  isLocked: PropTypes.bool,
};
