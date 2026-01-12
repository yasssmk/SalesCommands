// frontend/src/sections/accounts/activities/AlertActivityDelete.jsx
/**
 * Alert Activity Delete Component
 * 
 * Confirmation dialog for deleting an activity.
 * Follows AlertStepDelete pattern.
 */

'use client';

import PropTypes from 'prop-types';
import { useState } from 'react';

// material-ui
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import CircularProgress from '@mui/material/CircularProgress';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';

// icons
import WarningFilled from '@ant-design/icons/WarningFilled';

// project imports
import { deleteActivity } from 'api/accounts/activities';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// ==============================|| ALERT ACTIVITY DELETE ||============================== //

/**
 * AlertActivityDelete Component
 * 
 * @param {boolean} open - Dialog open state
 * @param {Function} onClose - Close dialog callback
 * @param {Object} activity - Activity to delete
 * @param {Function} onSuccess - Success callback after deletion
 */
export default function AlertActivityDelete({ 
  open, 
  onClose, 
  activity,
  onSuccess 
}) {
  const [deleting, setDeleting] = useState(false);
  
  const handleDelete = async () => {
    if (!activity?.id) return;
    
    setDeleting(true);
    
    try {
      const result = await deleteActivity(activity.id);
      
      if (result.success) {
        displaySuccessSnackbar('Activity deleted successfully');
        onSuccess?.(activity);
        onClose();
      } else {
        displayErrorSnackbar(result.error || 'Failed to delete activity');
      }
    } catch (error) {
      displayErrorSnackbar(error.message || 'An error occurred');
    } finally {
      setDeleting(false);
    }
  };
  
  const handleClose = () => {
    if (!deleting) {
      onClose();
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="xs"
      fullWidth
      aria-labelledby="alert-activity-delete-title"
      aria-describedby="alert-activity-delete-description"
    >
      <DialogTitle id="alert-activity-delete-title">
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <WarningFilled style={{ fontSize: 24, color: '#faad14' }} />
          <Typography variant="h5">Delete Activity</Typography>
        </Box>
      </DialogTitle>
      
      <DialogContent>
        <DialogContentText id="alert-activity-delete-description">
          Are you sure you want to delete the activity{' '}
          <Typography component="span" fontWeight={600} color="text.primary">
            &quot;{activity?.title}&quot;
          </Typography>
          ?
        </DialogContentText>
        <DialogContentText sx={{ mt: 1.5, color: 'text.secondary' }}>
          This action cannot be undone.
        </DialogContentText>
      </DialogContent>
      
      <DialogActions sx={{ px: 3, pb: 2.5 }}>
        <Button 
          color="secondary" 
          onClick={handleClose}
          disabled={deleting}
        >
          Cancel
        </Button>
        <Button
          variant="contained"
          color="error"
          onClick={handleDelete}
          disabled={deleting}
          startIcon={deleting ? <CircularProgress size={16} color="inherit" /> : null}
        >
          {deleting ? 'Deleting...' : 'Delete'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

AlertActivityDelete.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  activity: PropTypes.shape({
    id: PropTypes.string,
    title: PropTypes.string
  }),
  onSuccess: PropTypes.func
};