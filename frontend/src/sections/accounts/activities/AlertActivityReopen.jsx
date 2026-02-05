// frontend/src/sections/accounts/activities/AlertActivityReopen.jsx
/**
 * Alert Activity Reopen Component
 * 
 * Confirmation dialog for reopening a completed or cancelled activity.
 * Follows AlertContactDelete / AlertTerritoryDelete standard pattern.
 */

'use client';

import PropTypes from 'prop-types';
import { useState } from 'react';

// material-ui
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogContent from '@mui/material/DialogContent';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project imports
import Avatar from 'components/@extended/Avatar';
import { PopupTransition } from 'components/@extended/Transitions';
import { reopenActivity, ACTIVITY_STATUS_LABELS } from 'api/accounts/activities';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// assets
import UndoOutlined from '@ant-design/icons/UndoOutlined';

// ==============================|| ACTIVITY - REOPEN ||============================== //

/**
 * AlertActivityReopen Component
 * 
 * @param {Object} activity - Activity object to reopen
 * @param {boolean} open - Dialog open state
 * @param {Function} handleClose - Function to close dialog
 * @param {Function} onSuccess - Optional callback after successful reopen
 */
export default function AlertActivityReopen({ activity, open, handleClose, onSuccess }) {
  const [reopening, setReopening] = useState(false);

  const reopenHandler = async () => {
    if (!activity?.id) return;

    try {
      setReopening(true);
      const result = await reopenActivity(activity.id, { status: 'PLANNED' });

      if (result.success) {
        displaySuccessSnackbar('Activity reopened successfully');
        handleClose?.();
        onSuccess?.(result.data);
      } else {
        displayErrorSnackbar({
          message: result.error || 'Failed to reopen activity',
          status: result.status
        });
      }
    } catch (err) {
      displayErrorSnackbar({
        message: err?.message || 'An unexpected error occurred',
        status: 500
      });
    } finally {
      setReopening(false);
    }
  };

  // Don't render if no activity
  if (!activity) return null;

  const activityTitle = activity.title || 'this activity';
  const currentStatus = ACTIVITY_STATUS_LABELS[activity.status] || activity.status;

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      keepMounted
      TransitionComponent={PopupTransition}
      maxWidth="xs"
      aria-labelledby="activity-reopen-title"
      aria-describedby="activity-reopen-description"
    >
      <DialogContent sx={{ mt: 2, my: 1 }}>
        <Stack alignItems="center" spacing={3.5}>
          <Avatar
            color="primary"
            sx={{
              width: 72,
              height: 72,
              fontSize: '1.75rem'
            }}
          >
            <UndoOutlined />
          </Avatar>

          <Stack spacing={2}>
            <Typography variant="h4" align="center">
              Reopen this activity?
            </Typography>
            <Typography align="center">
              The activity{' '}
              <Typography variant="subtitle1" component="span">
                &quot;{activityTitle}&quot;
              </Typography>
              {' '}is currently <strong>{currentStatus}</strong>. Reopening it will set the status back to Planned and clear the outcome.
            </Typography>
          </Stack>

          <Stack direction="row" spacing={2} sx={{ width: 1 }}>
            <Button
              fullWidth
              onClick={handleClose}
              color="secondary"
              variant="outlined"
              disabled={reopening}
            >
              Cancel
            </Button>
            <Button
              fullWidth
              color="primary"
              variant="contained"
              onClick={reopenHandler}
              disabled={reopening}
            >
              {reopening ? 'Reopening...' : 'Reopen Activity'}
            </Button>
          </Stack>
        </Stack>
      </DialogContent>
    </Dialog>
  );
}

AlertActivityReopen.propTypes = {
  activity: PropTypes.shape({
    id: PropTypes.string,
    title: PropTypes.string,
    status: PropTypes.string
  }),
  open: PropTypes.bool.isRequired,
  handleClose: PropTypes.func.isRequired,
  onSuccess: PropTypes.func
};