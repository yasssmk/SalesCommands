// frontend/src/sections/territories/AlertTerritoryDelete.jsx

import PropTypes from 'prop-types';
import { useState } from 'react';

// material-ui
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';

// project imports
import { displaySuccessSnackbar, displayErrorSnackbar } from 'utils/displayError';

// api
import { deleteTerritory } from 'api/territories/territories';

// ==============================|| ALERT TERRITORY DELETE ||============================== //

/**
 * AlertTerritoryDelete - Confirmation dialog for territory deletion
 * 
 * Features:
 * - Prevents deletion of system territories
 * - Shows territory name for confirmation
 * - Loading state during deletion
 * 
 * @param {Object} territory - Territory to delete
 * @param {boolean} open - Dialog open state
 * @param {Function} closeModal - Function to close the modal
 */
function AlertTerritoryDelete({ territory, open, closeModal }) {
  const [isDeleting, setIsDeleting] = useState(false);

  // ==============================|| HANDLERS ||============================== //

  const handleDelete = async () => {
    if (!territory?.id) {
      displayErrorSnackbar('Invalid territory');
      return;
    }

    setIsDeleting(true);
    
    try {
      const result = await deleteTerritory(territory.id);
      
      if (result.success) {
        displaySuccessSnackbar('Territory deleted successfully');
        closeModal?.();
      } else {
        displayErrorSnackbar(result);
      }
    } catch (err) {
      displayErrorSnackbar('An unexpected error occurred');
      console.error('Delete territory error:', err);
    } finally {
      setIsDeleting(false);
    }
  };

  // ==============================|| RENDER ||============================== //

  // System territories cannot be deleted
  if (territory?.is_system) {
    return (
      <Dialog open={open} onClose={closeModal} maxWidth="sm" fullWidth>
        <DialogTitle>Cannot Delete Territory</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mt: 1 }}>
            System territories cannot be deleted. The territory "{territory.name}" is a built-in system territory.
          </Alert>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={closeModal} variant="contained">
            Close
          </Button>
        </DialogActions>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onClose={closeModal} maxWidth="sm" fullWidth>
      <DialogTitle>Delete Territory</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <DialogContentText>
            Are you sure you want to delete this territory?
          </DialogContentText>
          
          <Alert severity="error" variant="outlined">
            <Typography variant="subtitle1" fontWeight={600}>
              {territory?.name}
            </Typography>
            {territory?.description && (
              <Typography variant="body2" color="text.secondary">
                {territory.description}
              </Typography>
            )}
          </Alert>
          
          <Typography variant="body2" color="text.secondary">
            This action cannot be undone. The territory will be permanently removed.
          </Typography>
        </Stack>
      </DialogContent>
      <DialogActions sx={{ p: 2.5 }}>
        <Button onClick={closeModal} color="inherit" disabled={isDeleting}>
          Cancel
        </Button>
        <Button 
          onClick={handleDelete} 
          color="error" 
          variant="contained"
          disabled={isDeleting}
        >
          {isDeleting ? 'Deleting...' : 'Delete'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

AlertTerritoryDelete.propTypes = {
  territory: PropTypes.object,
  open: PropTypes.bool.isRequired,
  closeModal: PropTypes.func.isRequired
};

export default AlertTerritoryDelete;