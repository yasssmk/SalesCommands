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
import { bulkDeleteUsers } from 'api/admin/users';
import { openSnackbar } from 'api/snackbar';

// assets
import DeleteFilled from '@ant-design/icons/DeleteFilled';

// ==============================|| User - BULK DELETE ||============================== //

export default function AlertUserBulkDelete({ selectedIds, open, handleClose, onDeleteComplete }) {
  const [deleting, setDeleting] = useState(false);
  const userCount = selectedIds?.length || 0;

  const deletehandler = async () => {
    try {
      setDeleting(true);
      const res = await bulkDeleteUsers(selectedIds, 'partial');
      
      if (res?.success) {
        openSnackbar({
          open: true,
          message: `${userCount} user${userCount > 1 ? 's' : ''} deleted successfully`,
          anchorOrigin: { vertical: 'top', horizontal: 'right' },
          variant: 'alert',
          alert: { color: 'success' }
        });
        handleClose?.();
        onDeleteComplete?.();
      } else {
        // ✅ CORRECTION: Extraire le message correctement
        // res.error peut être un objet {message, status, response}
        const errorMessage = res?.message || res?.error?.message || res?.error || 'Failed to delete users';
        const status = res?.status || res?.error?.status || 0;
        
        // Choix de la couleur: warning si 400, sinon error
        const color = status === 400 ? 'warning' : 'error';
        
        openSnackbar({
          open: true,
          message: String(errorMessage), // ✅ Toujours convertir en string
          anchorOrigin: { vertical: 'top', horizontal: 'right' },
          variant: 'alert',
          alert: { color }
        });
        // on NE ferme PAS la modal en cas d'erreur
      }
    } catch (err) {
      // ✅ Gestion sécurisée des erreurs JS
      const errorMessage = err?.message || err?.error?.message || String(err) || 'Unexpected error';
      
      openSnackbar({
        open: true,
        message: String(errorMessage),
        anchorOrigin: { vertical: 'top', horizontal: 'right' },
        variant: 'alert',
        alert: { color: 'error' }
      });
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
      aria-labelledby="bulk-delete-title"
      aria-describedby="bulk-delete-description"
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
                {userCount} user{userCount > 1 ? 's' : ''}{' '}
              </Typography>
              all tasks assigned to {userCount > 1 ? 'these users' : 'this user'} will also be deleted.
            </Typography>
            
            {/* ✅ Message de patience pour gros batch */}
            {userCount > 10 && (
              <Typography 
                variant="body2" 
                color="warning.main" 
                align="center"
                sx={{ mt: 2, fontStyle: 'italic' }}
              >
                ⏱️ Large batch deletion may take up to 30 seconds. Please be patient.
              </Typography>
            )}
          </Stack>

          <Stack direction="row" spacing={2} sx={{ width: 1 }}>
            <Button fullWidth onClick={handleClose} color="secondary" variant="outlined" disabled={deleting}>
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

AlertUserBulkDelete.propTypes = {
  selectedIds: PropTypes.array.isRequired,
  open: PropTypes.bool,
  handleClose: PropTypes.func,
  onDeleteComplete: PropTypes.func
};