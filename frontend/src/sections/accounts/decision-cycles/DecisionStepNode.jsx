// frontend/src/sections/accounts/decision-cycles/DecisionStepNode.jsx
/**
 * Decision Step Node Component
 * 
 * Individual step card displayed in the timeline.
 * Shows step name, status indicator, and key info.
 * 
 * Features:
 * - Color-coded status indicator
 * - Hover effect for preview trigger
 * - Click for edit modal
 * - Shows stakeholder and expected days
 */

'use client';

import PropTypes from 'prop-types';

// material-ui
import { useTheme, alpha } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';

// icons
import UserOutlined from '@ant-design/icons/UserOutlined';
import ClockCircleOutlined from '@ant-design/icons/ClockCircleOutlined';
import LinkOutlined from '@ant-design/icons/LinkOutlined';

// ==============================|| DECISION STEP NODE ||============================== //

/**
 * Step Node Component
 * 
 * @param {Object} props
 * @param {Object} props.step - Step data
 * @param {Object} props.statusConfig - Status configuration (color, icon, label)
 * @param {Function} props.onClick - Click handler for edit
 * @param {Function} props.onMouseEnter - Mouse enter handler for preview
 * @param {Function} props.onMouseLeave - Mouse leave handler
 * @param {boolean} props.isHovered - Whether this step is currently hovered
 */
export default function DecisionStepNode({
  step,
  statusConfig,
  onClick,
  onMouseEnter,
  onMouseLeave,
  isHovered = false
}) {
  const theme = useTheme();
  
  const StatusIcon = statusConfig?.icon;
  
  // Determine border color based on status
  const getBorderColor = () => {
    if (isHovered) return theme.palette.primary.main;
    if (step.is_current) return theme.palette.primary.main;
    
    switch (step.status) {
      case 'VALIDATED':
        return theme.palette.success.main;
      case 'REJECTED':
        return theme.palette.error.main;
      case 'IN_PROGRESS':
      case 'PENDING_CLIENT':
      case 'IN_CHASING':
        return theme.palette.info.main;
      default:
        return theme.palette.divider;
    }
  };
  
  // Determine background color
  const getBgColor = () => {
    if (isHovered) return alpha(theme.palette.primary.main, 0.08);
    if (step.is_current) return alpha(theme.palette.primary.main, 0.04);
    return theme.palette.background.paper;
  };
  
  return (
    <Box
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      sx={{
        p: 1.5,
        borderRadius: 1.5,
        border: '2px solid',
        borderColor: getBorderColor(),
        bgcolor: getBgColor(),
        cursor: 'pointer',
        transition: 'all 0.2s ease-in-out',
        '&:hover': {
          borderColor: theme.palette.primary.main,
          bgcolor: alpha(theme.palette.primary.main, 0.08),
          transform: 'translateY(-2px)',
          boxShadow: theme.shadows[2]
        }
      }}
    >
      <Stack spacing={1}>
        {/* Header: Name + Status */}
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
          <Typography 
            variant="subtitle2" 
            fontWeight={600}
            sx={{
              flex: 1,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical'
            }}
          >
            {step.name}
          </Typography>
          
          {StatusIcon && (
            <Box
              sx={{
                color: `${statusConfig.color}.main`,
                fontSize: 16,
                flexShrink: 0
              }}
            >
              <StatusIcon />
            </Box>
          )}
        </Stack>
        
        {/* Status Chip */}
        <Chip
          size="small"
          label={statusConfig?.label || step.status}
          color={statusConfig?.color || 'default'}
          variant={step.status === 'VALIDATED' || step.status === 'REJECTED' ? 'filled' : 'outlined'}
          sx={{ 
            height: 20, 
            fontSize: '0.7rem',
            alignSelf: 'flex-start'
          }}
        />
        
        {/* Meta Info */}
        <Stack direction="row" spacing={1.5} flexWrap="wrap" sx={{ mt: 0.5 }}>
          {/* Stakeholder */}
          {step.stakeholder && (
            <Stack direction="row" spacing={0.5} alignItems="center">
              <UserOutlined style={{ fontSize: 12, color: theme.palette.text.secondary }} />
              <Typography variant="caption" color="text.secondary" noWrap sx={{ maxWidth: 80 }}>
                {step.stakeholder}
              </Typography>
            </Stack>
          )}
          
          {/* Expected Days */}
          {step.expected_days && (
            <Stack direction="row" spacing={0.5} alignItems="center">
              <ClockCircleOutlined style={{ fontSize: 12, color: theme.palette.text.secondary }} />
              <Typography variant="caption" color="text.secondary">
                {step.expected_days}d
              </Typography>
            </Stack>
          )}
          
          {/* Contacts Count */}
          {step.contacts_count > 0 && (
            <Stack direction="row" spacing={0.5} alignItems="center">
              <LinkOutlined style={{ fontSize: 12, color: theme.palette.text.secondary }} />
              <Typography variant="caption" color="text.secondary">
                {step.contacts_count}
              </Typography>
            </Stack>
          )}
        </Stack>
        
        {/* Current Step Indicator */}
        {step.is_current && (
          <Box
            sx={{
              mt: 0.5,
              px: 1,
              py: 0.25,
              bgcolor: 'primary.main',
              borderRadius: 0.5,
              alignSelf: 'flex-start'
            }}
          >
            <Typography variant="caption" sx={{ color: 'white', fontWeight: 600, fontSize: '0.65rem' }}>
              CURRENT
            </Typography>
          </Box>
        )}
      </Stack>
    </Box>
  );
}

DecisionStepNode.propTypes = {
  step: PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    status: PropTypes.string.isRequired,
    stage: PropTypes.string.isRequired,
    stakeholder: PropTypes.string,
    expected_days: PropTypes.number,
    contacts_count: PropTypes.number,
    is_current: PropTypes.bool
  }).isRequired,
  statusConfig: PropTypes.shape({
    color: PropTypes.string,
    bgColor: PropTypes.string,
    icon: PropTypes.elementType,
    label: PropTypes.string
  }),
  onClick: PropTypes.func,
  onMouseEnter: PropTypes.func,
  onMouseLeave: PropTypes.func,
  isHovered: PropTypes.bool
};