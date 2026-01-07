// frontend/src/sections/accounts/decision-cycles/DecisionCycleEmpty.jsx
/**
 * Decision Cycle Empty State Component
 * 
 * Displayed when no decision cycle exists for an account.
 * Provides clear call-to-action to create first cycle.
 * 
 * Features:
 * - Friendly empty state illustration
 * - Clear explanation of Decision Cycles
 * - Prominent CTA to create first cycle
 */

'use client';

import PropTypes from 'prop-types';

// material-ui
import { useTheme, alpha } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// icons
import PlusOutlined from '@ant-design/icons/PlusOutlined';
import NodeIndexOutlined from '@ant-design/icons/NodeIndexOutlined';

// ==============================|| DECISION CYCLE EMPTY ||============================== //

/**
 * DecisionCycleEmpty Component
 * 
 * @param {Function} onCreateCycle - Callback to create new cycle
 * @param {string} accountName - Name of the account (optional)
 */
export default function DecisionCycleEmpty({ onCreateCycle, accountName }) {
  const theme = useTheme();
  
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        py: 8,
        px: 3,
        textAlign: 'center'
      }}
    >
      {/* Icon */}
      <Box
        sx={{
          width: 80,
          height: 80,
          borderRadius: '50%',
          bgcolor: alpha(theme.palette.primary.main, 0.1),
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          mb: 3
        }}
      >
        <NodeIndexOutlined 
          style={{ 
            fontSize: 40, 
            color: theme.palette.primary.main 
          }} 
        />
      </Box>
      
      {/* Title */}
      <Typography variant="h5" gutterBottom>
        No Decision Cycle Yet
      </Typography>
      
      {/* Description */}
      <Typography 
        variant="body1" 
        color="text.secondary" 
        sx={{ 
          maxWidth: 480, 
          mb: 1 
        }}
      >
        Decision Cycles help you map and track the buyer&apos;s decision journey.
      </Typography>
      
      <Typography 
        variant="body2" 
        color="text.secondary" 
        sx={{ 
          maxWidth: 480, 
          mb: 4 
        }}
      >
        Create your first cycle to define the key steps, stakeholders, and milestones
        {accountName ? ` for ${accountName}` : ''}.
      </Typography>
      
      {/* Features List */}
      <Stack 
        spacing={1.5} 
        sx={{ 
          mb: 4,
          textAlign: 'left',
          bgcolor: 'background.default',
          borderRadius: 2,
          p: 2.5,
          border: '1px solid',
          borderColor: 'divider'
        }}
      >
        <FeatureItem text="Track decision steps across 5 stages" />
        <FeatureItem text="Identify stakeholders and their influence" />
        <FeatureItem text="Monitor progress and blockers" />
        <FeatureItem text="Estimate timelines and forecast accurately" />
      </Stack>
      
      {/* CTA Button */}
      <Button
        variant="contained"
        size="large"
        startIcon={<PlusOutlined />}
        onClick={onCreateCycle}
        sx={{
          px: 4,
          py: 1.25
        }}
      >
        Create Decision Cycle
      </Button>
    </Box>
  );
}

// ==============================|| FEATURE ITEM ||============================== //

function FeatureItem({ text }) {
  const theme = useTheme();
  
  return (
    <Stack direction="row" spacing={1.5} alignItems="center">
      <Box
        sx={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          bgcolor: 'primary.main',
          flexShrink: 0
        }}
      />
      <Typography variant="body2" color="text.secondary">
        {text}
      </Typography>
    </Stack>
  );
}

FeatureItem.propTypes = {
  text: PropTypes.string.isRequired
};

DecisionCycleEmpty.propTypes = {
  onCreateCycle: PropTypes.func.isRequired,
  accountName: PropTypes.string
};