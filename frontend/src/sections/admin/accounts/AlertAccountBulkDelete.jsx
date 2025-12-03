// frontend/src/sections/admin/accounts/AlertAccountBulkDelete.jsx

import PropTypes from 'prop-types';
import { useState, useCallback } from 'react';

// material-ui
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogContent from '@mui/material/DialogContent';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project imports
import Avatar from 'components/@extended/Avatar';
import { PopupTransition } from 'components/@extended/Transitions';
import BulkOperationSyncDialog from 'components/bulk/BulkOperationSyncDialog';
import { bulkDeleteAccounts } from 'api/admin/accounts';
import { displayErrorSnackbar, displaySuccessSnackbar, displayWarningSnackbar } from 'utils/displayError';
import { handleBulkError } from 'utils/bulkErrorHandler';
import { useBulkOperationSync } from 'hooks/useBulkOperationSync';

// assets
import DeleteFilled from '@ant-design/icons/DeleteFilled';

// ==============================|| ACCOUNT - BULK DELETE ||============================== //

export default function AlertAccountBulkDelete({ selectedIds, open, handleClose, onDeleteComplete }) {
  const [deleting, setDeleting] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [hadTimeout, setHadTimeout] = useState(false);
  
  const accountCount = selectedIds?.length || 0;

  const handleSyncComplete = useCallback(() => {
    if (hadTimeout) {
      displaySuccessSnackbar(
        `${accountCount} account${accountCount > 1 ? 's' : ''} deleted successfully`
      );
    }
    
    setProcessing(false);
    handleClose?.();
    onDeleteComplete?.();
    setHadTimeout(false);
  }, [hadTimeout, accountCount, handleClose, onDeleteComplete]);

  const { syncing, syncAttempt, onSyncProgress, onSyncComplete } = useBulkOperationSync({
    onComplete: handleSyncComplete,
    closeDelay: 300
  });

  const isProcessing = deleting || processing || syncing;

  const deleteHandler = async () => {
    let apiError = null;
    
    try {
      setDeleting(true);
      
      const res = await bulkDeleteAccounts(
        selectedIds,
        'partial',
        onSyncProgress,
        onSyncComplete
      );

      if (res?.data?.__is202) {
        console.log('[AlertAccountBulkDelete] 202 Accepted → entering processing state');
        setProcessing(true);
        return;
      }
      
      // Store the error if res is not success
      if (res && !res.success && !res.isTimeout) {
        apiError = res;
      }
      
      if (res?.success === true) {
        // Succès immédiat (pas de timeout)
        displaySuccessSnackbar(
          `${accountCount} account${accountCount > 1 ? 's' : ''} deleted successfully`
        );
        
        // Fermer immédiatement si pas de sync
        if (!isProcessing) {
          handleClose?.();
          onDeleteComplete?.();
        }
      } else if (res?.isPending) {
        const pendingMessage =
          res.message ||
          'Operation still in progress. It will complete in the background.';

        displayWarningSnackbar(pendingMessage);

        if (!isProcessing) {
          handleClose?.();
          onDeleteComplete?.();
        }
        
      } else if (res?.isTimeout) {
        console.log('[AlertAccountBulkDelete] Timeout detected, sync will start');
        setHadTimeout(true);
        setProcessing(true);
      } else {
        // All errors (partial 1-99% or total 0%) handled by handleBulkError
        handleBulkError(res, apiError, {
          onComplete: () => {
            handleClose?.();
            onDeleteComplete?.();
          }
        });
      }
    } catch (err) {
      console.error('[AlertAccountBulkDelete] Exception:', err);
      
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
        {isProcessing ? (
          <BulkOperationSyncDialog 
            attempt={syncAttempt}
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
                  {accountCount} account{accountCount > 1 ? 's' : ''}{' '}
                </Typography>
                all associated data including contacts, opportunities, and activities will also be deleted.
              </Typography>
              
              {accountCount > 10 && (
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
                onClick={deleteHandler} 
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

AlertAccountBulkDelete.propTypes = {
  selectedIds: PropTypes.array.isRequired,
  open: PropTypes.bool,
  handleClose: PropTypes.func,
  onDeleteComplete: PropTypes.func
};