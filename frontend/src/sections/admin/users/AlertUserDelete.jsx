import PropTypes from 'prop-types';
import { useState } from 'react';
// material-ui
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogContent from '@mui/material/DialogContent';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project import
import Avatar from 'components/@extended/Avatar';
import { PopupTransition } from 'components/@extended/Transitions';

import { deleteUser } from 'api/admin/users';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// assets
import DeleteFilled from '@ant-design/icons/DeleteFilled';

// ==============================|| User - DELETE ||============================== //

export default function AlertUserDelete({ id, title, open, handleClose }) {
  const [deleting, setDeleting] = useState(false);

  const deletehandler = async () => {
    try {
      setDeleting(true);
      const res = await deleteUser(id);

      if (res?.success) {
        displaySuccessSnackbar('User deleted successfully');
        handleClose?.();
      } else {
        // Choix de la couleur: warning si 400, sinon error
        displayErrorSnackbar(res);
        // on NE ferme PAS la modal en cas d’erreur
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
      aria-labelledby="column-delete-title"
      aria-describedby="column-delete-description"
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
                &quot;{title}&quot;{' '}
              </Typography>
              user, all task assigned to that user will also be deleted.
            </Typography>
          </Stack>

          <Stack direction="row" spacing={2} sx={{ width: 1 }}>
            <Button fullWidth onClick={handleClose} color="secondary" variant="outlined">
              Cancel
            </Button>
            <Button fullWidth color="error" variant="contained" onClick={deletehandler} autoFocus disabled={deleting}>
              {deleting ? 'Deleting...' : 'Delete'}
            </Button>
          </Stack>
        </Stack>
      </DialogContent>
    </Dialog>
  );
}

AlertUserDelete.propTypes = { id: PropTypes.number, title: PropTypes.string, open: PropTypes.bool, handleClose: PropTypes.func };


