// frontend/src/sections/accounts/decision-cycles/DecisionStepPreview.jsx
/**
 * Decision Step Preview Component
 * 
 * Popover that appears on hover over a step node.
 * Shows quick summary of step details.
 * 
 * Features:
 * - Appears on hover with slight delay
 * - Shows step type with icon
 * - Scheduled date/time display
 * - Departments list
 * - Status indicator
 * - Stakeholder, expected days
 * - Description preview
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
import CalendarOutlined from '@ant-design/icons/CalendarOutlined';
import PhoneOutlined from '@ant-design/icons/PhoneOutlined';
import MailOutlined from '@ant-design/icons/MailOutlined';
import CheckSquareOutlined from '@ant-design/icons/CheckSquareOutlined';
import AuditOutlined from '@ant-design/icons/AuditOutlined';
import SafetyOutlined from '@ant-design/icons/SafetyOutlined';
import QuestionCircleOutlined from '@ant-design/icons/QuestionCircleOutlined';
import BankOutlined from '@ant-design/icons/BankOutlined';

// ==============================|| CONSTANTS ||============================== //

const STAGE_LABELS = {
  EXPLORATION: 'Exploration',
  CRITERIA_VALIDATION: 'Criteria Validation',
  SOLUTION_CONFIRMATION: 'Solution Confirmation',
  BUSINESS_VALIDATION: 'Business Validation',
  FORMALIZATION: 'Formalization'
};

const STEP_TYPE_CONFIG = {
  MEETING: { icon: TeamOutlined, label: 'Meeting', color: 'primary' },
  CALL: { icon: PhoneOutlined, label: 'Call', color: 'info' },
  EMAIL: { icon: MailOutlined, label: 'Email', color: 'default' },
  TASK_SELLER: { icon: CheckSquareOutlined, label: 'Task (Seller)', color: 'warning' },
  TASK_BUYER: { icon: AuditOutlined, label: 'Task (Buyer)', color: 'secondary' },
  INTERNAL_VALIDATION: { icon: SafetyOutlined, label: 'Internal Validation', color: 'success' },
  OTHER: { icon: QuestionCircleOutlined, label: 'Other', color: 'default' }
};

// ==============================|| INFO ROW ||============================== //

function InfoRow({ icon: Icon, label, value, color }) {
  const theme = useTheme();
  
  if (!value) return null;
  
  return (
    <Stack direction="row" spacing={1} alignItems="flex-start">
      <Icon style={{ fontSize: 14, color: color || theme.palette.text.secondary, marginTop: 2 }} />
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
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  color: PropTypes.string
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
  
  // Get step type config
  const stepTypeConfig = STEP_TYPE_CONFIG[step.step_type] || STEP_TYPE_CONFIG.OTHER;
  const StepTypeIcon = stepTypeConfig.icon;
  
  // Truncate description for preview
  const descriptionPreview = step.description
    ? step.description.length > 120
      ? `${step.description.substring(0, 120)}...`
      : step.description
    : null;

  // Format scheduled date/time
  const formatScheduled = () => {
    if (!step.scheduled_date) return null;
    const date = new Date(step.scheduled_date);
    const options = { weekday: 'short', month: 'short', day: 'numeric' };
    const formatted = date.toLocaleDateString(undefined, options);
    
    if (step.scheduled_time) {
      return `${formatted} at ${step.scheduled_time.substring(0, 5)}`;
    }
    return formatted;
  };

  const scheduledDisplay = formatScheduled();
  const isPastDue = step.scheduled_date && 
    new Date(step.scheduled_date) < new Date() && 
    step.status !== 'VALIDATED' && 
    step.status !== 'REJECTED';
  
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
          maxWidth: 340,
          minWidth: 280,
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
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mt: 0.5 }}>
            {/* Step Type Chip */}
            <Chip
              size="small"
              icon={<StepTypeIcon style={{ fontSize: 12 }} />}
              label={stepTypeConfig.label}
              color={stepTypeConfig.color}
              variant="outlined"
              sx={{ height: 22, fontSize: '0.7rem' }}
            />
            {/* Stage Chip */}
            <Chip
              size="small"
              label={STAGE_LABELS[step.stage] || step.stage}
              variant="outlined"
              sx={{ height: 20, fontSize: '0.7rem' }}
            />
            {/* Status Chip */}
            <Chip
              size="small"
              label={statusConfig?.label || step.status}
              color={statusConfig?.color || 'default'}
              sx={{ height: 20, fontSize: '0.7rem' }}
            />
          </Stack>
        </Box>

        {/* Scheduled Date (prominent) */}
        {scheduledDisplay && (
          <>
            <Divider />
            <Box
              sx={{
                p: 1,
                borderRadius: 1,
                bgcolor: isPastDue 
                  ? alpha(theme.palette.error.main, 0.1)
                  : alpha(theme.palette.primary.main, 0.08)
              }}
            >
              <Stack direction="row" spacing={1} alignItems="center">
                <CalendarOutlined 
                  style={{ 
                    fontSize: 16, 
                    color: isPastDue ? theme.palette.error.main : theme.palette.primary.main 
                  }} 
                />
                <Box>
                  <Typography 
                    variant="caption" 
                    color={isPastDue ? 'error.main' : 'text.secondary'}
                    display="block"
                  >
                    {isPastDue ? 'Overdue' : 'Scheduled'}
                  </Typography>
                  <Typography 
                    variant="body2" 
                    fontWeight={600}
                    color={isPastDue ? 'error.main' : 'primary.main'}
                  >
                    {scheduledDisplay}
                  </Typography>
                </Box>
              </Stack>
            </Box>
          </>
        )}
        
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

        {/* Departments */}
        {step.departments_list && step.departments_list.length > 0 && (
          <>
            <Divider />
            <Box>
              <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mb: 0.5 }}>
                <BankOutlined style={{ fontSize: 12, color: theme.palette.text.secondary }} />
                <Typography variant="caption" color="text.secondary">
                  Departments
                </Typography>
              </Stack>
              <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                {step.departments_list.slice(0, 3).map((dept) => (
                  <Chip
                    key={dept.id}
                    label={dept.name}
                    size="small"
                    variant="outlined"
                    sx={{ height: 20, fontSize: '0.65rem' }}
                  />
                ))}
                {step.departments_list.length > 3 && (
                  <Chip
                    label={`+${step.departments_list.length - 3}`}
                    size="small"
                    sx={{ height: 20, fontSize: '0.65rem' }}
                  />
                )}
              </Stack>
            </Box>
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
    step_type: PropTypes.string,
    stakeholder: PropTypes.string,
    description: PropTypes.string,
    goal: PropTypes.string,
    expected_days: PropTypes.number,
    contacts_count: PropTypes.number,
    scheduled_date: PropTypes.string,
    scheduled_time: PropTypes.string,
    departments_list: PropTypes.array,
    criterias: PropTypes.array
  }),
  anchorEl: PropTypes.any,
  onClose: PropTypes.func.isRequired,
  statusConfig: PropTypes.shape({
    color: PropTypes.string,
    label: PropTypes.string
  })
};