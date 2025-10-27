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
import {  displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';
import { showSnackbar } from 'utils/snackbar';
import { handleBulkError } from 'utils/bulkErrorHandler';
import { useBulkOperationSync } from 'hooks/useBulkOperationSync';

// assets
import DeleteFilled from '@ant-design/icons/DeleteFilled';

// ==============================|| HELPER ||============================== //

/**
 * Check if value is a plain object (not Array, not null)
 */
const isPlainObject = (obj) => {
  return obj !== null && 
         typeof obj === 'object' && 
         !Array.isArray(obj) &&
         Object.prototype.toString.call(obj) === '[object Object]';
};


// ==============================|| User - BULK DELETE ||============================== //

export default function AlertUserBulkDelete({ selectedIds, open, handleClose, onDeleteComplete }) {
  const [deleting, setDeleting] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [hadTimeout, setHadTimeout] = useState(false);  
  
  const userCount = selectedIds?.length || 0;

  // ⭐ Hook centralisé avec snackbar de succès après sync
  const { syncing, syncAttempt, onSyncProgress, onSyncComplete } = useBulkOperationSync({
    onComplete: () => {
      // ⭐ Si timeout, afficher le snackbar de succès maintenant
      if (hadTimeout) {
        displaySuccessSnackbar(
          `${userCount} user${userCount > 1 ? 's' : ''} deleted successfully`
        );
      }
      
      setProcessing(false);
      handleClose?.();
      onDeleteComplete?.();
      setHadTimeout(false);  // Reset le flag
    },
    closeDelay: 300
  });

  const isProcessing = deleting || processing || syncing;

 const deletehandler = async () => {
  let apiError = null;  // ⭐ Store original error for handleBulkError
  
  try {
    setDeleting(true);
    
    const res = await bulkDeleteUsers(
      selectedIds, 
      'partial', 
      onSyncProgress,
      onSyncComplete
    );

    if (res?.data?.__is202) {
       console.log('[AlertUserBulkDelete] 202 Accepted → entering processing state');
       setProcessing(true);
       return;
     }
    
    // ⭐ Store the error if res is not success
    if (res && !res.success && !res.isTimeout) {
      // Create an error-like object from the response for proper handling
      apiError = res;
    }
    
    if (res?.success === true) {
      // ✅ Succès immédiat (pas de timeout)
      displaySuccessSnackbar(
        `${userCount} user${userCount > 1 ? 's' : ''} deleted successfully`
      );
      
      // Fermer immédiatement si pas de sync
      if (!isProcessing) {
        handleClose?.();
        onDeleteComplete?.();
      }
    } else if (res?.isTimeout) {
      console.log('[AlertUserBulkDelete] Timeout detected, sync will start');
      setHadTimeout(true);  // Flag pour afficher succès après sync
      setProcessing(true);
    } else {
      // ⭐ All errors (partial 1-99% or total 0%) handled by handleBulkError
      handleBulkError(res, apiError, {
        onComplete: () => {
          handleClose?.();
          onDeleteComplete?.();
        }
      });
    }
  } catch (err) {
    console.error('[AlertUserBulkDelete] Exception:', err);
    
    // For unexpected exceptions
    displayErrorSnackbar(err);
    
    // Close modal
    handleClose?.();
    onDeleteComplete?.();

  } finally {
    setDeleting(false);
  }
};

  return (
    <Dialog
      open={open}
      onClose={isProcessing ? undefined : handleClose}
      keepMounted
      TransitionComponent={PopupTransition}
      maxWidth="xs"
      aria-labelledby="bulk-delete-title"
      aria-describedby="bulk-delete-description"
    >
      <DialogContent sx={{ mt: 2, my: 1 }}>
        {isProcessing ?  (
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
                disabled={isProcessing}
              >
                Cancel
              </Button>
              <Button 
                fullWidth 
                color="error" 
                variant="contained" 
                onClick={deletehandler} 
                autoFocus 
                disabled={isProcessing}
              >
                {isProcessing ? 'Processing...' : 'Delete'} 
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