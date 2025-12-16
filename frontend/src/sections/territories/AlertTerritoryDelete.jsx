// frontend/src/sections/territories/AlertTerritoryDelete.jsx

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
import { deleteTerritory } from 'api/territories/territories';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// assets
import DeleteFilled from '@ant-design/icons/DeleteFilled';

// ==============================|| TERRITORY - DELETE ||============================== //

/**
 * AlertTerritoryDelete Component
 * 
 * Confirmation dialog for single territory deletion.
 * Follows AlertAccountDelete pattern for consistency.
 * 
 * @param {Object} territory - Territory object to delete
 * @param {boolean} open - Dialog open state
 * @param {Function} handleClose - Function to close dialog
 */
export default function AlertTerritoryDelete({ territory, open, handleClose }) {
  const [deleting, setDeleting] = useState(false);

  // Check if territory is system (cannot be deleted)
  const isSystem = territory?.is_system === true;

  const deleteHandler = async () => {
    if (!territory?.id || isSystem) return;

    try {
      setDeleting(true);
      const result = await deleteTerritory(territory.id);

      if (result?.success) {
        displaySuccessSnackbar('Territory deleted successfully');
        handleClose?.();
      } else {
        displayErrorSnackbar(result);
        // Do NOT close modal on error
      }
    } catch (err) {
      displayErrorSnackbar(err);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      keepMounted
      TransitionComponent={PopupTransition}
      maxWidth="xs"
      aria-labelledby="territory-delete-title"
      aria-describedby="territory-delete-description"
    >
      <DialogContent sx={{ mt: 2, my: 1 }}>
        <Stack alignItems="center" spacing={3.5}>
          <Avatar color="error" sx={{ width: 72, height: 72, fontSize: '1.75rem' }}>
            <DeleteFilled />
          </Avatar>

          <Stack spacing={2}>
            <Typography variant="h4" align="center">
              {isSystem ? 'Cannot Delete Territory' : 'Are you sure you want to delete?'}
            </Typography>
            
            {isSystem ? (
              <Typography align="center" color="text.secondary">
                System territories cannot be deleted. The territory
                <Typography variant="subtitle1" component="span">
                  {' '}&quot;{territory?.name}&quot;{' '}
                </Typography>
                is a built-in system territory.
              </Typography>
            ) : (
              <Typography align="center">
                By deleting
                <Typography variant="subtitle1" component="span">
                  {' '}&quot;{territory?.name}&quot;{' '}
                </Typography>
                territory, this action cannot be undone.
              </Typography>
            )}
          </Stack>

          <Stack direction="row" spacing={2} sx={{ width: 1 }}>
            <Button 
              fullWidth 
              onClick={handleClose} 
              color="secondary" 
              variant="outlined"
              disabled={deleting}
            >
              {isSystem ? 'Close' : 'Cancel'}
            </Button>
            {!isSystem && (
              <Button 
                fullWidth 
                color="error" 
                variant="contained" 
                onClick={deleteHandler} 
                autoFocus 
                disabled={deleting}
              >
                {deleting ? 'Deleting...' : 'Delete'}
              </Button>
            )}
          </Stack>
        </Stack>
      </DialogContent>
    </Dialog>
  );
}

AlertTerritoryDelete.propTypes = {
  territory: PropTypes.shape({
    id: PropTypes.string,
    name: PropTypes.string,
    is_system: PropTypes.bool
  }),
  open: PropTypes.bool,
  handleClose: PropTypes.func
};