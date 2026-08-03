// frontend/src/sections/admin/users/DeactivateUserDialog.jsx

import PropTypes from 'prop-types';
import { useState } from 'react';

// material-ui
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Divider from '@mui/material/Divider';

// project imports
import { PopupTransition } from 'components/@extended/Transitions';
import SuccessorPicker from './SuccessorPicker';
import { updateUser } from 'api/admin/users';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// ==============================|| User - DEACTIVATE (with successor) ||============================== //

export default function DeactivateUserDialog({ user, open, handleClose, onDone }) {
  const [successor, setSuccessor] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const close = () => {
    setSuccessor(null);
    handleClose?.();
  };

  const handleConfirm = async () => {
    if (!successor?.id || !user?.id) return;
    try {
      setSubmitting(true);
      const res = await updateUser(user.id, {
        is_active: false,
        successor_id: String(successor.id)
      });
      if (res?.success) {
        displaySuccessSnackbar('User deactivated and work transferred');
        onDone?.();
        close();
      } else {
        displayErrorSnackbar(res);
      }
    } catch (err) {
      displayErrorSnackbar(err);
    } finally {
      setSubmitting(false);
    }
  };

  const name = user ? `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.email : '';

  return (
    <Dialog
      open={open}
      onClose={close}
      keepMounted
      TransitionComponent={PopupTransition}
      maxWidth="sm"
      fullWidth
      aria-labelledby="user-deactivate-title"
    >
      <DialogTitle id="user-deactivate-title">
        {name ? `Deactivate ${name}` : 'Deactivate user'}
      </DialogTitle>
      <Divider />
      <DialogContent sx={{ p: 2.5 }}>
        {open && user ? (
          <SuccessorPicker
            targetUser={user}
            value={successor}
            onChange={(event, newValue) => setSuccessor(newValue)}
            disabled={submitting}
          />
        ) : null}
      </DialogContent>
      <Divider />
      <DialogActions sx={{ p: 2.5 }}>
        <Button color="secondary" onClick={close} disabled={submitting}>
          Cancel
        </Button>
        <Button
          color="error"
          variant="contained"
          onClick={handleConfirm}
          disabled={submitting || !successor?.id}
        >
          {submitting ? 'Deactivating…' : 'Deactivate & transfer'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

DeactivateUserDialog.propTypes = {
  user: PropTypes.object,
  open: PropTypes.bool,
  handleClose: PropTypes.func,
  onDone: PropTypes.func
};
