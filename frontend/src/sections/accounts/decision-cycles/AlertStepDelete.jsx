// frontend/src/sections/accounts/decision-cycles/AlertStepDelete.jsx
/**
 * Alert Step Delete Component
 * 
 * Confirmation dialog for deleting a decision step.
 * 
 * Features:
 * - Warning message with step name
 * - Confirm/Cancel actions
 * - Loading state during deletion
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
import { deleteDecisionStep } from 'api/accounts/decisionCycles';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// ==============================|| ALERT STEP DELETE ||============================== //

/**
 * AlertStepDelete Component
 * 
 * @param {boolean} open - Dialog open state
 * @param {Function} onClose - Close dialog callback
 * @param {Object} step - Step to delete
 * @param {string} cycleId - Parent cycle UUID (for revalidation)
 * @param {Function} onSuccess - Success callback after deletion
 */
export default function AlertStepDelete({ 
  open, 
  onClose, 
  step, 
  cycleId,
  onSuccess 
}) {
  const [deleting, setDeleting] = useState(false);
  
  const handleDelete = async () => {
    if (!step?.id) return;
    
    setDeleting(true);
    
    try {
      const result = await deleteDecisionStep(step.id, cycleId);
      
      if (result.success) {
        displaySuccessSnackbar('Decision step deleted successfully');
        onSuccess?.(step);
        onClose();
      } else {
        displayErrorSnackbar(result.error || 'Failed to delete step');
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
      aria-labelledby="alert-step-delete-title"
      aria-describedby="alert-step-delete-description"
    >
      <DialogTitle id="alert-step-delete-title">
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <WarningFilled style={{ fontSize: 24, color: '#faad14' }} />
          <Typography variant="h5">Delete Step</Typography>
        </Box>
      </DialogTitle>
      
      <DialogContent>
        <DialogContentText id="alert-step-delete-description">
          Are you sure you want to delete the step{' '}
          <Typography component="span" fontWeight={600} color="text.primary">
            &quot;{step?.name}&quot;
          </Typography>
          ?
        </DialogContentText>
        <DialogContentText sx={{ mt: 1.5, color: 'text.secondary' }}>
          This action cannot be undone. All associated data including contacts, 
          criterias, and metrics will be permanently removed.
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
          {deleting ? 'Deleting...' : 'Delete Step'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

AlertStepDelete.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  step: PropTypes.shape({
    id: PropTypes.string,
    name: PropTypes.string
  }),
  cycleId: PropTypes.string,
  onSuccess: PropTypes.func
};