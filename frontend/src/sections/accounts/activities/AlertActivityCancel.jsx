// frontend/src/sections/accounts/activities/AlertActivityCancel.jsx
/**
 * Alert Activity Cancel Component
 * 
 * Confirmation dialog for cancelling an activity.
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
import { cancelActivity } from 'api/accounts/activities';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// assets
import StopFilled from '@ant-design/icons/StopFilled';

// ==============================|| ACTIVITY - CANCEL ||============================== //

/**
 * AlertActivityCancel Component
 * 
 * @param {Object} activity - Activity object to cancel
 * @param {boolean} open - Dialog open state
 * @param {Function} handleClose - Function to close dialog
 * @param {Function} onSuccess - Optional callback after successful cancellation
 */
export default function AlertActivityCancel({ activity, open, handleClose, onSuccess }) {
  const [cancelling, setCancelling] = useState(false);

  const cancelHandler = async () => {
    if (!activity?.id) return;

    try {
      setCancelling(true);
      const result = await cancelActivity(activity.id);

      if (result.success) {
        displaySuccessSnackbar('Activity cancelled successfully');
        handleClose?.();
        onSuccess?.(result.data);
      } else {
        displayErrorSnackbar({
          message: result.error || 'Failed to cancel activity',
          status: result.status
        });
      }
    } catch (err) {
      displayErrorSnackbar({
        message: err?.message || 'An unexpected error occurred',
        status: 500
      });
    } finally {
      setCancelling(false);
    }
  };

  // Don't render if no activity
  if (!activity) return null;

  const activityTitle = activity.title || 'this activity';

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      keepMounted
      TransitionComponent={PopupTransition}
      maxWidth="xs"
      aria-labelledby="activity-cancel-title"
      aria-describedby="activity-cancel-description"
    >
      <DialogContent sx={{ mt: 2, my: 1 }}>
        <Stack alignItems="center" spacing={3.5}>
          <Avatar
            color="warning"
            sx={{
              width: 72,
              height: 72,
              fontSize: '1.75rem'
            }}
          >
            <StopFilled />
          </Avatar>

          <Stack spacing={2}>
            <Typography variant="h4" align="center">
              Are you sure you want to cancel?
            </Typography>
            <Typography align="center">
              The activity{' '}
              <Typography variant="subtitle1" component="span">
                &quot;{activityTitle}&quot;
              </Typography>
              {' '}will be marked as cancelled. You can reopen it later if needed.
            </Typography>
          </Stack>

          <Stack direction="row" spacing={2} sx={{ width: 1 }}>
            <Button
              fullWidth
              onClick={handleClose}
              color="secondary"
              variant="outlined"
              disabled={cancelling}
            >
              Go Back
            </Button>
            <Button
              fullWidth
              color="warning"
              variant="contained"
              onClick={cancelHandler}
              disabled={cancelling}
            >
              {cancelling ? 'Cancelling...' : 'Cancel Activity'}
            </Button>
          </Stack>
        </Stack>
      </DialogContent>
    </Dialog>
  );
}

AlertActivityCancel.propTypes = {
  activity: PropTypes.shape({
    id: PropTypes.string,
    title: PropTypes.string
  }),
  open: PropTypes.bool.isRequired,
  handleClose: PropTypes.func.isRequired,
  onSuccess: PropTypes.func
};