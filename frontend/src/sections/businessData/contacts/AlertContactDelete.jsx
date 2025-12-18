// frontend/src/sections/businessData/contacts/AlertContactDelete.jsx

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
import { deleteContact } from 'api/businessData/contacts';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// assets
import DeleteFilled from '@ant-design/icons/DeleteFilled';

// ==============================|| CONTACT - DELETE ||============================== //

export default function AlertContactDelete({ contact, open, handleClose }) {
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    if (!contact?.id) return;

    try {
      setDeleting(true);
      const result = await deleteContact(contact.id);

      if (result.success) {
        displaySuccessSnackbar('Contact deleted successfully');
        handleClose();
      } else {
        displayErrorSnackbar({
          message: result.error || 'Failed to delete contact',
          status: result.status
        });
      }
    } catch (err) {
      displayErrorSnackbar({
        message: err?.message || 'An unexpected error occurred',
        status: 500
      });
    } finally {
      setDeleting(false);
    }
  };

  // Don't render if no contact
  if (!contact) return null;

  const contactName = `${contact.first_name || ''} ${contact.last_name || ''}`.trim() || 'this contact';

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      keepMounted
      TransitionComponent={PopupTransition}
      maxWidth="xs"
      aria-labelledby="contact-delete-title"
      aria-describedby="contact-delete-description"
    >
      <DialogContent sx={{ mt: 2, my: 1 }}>
        <Stack alignItems="center" spacing={3.5}>
          <Avatar
            color="error"
            sx={{
              width: 72,
              height: 72,
              fontSize: '1.75rem'
            }}
          >
            <DeleteFilled />
          </Avatar>

          <Stack spacing={2}>
            <Typography variant="h4" align="center">
              Are you sure you want to delete?
            </Typography>
            <Typography align="center">
              By deleting <strong>{contactName}</strong>, all associated data will be permanently removed.
              This action cannot be undone.
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
              onClick={handleDelete}
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

AlertContactDelete.propTypes = {
  contact: PropTypes.object,
  open: PropTypes.bool.isRequired,
  handleClose: PropTypes.func.isRequired
};