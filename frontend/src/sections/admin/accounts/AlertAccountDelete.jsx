// frontend/src/sections/admin/accounts/AlertAccountDelete.jsx

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
import { deleteAccount } from 'api/admin/accounts';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// assets
import DeleteFilled from '@ant-design/icons/DeleteFilled';

// ==============================|| ACCOUNT - DELETE ||============================== //

/**
 * AlertAccountDelete Component
 * 
 * Confirmation dialog for single account deletion.
 * 
 * @param {Object} account - Account object to delete
 * @param {boolean} open - Dialog open state
 * @param {Function} handleClose - Function to close dialog
 */
export default function AlertAccountDelete({ account, open, handleClose }) {
  const [deleting, setDeleting] = useState(false);

  const deleteHandler = async () => {
    if (!account?.id) return;

    try {
      setDeleting(true);
      const result = await deleteAccount(account.id);

      if (result?.success) {
        displaySuccessSnackbar('Account deleted successfully');
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
      aria-labelledby="account-delete-title"
      aria-describedby="account-delete-description"
    >
      <DialogContent sx={{ mt: 2, my: 1 }}>
        <Stack alignItems="center" spacing={3.5}>
          <Avatar color="error" sx={{ width: 72, height: 72, fontSize: '1.75rem' }}>
            <DeleteFilled />
          </Avatar>

          <Stack spacing={2}>
            <Typography variant="h4" align="center">
              Are you sure you want to delete?
            </Typography>
            <Typography align="center">
              By deleting
              <Typography variant="subtitle1" component="span">
                {' '}
                &quot;{account?.company_name}&quot;{' '}
              </Typography>
              account, all associated data including contacts, opportunities, and activities will also be affected.
            </Typography>
          </Stack>

          <Stack direction="row" spacing={2} sx={{ width: 1 }}>
            <Button 
              fullWidth 
              onClick={handleClose} 
              color="secondary" 
              variant="outlined"
              disabled={deleting}
            >
              Cancel
            </Button>
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
          </Stack>
        </Stack>
      </DialogContent>
    </Dialog>
  );
}

AlertAccountDelete.propTypes = {
  account: PropTypes.shape({
    id: PropTypes.string,
    company_name: PropTypes.string
  }),
  open: PropTypes.bool,
  handleClose: PropTypes.func
};