// frontend/src/sections/businessData/contacts/AlertContactBulkDelete.jsx

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
import { bulkDeleteContacts } from 'api/businessData/contacts';
import { displayErrorSnackbar, displaySuccessSnackbar, displayWarningSnackbar } from 'utils/displayError';
import { handleBulkError } from 'utils/bulkErrorHandler';
import { useBulkOperationSync } from 'hooks/useBulkOperationSync';

// assets
import DeleteFilled from '@ant-design/icons/DeleteFilled';

// ==============================|| CONTACT - BULK DELETE ||============================== //

export default function AlertContactBulkDelete({ selectedIds, open, handleClose, onDeleteComplete }) {
  const [deleting, setDeleting] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [hadTimeout, setHadTimeout] = useState(false);
  
  const contactCount = selectedIds?.length || 0;

  const handleSyncComplete = useCallback(() => {
    if (hadTimeout) {
      displaySuccessSnackbar(
        `${contactCount} contact${contactCount > 1 ? 's' : ''} deleted successfully`
      );
    }
    
    setProcessing(false);
    handleClose?.();
    onDeleteComplete?.();
    setHadTimeout(false);
  }, [hadTimeout, contactCount, handleClose, onDeleteComplete]);

  const { syncing, syncAttempt, onSyncProgress, onSyncComplete } = useBulkOperationSync({
    onComplete: handleSyncComplete,
    closeDelay: 300
  });

  const isProcessing = deleting || processing || syncing;

  const deleteHandler = async () => {
    let apiError = null;
    
    try {
      setDeleting(true);
      
      const res = await bulkDeleteContacts(
        selectedIds,
        'partial',
        onSyncProgress,
        onSyncComplete
      );

      if (res?.data?.__is202) {
        console.log('[AlertContactBulkDelete] 202 Accepted → entering processing state');
        setProcessing(true);
        return;
      }
      
      // Store the error if res is not success
      if (res && !res.success && !res.isTimeout) {
        apiError = res;
      }
      
      if (res?.success === true) {
        // Immediate success (no timeout)
        displaySuccessSnackbar(
          `${contactCount} contact${contactCount > 1 ? 's' : ''} deleted successfully`
        );
        
        // Close immediately if no sync
        if (!isProcessing) {
          handleClose?.();
          onDeleteComplete?.();
        }
        return;
      }

      if (res?.isTimeout) {
        console.log('[AlertContactBulkDelete] Timeout detected → entering processing state');
        setHadTimeout(true);
        setProcessing(true);
        return;
      }
      
      // Handle error
      if (apiError) {
        handleBulkError(apiError, 'contact', 'delete');
      }
      
    } catch (err) {
      console.error('[AlertContactBulkDelete] Unexpected error:', err);
      displayErrorSnackbar({
        message: err?.message || 'An unexpected error occurred',
        status: 500
      });
    } finally {
      setDeleting(false);
    }
  };

  // Don't render if no selection
  if (!selectedIds || selectedIds.length === 0) return null;

  return (
    <>
      <Dialog
        open={open && !syncing}
        onClose={isProcessing ? undefined : handleClose}
        keepMounted
        TransitionComponent={PopupTransition}
        maxWidth="xs"
        aria-labelledby="contact-bulk-delete-title"
        aria-describedby="contact-bulk-delete-description"
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
                Delete {contactCount} contact{contactCount > 1 ? 's' : ''}?
              </Typography>
              <Typography align="center">
                This will permanently delete the selected contact{contactCount > 1 ? 's' : ''} and all associated data.
                This action cannot be undone.
              </Typography>
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
                disabled={isProcessing}
              >
                {deleting ? 'Deleting...' : processing ? 'Processing...' : 'Delete'}
              </Button>
            </Stack>
          </Stack>
        </DialogContent>
      </Dialog>

      {/* Sync Dialog for timeout recovery */}
      <BulkOperationSyncDialog
        open={syncing}
        attempt={syncAttempt}
        maxAttempts={10}
        entityName="contact"
        operation="delete"
      />
    </>
  );
}

AlertContactBulkDelete.propTypes = {
  selectedIds: PropTypes.array,
  open: PropTypes.bool.isRequired,
  handleClose: PropTypes.func.isRequired,
  onDeleteComplete: PropTypes.func
};