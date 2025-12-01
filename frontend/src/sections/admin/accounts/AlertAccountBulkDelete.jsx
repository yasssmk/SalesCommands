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

/**
 * AlertAccountBulkDelete Component
 * 
 * Confirmation dialog for bulk account deletion with sync support.
 * 
 * @param {Array} selectedIds - Array of account UUIDs to delete
 * @param {boolean} open - Dialog open state
 * @param {Function} handleClose - Function to close dialog
 * @param {Function} onDeleteComplete - Callback after successful deletion
 */
export default function AlertAccountBulkDelete({ selectedIds, open, handleClose, onDeleteComplete }) {
  const [deleting, setDeleting] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [hadTimeout, setHadTimeout] = useState(false);

  const accountCount = selectedIds?.length || 0;

  // Sync completion handler
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

  // Bulk operation sync hook
  const { syncing, syncAttempt, onSyncProgress, onSyncComplete } = useBulkOperationSync({
    onComplete: handleSyncComplete,
    closeDelay: 300
  });

  const isProcessing = deleting || processing || syncing;

  // Delete handler
  const deleteHandler = async () => {
    let apiError = null;

    try {
      setDeleting(true);

      const result = await bulkDeleteAccounts(
        selectedIds,
        'partial',
        onSyncProgress,
        onSyncComplete
      );

      // Handle 202 Accepted (async processing)
      if (result?.data?.__is202) {
        console.log('[AlertAccountBulkDelete] 202 Accepted → entering processing state');
        setProcessing(true);
        return;
      }

      // Store error if not success
      if (result && !result.success && !result.isTimeout) {
        apiError = result;
      }

      if (result?.success === true) {
        // Immediate success (no timeout)
        displaySuccessSnackbar(
          `${accountCount} account${accountCount > 1 ? 's' : ''} deleted successfully`
        );

        if (!isProcessing) {
          handleClose?.();
          onDeleteComplete?.();
        }
      } else if (result?.isPending) {
        const pendingMessage =
          result.message ||
          'Operation still in progress. It will complete in the background.';

        displayWarningSnackbar(pendingMessage);

        if (!isProcessing) {
          handleClose?.();
          onDeleteComplete?.();
        }
      } else if (result?.isTimeout) {
        console.log('[AlertAccountBulkDelete] Timeout detected, sync will start');
        setHadTimeout(true);
        setProcessing(true);
      } else {
        // All errors handled by handleBulkError
        handleBulkError(result, apiError, {
          onComplete: () => {
            handleClose?.();
            onDeleteComplete?.();
          }
        });
      }
    } catch (err) {
      console.error('[AlertAccountBulkDelete] Exception:', err);
      displayErrorSnackbar(err);
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
                all associated data including contacts, opportunities, and activities will also be affected.
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
