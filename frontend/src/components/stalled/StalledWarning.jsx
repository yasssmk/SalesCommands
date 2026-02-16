// frontend/src/components/stalled/StalledWarning.jsx
/**
 * Stalled Warning Component
 * 
 * Displays a warning alert when a Decision Step is detected as stalled.
 * Shows reason, last activity info, and action buttons.
 * 
 * Stalled reasons (from backend):
 * - NO_ACTIVITY: No activities linked to this step
 * - NO_FUTURE_ACTIVITY: No future activities planned
 * - NO_NEXT_STEP: Last activity has no next step agreed
 * - EXPECTED_END_PASSED: Expected end date has passed
 * - WAITING_TOO_LONG: No activity in 7+ days
 */

'use client';

import PropTypes from 'prop-types';
import { useState } from 'react';

// MUI
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// Icons
import WarningOutlined from '@ant-design/icons/WarningOutlined';
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import CalendarOutlined from '@ant-design/icons/CalendarOutlined';
import PhoneOutlined from '@ant-design/icons/PhoneOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';

// Date formatting
import { formatDistanceToNow, format } from 'date-fns';

// ==============================|| STALLED REASON CONFIG ||============================== //

/**
 * Stalled reason config.
 * NO_NEXT_STEP removed — next step tracking is now derived from
 * activity sequence, not explicit agreement fields.
 */
const STALLED_REASON_CONFIG = {
  NO_ACTIVITY: {
    title: 'No Activities Linked',
    description: 'This step has no activities associated with it.',
    severity: 'warning'
  },
  NO_FUTURE_ACTIVITY: {
    title: 'No Planned Activities',
    description: 'There are no future activities scheduled for this step.',
    severity: 'warning'
  },
  EXPECTED_END_PASSED: {
    title: 'Expected End Date Passed',
    description: 'This step is past its expected completion date.',
    severity: 'error'
  },
  WAITING_TOO_LONG: {
    title: 'Waiting Too Long',
    description: 'No activity has occurred in the last 7+ days.',
    severity: 'warning'
  }
};

// ==============================|| STALLED WARNING ||============================== //

/**
 * StalledWarning Component
 * 
 * @param {boolean} isStalled - Whether the step is stalled
 * @param {string} stalledReason - Reason code from backend
 * @param {object} stalledDetails - Detailed stalled info from backend
 * @param {function} onScheduleCall - Callback for "Schedule Call" action
 * @param {function} onScheduleMeeting - Callback for "Schedule Meeting" action
 * @param {function} onMarkValidated - Callback for "Mark as Validated" action
 * @param {boolean} dismissible - Whether the warning can be dismissed
 */
export default function StalledWarning({
  isStalled,
  stalledReason,
  stalledDetails,
  onScheduleCall,
  onScheduleMeeting,
  onMarkValidated,
  dismissible = true
}) {
  const [dismissed, setDismissed] = useState(false);

  // Don't render if not stalled or dismissed
  if (!isStalled || stalledReason === 'NONE' || dismissed) {
    return null;
  }

  // Get config for this reason
  const config = STALLED_REASON_CONFIG[stalledReason] || {
    title: 'Step Appears Stalled',
    description: 'This step may need attention.',
    severity: 'warning'
  };

  // Format dates from stalled details
  const lastActivityDate = stalledDetails?.last_activity_date;
  const daysSinceLastActivity = stalledDetails?.days_since_last_activity;
  const expectedEnd = stalledDetails?.expected_end;
  const hasFutureActivity = stalledDetails?.has_future_activity;

  return (
    <Collapse in={!dismissed}>
      <Alert
        severity={config.severity}
        icon={<WarningOutlined />}
        action={
          dismissible && (
            <IconButton
              aria-label="dismiss"
              color="inherit"
              size="small"
              onClick={() => setDismissed(true)}
            >
              <CloseOutlined />
            </IconButton>
          )
        }
        sx={{ mb: 2 }}
      >
        <AlertTitle sx={{ fontWeight: 600 }}>
          ⚠️ {config.title}
        </AlertTitle>
        
        <Typography variant="body2" sx={{ mb: 1.5 }}>
          {config.description}
        </Typography>

        {/* Stalled Details */}
        <Stack spacing={0.5} sx={{ mb: 2 }}>
          {lastActivityDate && (
            <Typography variant="caption" color="text.secondary">
              📅 Last activity: {formatDistanceToNow(new Date(lastActivityDate), { addSuffix: true })}
              {daysSinceLastActivity !== null && ` (${daysSinceLastActivity} days ago)`}
            </Typography>
          )}
          
          {expectedEnd && (
            <Typography variant="caption" color="text.secondary">
              ⏰ Expected end: {format(new Date(expectedEnd), 'MMM d, yyyy')}
              {new Date(expectedEnd) < new Date() && (
                <Typography component="span" variant="caption" color="error.main" sx={{ ml: 0.5 }}>
                  (overdue)
                </Typography>
              )}
            </Typography>
          )}
          
          {hasFutureActivity === false && (
            <Typography variant="caption" color="text.secondary">
              🔴 No future activities planned
            </Typography>
          )}
        </Stack>

        {/* Action Buttons */}
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {onScheduleCall && (
            <Button
              size="small"
              variant="outlined"
              startIcon={<PhoneOutlined />}
              onClick={onScheduleCall}
              sx={{ 
                borderColor: 'inherit', 
                color: 'inherit',
                '&:hover': { borderColor: 'inherit', bgcolor: 'action.hover' }
              }}
            >
              Schedule Call
            </Button>
          )}
          
          {onScheduleMeeting && (
            <Button
              size="small"
              variant="outlined"
              startIcon={<TeamOutlined />}
              onClick={onScheduleMeeting}
              sx={{ 
                borderColor: 'inherit', 
                color: 'inherit',
                '&:hover': { borderColor: 'inherit', bgcolor: 'action.hover' }
              }}
            >
              Schedule Meeting
            </Button>
          )}
          
          {onMarkValidated && (
            <Button
              size="small"
              variant="outlined"
              startIcon={<CheckCircleOutlined />}
              onClick={onMarkValidated}
              sx={{ 
                borderColor: 'inherit', 
                color: 'inherit',
                '&:hover': { borderColor: 'inherit', bgcolor: 'action.hover' }
              }}
            >
              Mark as Validated
            </Button>
          )}
        </Stack>
      </Alert>
    </Collapse>
  );
}

StalledWarning.propTypes = {
  isStalled: PropTypes.bool,
  stalledReason: PropTypes.oneOf([
    'NONE',
    'NO_ACTIVITY',
    'NO_FUTURE_ACTIVITY',
    'EXPECTED_END_PASSED',
    'WAITING_TOO_LONG'
  ]),
  stalledDetails: PropTypes.shape({
    reason: PropTypes.string,
    reason_display: PropTypes.string,
    last_activity_date: PropTypes.string,
    days_since_last_activity: PropTypes.number,
    has_future_activity: PropTypes.bool,
    expected_end: PropTypes.string
  }),
  onScheduleCall: PropTypes.func,
  onScheduleMeeting: PropTypes.func,
  onMarkValidated: PropTypes.func,
  dismissible: PropTypes.bool
};