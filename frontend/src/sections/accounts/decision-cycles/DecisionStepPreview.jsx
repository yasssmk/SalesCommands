// frontend/src/sections/accounts/decision-cycles/DecisionStepPreview.jsx
/**
 * Decision Step Preview Component
 * 
 * Popover that appears on hover over a step node.
 * Shows quick summary of step details.
 * 
 * Features:
 * - Appears on hover with slight delay
 * - Shows key step information
 * - Status indicator
 * - Stakeholder, expected days
 * - Description preview
 * - Click prompt to open full detail
 */

'use client';

import PropTypes from 'prop-types';

// material-ui
import { useTheme, alpha } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Popover from '@mui/material/Popover';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// icons
import UserOutlined from '@ant-design/icons/UserOutlined';
import ClockCircleOutlined from '@ant-design/icons/ClockCircleOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import AimOutlined from '@ant-design/icons/AimOutlined';

// ==============================|| STAGE LABELS ||============================== //

const STAGE_LABELS = {
  EXPLORATION: 'Exploration',
  CRITERIA_VALIDATION: 'Criteria Validation',
  SOLUTION_CONFIRMATION: 'Solution Confirmation',
  BUSINESS_VALIDATION: 'Business Validation',
  FORMALIZATION: 'Formalization'
};

// ==============================|| INFO ROW ||============================== //

function InfoRow({ icon: Icon, label, value }) {
  const theme = useTheme();
  
  if (!value) return null;
  
  return (
    <Stack direction="row" spacing={1} alignItems="flex-start">
      <Icon style={{ fontSize: 14, color: theme.palette.text.secondary, marginTop: 2 }} />
      <Box>
        <Typography variant="caption" color="text.secondary" display="block">
          {label}
        </Typography>
        <Typography variant="body2">
          {value}
        </Typography>
      </Box>
    </Stack>
  );
}

InfoRow.propTypes = {
  icon: PropTypes.elementType.isRequired,
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number])
};

// ==============================|| DECISION STEP PREVIEW ||============================== //

/**
 * DecisionStepPreview Component
 * 
 * @param {Object} step - Step data to display
 * @param {Element} anchorEl - Anchor element for popover positioning
 * @param {Function} onClose - Close callback
 * @param {Object} statusConfig - Status configuration (color, label)
 */
export default function DecisionStepPreview({
  step,
  anchorEl,
  onClose,
  statusConfig
}) {
  const theme = useTheme();
  
  const open = Boolean(anchorEl) && Boolean(step);
  
  if (!step) return null;
  
  // Truncate description for preview
  const descriptionPreview = step.description
    ? step.description.length > 120
      ? `${step.description.substring(0, 120)}...`
      : step.description
    : null;
  
  return (
    <Popover
      open={open}
      anchorEl={anchorEl}
      onClose={onClose}
      anchorOrigin={{
        vertical: 'bottom',
        horizontal: 'center'
      }}
      transformOrigin={{
        vertical: 'top',
        horizontal: 'center'
      }}
      sx={{
        pointerEvents: 'none'
      }}
      PaperProps={{
        sx: {
          p: 2,
          maxWidth: 320,
          minWidth: 260,
          boxShadow: theme.shadows[8],
          border: '1px solid',
          borderColor: 'divider'
        }
      }}
      disableRestoreFocus
    >
      <Stack spacing={1.5}>
        {/* Header */}
        <Box>
          <Typography variant="subtitle1" fontWeight={600}>
            {step.name}
          </Typography>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 0.5 }}>
            <Chip
              size="small"
              label={STAGE_LABELS[step.stage] || step.stage}
              variant="outlined"
              sx={{ height: 20, fontSize: '0.7rem' }}
            />
            <Chip
              size="small"
              label={statusConfig?.label || step.status}
              color={statusConfig?.color || 'default'}
              sx={{ height: 20, fontSize: '0.7rem' }}
            />
          </Stack>
        </Box>
        
        {/* Quick Info */}
        {(step.stakeholder || step.expected_days || step.contacts_count > 0) && (
          <>
            <Divider />
            <Stack spacing={1}>
              {step.stakeholder && (
                <InfoRow
                  icon={UserOutlined}
                  label="Stakeholder"
                  value={step.stakeholder}
                />
              )}
              
              {step.expected_days && (
                <InfoRow
                  icon={ClockCircleOutlined}
                  label="Expected Duration"
                  value={`${step.expected_days} days`}
                />
              )}
              
              {step.contacts_count > 0 && (
                <InfoRow
                  icon={TeamOutlined}
                  label="Contacts"
                  value={`${step.contacts_count} contact${step.contacts_count > 1 ? 's' : ''}`}
                />
              )}
            </Stack>
          </>
        )}
        
        {/* Goal Preview */}
        {step.goal && (
          <>
            <Divider />
            <Box>
              <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mb: 0.5 }}>
                <AimOutlined style={{ fontSize: 12, color: theme.palette.text.secondary }} />
                <Typography variant="caption" color="text.secondary">
                  Goal
                </Typography>
              </Stack>
              <Typography variant="body2" color="text.secondary">
                {step.goal.length > 80 ? `${step.goal.substring(0, 80)}...` : step.goal}
              </Typography>
            </Box>
          </>
        )}
        
        {/* Description Preview */}
        {descriptionPreview && (
          <>
            <Divider />
            <Typography variant="body2" color="text.secondary">
              {descriptionPreview}
            </Typography>
          </>
        )}
        
        {/* Criterias Preview */}
        {step.criterias && step.criterias.length > 0 && (
          <>
            <Divider />
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
                Criterias
              </Typography>
              <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                {step.criterias.slice(0, 3).map((criteria, index) => (
                  <Chip
                    key={index}
                    label={criteria}
                    size="small"
                    variant="outlined"
                    sx={{ height: 20, fontSize: '0.65rem' }}
                  />
                ))}
                {step.criterias.length > 3 && (
                  <Chip
                    label={`+${step.criterias.length - 3}`}
                    size="small"
                    sx={{ height: 20, fontSize: '0.65rem' }}
                  />
                )}
              </Stack>
            </Box>
          </>
        )}
        
        {/* Click hint */}
        <Divider />
        <Typography 
          variant="caption" 
          color="primary"
          sx={{ 
            textAlign: 'center',
            fontStyle: 'italic'
          }}
        >
          Click to view full details
        </Typography>
      </Stack>
    </Popover>
  );
}

DecisionStepPreview.propTypes = {
  step: PropTypes.shape({
    id: PropTypes.string,
    name: PropTypes.string,
    stage: PropTypes.string,
    status: PropTypes.string,
    stakeholder: PropTypes.string,
    description: PropTypes.string,
    goal: PropTypes.string,
    expected_days: PropTypes.number,
    contacts_count: PropTypes.number,
    criterias: PropTypes.array
  }),
  anchorEl: PropTypes.any,
  onClose: PropTypes.func.isRequired,
  statusConfig: PropTypes.shape({
    color: PropTypes.string,
    label: PropTypes.string
  })
};