// frontend/src/sections/accounts/decision-cycles/Decision-steps/DecisionStepAIPrepTab.jsx

'use client';

import PropTypes from 'prop-types';

// MUI
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';

// Icons
import { RobotOutlined } from '@ant-design/icons';

// ==============================|| DECISION STEP AI PREP TAB (STUB) ||============================== //

/**
 * Decision Step AI Preparation Tab - Phase 3 Stub
 * 
 * Future features:
 * - AI-generated meeting preparation
 * - Suggested talking points based on step context
 * - Objection handling suggestions
 * - Stakeholder analysis and approach recommendations
 * - Integration with campaign playbooks
 */
export default function DecisionStepAIPrepTab({ step }) {
  return (
    <Box
      display="flex"
      justifyContent="center"
      alignItems="center"
      minHeight="300px"
    >
      <Stack spacing={2} alignItems="center" textAlign="center">
        <RobotOutlined style={{ fontSize: 48, color: '#8c8c8c' }} />
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="h5" color="text.secondary">
            AI Preparation
          </Typography>
          <Chip label="Phase 3" size="small" variant="outlined" />
        </Stack>
        <Typography variant="body2" color="text.secondary" maxWidth={400}>
          Coming soon — AI-powered preparation for this decision step.
          Get suggested talking points, objection handling tips, 
          stakeholder insights, and personalized approach recommendations.
        </Typography>
      </Stack>
    </Box>
  );
}

DecisionStepAIPrepTab.propTypes = {
  step: PropTypes.object
};
