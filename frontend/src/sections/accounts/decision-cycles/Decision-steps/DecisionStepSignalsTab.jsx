// frontend/src/sections/accounts/decision-cycles/Decision-steps/DecisionStepSignalsTab.jsx

'use client';

import PropTypes from 'prop-types';

// MUI
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';

// Icons
import { ThunderboltOutlined } from '@ant-design/icons';

// ==============================|| DECISION STEP SIGNALS TAB (STUB) ||============================== //

/**
 * Decision Step Signals Tab - Phase 3 Stub
 * 
 * Future features:
 * - Signals extracted from linked activities' transcripts
 * - Manual signal tagging
 * - Buying signals, tech stack, pain points
 * - Integration with Signals module
 */
export default function DecisionStepSignalsTab({ step }) {
  return (
    <Box
      display="flex"
      justifyContent="center"
      alignItems="center"
      minHeight="300px"
    >
      <Stack spacing={2} alignItems="center" textAlign="center">
        <ThunderboltOutlined style={{ fontSize: 48, color: '#8c8c8c' }} />
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="h5" color="text.secondary">
            Signals & Insights
          </Typography>
          <Chip label="Phase 3" size="small" variant="outlined" />
        </Stack>
        <Typography variant="body2" color="text.secondary" maxWidth={400}>
          Coming soon — Aggregate signals from linked activities, transcripts, 
          and external sources. Track buying signals, pain points, and 
          decision criteria for this step.
        </Typography>
      </Stack>
    </Box>
  );
}

DecisionStepSignalsTab.propTypes = {
  step: PropTypes.object
};
