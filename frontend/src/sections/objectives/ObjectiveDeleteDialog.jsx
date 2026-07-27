// frontend/src/sections/objectives/ObjectiveDeleteDialog.jsx
//
// Confirmation dialog before deleting an objective. Mirrors the repo's
// Alert*Delete pattern — a confirm step, never a silent delete.

import PropTypes from 'prop-types';
import { useState } from 'react';

import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';

import { deleteObjective } from 'api/objectives/objectives';
import { metricLabel } from './metricLabels';
import { displaySuccessSnackbar, displayErrorSnackbar } from 'utils/displayError';

export default function ObjectiveDeleteDialog({ open, objective, closeDialog }) {
  const [deleting, setDeleting] = useState(false);

  const onConfirm = async () => {
    if (!objective?.id) return;
    setDeleting(true);
    try {
      const result = await deleteObjective(objective.id);
      if (result.success) {
        displaySuccessSnackbar('Objective deleted');
        closeDialog?.();
      } else {
        displayErrorSnackbar(result.error || 'Could not delete objective');
      }
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Dialog open={open} onClose={closeDialog} maxWidth="xs" fullWidth>
      <DialogTitle>Delete objective</DialogTitle>
      <DialogContent>
        <DialogContentText>
          Delete the {objective ? metricLabel(objective.metric) : ''} objective? This cannot be undone.
        </DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button color="secondary" onClick={closeDialog} disabled={deleting}>
          Cancel
        </Button>
        <Button color="error" variant="contained" onClick={onConfirm} disabled={deleting}>
          Delete
        </Button>
      </DialogActions>
    </Dialog>
  );
}

ObjectiveDeleteDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  objective: PropTypes.object,
  closeDialog: PropTypes.func.isRequired,
};
