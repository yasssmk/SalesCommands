import PropTypes from 'prop-types';
// material-ui
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogContent from '@mui/material/DialogContent';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project import
import Avatar from 'components/@extended/Avatar';
import { PopupTransition } from 'components/@extended/Transitions';

import { deleteAccount } from 'api/(crm)/account';
import { openSnackbar } from 'api/snackbar';

// assets
import DeleteFilled from '@ant-design/icons/DeleteFilled';

// ==============================|| CUSTOMER - DELETE ||============================== //

export default function AlertAccountDelete({ id, account_name, selectedAccounts, open, handleClose, onConfirm }) {
  
  const isBatchDelete = selectedAccounts?.length > 0;

  const deleteHandler = async () => {
    try {
      if (isBatchDelete) {
        await Promise.all(selectedAccounts.map(account => deleteAccount(account.id)));
        openSnackbar({
          open: true,
          message: `${selectedAccounts.length} accounts deleted successfully`,
          anchorOrigin: { vertical: 'top', horizontal: 'right' },
          variant: 'alert',
          alert: { color: 'success' }
        });
      } else {
        await deleteAccount(id);
        openSnackbar({
          open: true,
          message: 'Account deleted successfully',
          anchorOrigin: { vertical: 'top', horizontal: 'right' },
          variant: 'alert',
          alert: { color: 'success' }
        });
      }
      onConfirm();
      handleClose();
    } catch (error) {
      openSnackbar({
        open: true,
        message: 'An error occurred while deleting.',
        variant: 'alert',
        alert: { color: 'error' }
      });
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
            {isBatchDelete ? (
              <Typography align="center">
                You are about to delete {selectedAccounts.length} accounts. This action cannot be undone.
              </Typography>
            ) : (
              <Typography align="center">
                By deleting <Typography variant="subtitle1" component="span">&quot;{account_name}&quot;</Typography>, 
                all related data will also be deleted.
              </Typography>
            )}
          </Stack>

          <Stack direction="row" spacing={2} sx={{ width: 1 }}>
            <Button fullWidth onClick={handleClose} color="secondary" variant="outlined">
              Cancel
            </Button>
            <Button fullWidth color="error" variant="contained" onClick={deleteHandler} autoFocus>
              Delete
            </Button>
          </Stack>
        </Stack>
      </DialogContent>
    </Dialog>
  );
}

AlertAccountDelete.propTypes = { id: PropTypes.number, title: PropTypes.string, open: PropTypes.bool, handleClose: PropTypes.func, onConfirm: PropTypes.func };