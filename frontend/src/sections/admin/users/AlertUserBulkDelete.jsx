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
import BulkOperationSyncDialog from 'components/bulk/BulkOperationSyncDialog';
import { bulkDeleteUsers } from 'api/admin/users';
import { openSnackbar } from 'api/snackbar';
import { useBulkOperationSync } from 'hooks/useBulkOperationSync';

// assets
import DeleteFilled from '@ant-design/icons/DeleteFilled';

// ==============================|| User - BULK DELETE ||============================== //

export default function AlertUserBulkDelete({ selectedIds, open, handleClose, onDeleteComplete }) {
  const [deleting, setDeleting] = useState(false);
  const [hadTimeout, setHadTimeout] = useState(false);  // ⭐ NOUVEAU: Flag pour tracker le timeout
  
  const userCount = selectedIds?.length || 0;

  // ⭐ Hook centralisé avec snackbar de succès après sync
  const { syncing, syncAttempt, onSyncProgress, onSyncComplete } = useBulkOperationSync({
    onComplete: () => {
      // ⭐ Si timeout, afficher le snackbar de succès maintenant
      if (hadTimeout) {
        openSnackbar({
          open: true,
          message: `${userCount} user${userCount > 1 ? 's' : ''} deleted successfully`,
          anchorOrigin: { vertical: 'top', horizontal: 'right' },
          variant: 'alert',
          alert: { color: 'success' }
        });
      }
      
      handleClose?.();
      onDeleteComplete?.();
      setHadTimeout(false);  // Reset le flag
    },
    closeDelay: 300
  });

  const deletehandler = async () => {
    try {
      setDeleting(true);
      
      const res = await bulkDeleteUsers(
        selectedIds, 
        'partial', 
        onSyncProgress,
        onSyncComplete
      );
      
      if (res?.success) {
        // ✅ Succès immédiat (pas de timeout)
        openSnackbar({
          open: true,
          message: `${userCount} user${userCount > 1 ? 's' : ''} deleted successfully`,
          anchorOrigin: { vertical: 'top', horizontal: 'right' },
          variant: 'alert',
          alert: { color: 'success' }
        });
        
        // Fermer immédiatement si pas de sync
        if (!syncing) {
          handleClose?.();
          onDeleteComplete?.();
        }
      } else {
        // ⭐ NOUVEAU: Vérifier si c'est un timeout
        const isTimeout = res?.isTimeout || res?.status === 408 || res?.status === 504;
        
        if (isTimeout) {
          // ⭐ Timeout détecté → Le sync va démarrer, ne pas afficher d'erreur
          console.log('[AlertUserBulkDelete] Timeout detected, sync will start');
          setHadTimeout(true);  // Flag pour afficher succès après sync
          // NE PAS afficher de snackbar d'erreur ici
        } else {
          // ❌ Erreur réelle (validation, permissions, etc.) → Afficher l'erreur
          const errorMessage = res?.message || res?.error?.message || res?.error || 'Failed to delete users';
          const status = res?.status || res?.error?.status || 0;
          const color = status === 400 ? 'warning' : 'error';
          
          openSnackbar({
            open: true,
            message: String(errorMessage),
            anchorOrigin: { vertical: 'top', horizontal: 'right' },
            variant: 'alert',
            alert: { color }
          });
          // NE PAS fermer la modal en cas d'erreur réelle
        }
      }
    } catch (err) {
      // ❌ Exception JS (pas un timeout)
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
      onClose={syncing ? undefined : handleClose}
      keepMounted
      TransitionComponent={PopupTransition}
      maxWidth="xs"
      aria-labelledby="bulk-delete-title"
      aria-describedby="bulk-delete-description"
    >
      <DialogContent sx={{ mt: 2, my: 1 }}>
        {syncing ? (
          <BulkOperationSyncDialog 
            attempt={syncAttempt}
            maxAttempts={3}
            operation="delete"
          />
        ) : (
          <Stack alignItems="center" spacing={3.5}>
            <Avatar 
              color="error" 
              sx={{ width: 72, height: 72, fontSize: '1.75rem' }}
            >
              <DeleteFilled />
            </Avatar>
            
            <Stack spacing={2} sx={{ width: 1 }}>
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
                onClick={deletehandler} 
                autoFocus 
                disabled={deleting}
              >
                {deleting ? 'Deleting...' : 'Delete'}
              </Button>
            </Stack>
          </Stack>
        )}
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