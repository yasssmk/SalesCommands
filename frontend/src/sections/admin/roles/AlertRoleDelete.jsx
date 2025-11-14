import PropTypes from 'prop-types';
import { useState } from 'react';

// material-ui
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogContent from '@mui/material/DialogContent';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project import
import Avatar from 'components/@extended/Avatar';
import { PopupTransition } from 'components/@extended/Transitions';
import { deleteRole } from 'api/admin/roles';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// assets
import DeleteFilled from '@ant-design/icons/DeleteFilled';
import WarningOutlined from '@ant-design/icons/WarningOutlined';

// ==============================|| ROLE - DELETE ||============================== //

/**
 * AlertRoleDelete Component
 * 
 * Confirmation dialog for role deletion with business logic validation.
 * 
 * Business Rules:
 * - Cannot delete a role with assigned users
 * - Must reassign users before deletion
 * - Shows warning message if users are assigned
 * - Disables delete button if users_count > 0
 * 
 * @component
 */
export default function AlertRoleDelete({ role, open, handleClose }) {
  const [deleting, setDeleting] = useState(false);

  // Check if role has assigned users
  const hasUsers = role?.users_count > 0;
  const isLocked = role?.is_admin === true || role?.name === 'Admin';
  const canDelete = !hasUsers && !isLocked;

  const deleteHandler = async () => {
    if (!canDelete) return;

    try {
      setDeleting(true);
      const res = await deleteRole(role.id);
      
      if (res?.success) {
        displaySuccessSnackbar('Role deleted successfully');
        handleClose?.();
      } else {
        displayErrorSnackbar(res);
        // Do NOT close modal on error
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
      aria-labelledby="role-delete-title"
      aria-describedby="role-delete-description"
    >
      <DialogContent sx={{ mt: 2, my: 1 }}>
        <Stack alignItems="center" spacing={3.5}>
          <Avatar color="error" sx={{ width: 72, height: 72, fontSize: '1.75rem' }}>
            <DeleteFilled />
          </Avatar>

          <Stack spacing={2} sx={{ width: 1 }}>
            <Typography variant="h4" align="center">
              {hasUsers || isLocked ? 'Cannot Delete Role' : 'Are you sure you want to delete?'}
            </Typography>

            {isLocked ? (
              // Error message for locked/admin role
              <Alert severity="error" icon={<WarningOutlined />}>
                <Typography variant="body2">
                  The{' '}
                  <Typography component="span" variant="subtitle2">
                    &quot;{role?.name}&quot;
                  </Typography>
                  {' '}role is a system role and cannot be deleted.
                </Typography>
                <Typography variant="body2" sx={{ mt: 1 }}>
                  This role is essential for system administration and must always exist.
                </Typography>
              </Alert>
            ) : hasUsers ? (
              // Warning message when users are assigned
              <Alert severity="warning" icon={<WarningOutlined />}>
                <Typography variant="body2" gutterBottom>
                  This role cannot be deleted because{' '}
                  <Typography component="span" variant="subtitle2">
                    {role.users_count} {role.users_count === 1 ? 'user is' : 'users are'}
                  </Typography>
                  {' '}currently assigned to it.
                </Typography>
                <Typography variant="body2" sx={{ mt: 1 }}>
                  Please reassign these users to another role before deleting{' '}
                  <Typography component="span" variant="subtitle2">
                    &quot;{role?.name}&quot;
                  </Typography>
                  .
                </Typography>
              </Alert>
            ) : (
              // Standard confirmation message
              <Typography align="center">
                By deleting{' '}
                <Typography variant="subtitle1" component="span">
                  &quot;{role?.name}&quot;
                </Typography>
                , this role will be permanently removed from the system.
              </Typography>
            )}
          </Stack>

          <Stack direction="row" spacing={2} sx={{ width: 1 }}>
            <Button 
              fullWidth 
              onClick={handleClose} 
              color="secondary" 
              variant="outlined"
            >
              {(hasUsers || isLocked)? 'Close' : 'Cancel'}
            </Button>
            <Button
              fullWidth
              color="error"
              variant="contained"
              onClick={deleteHandler}
              autoFocus={canDelete}
              disabled={!canDelete || deleting}
            >
              {deleting ? 'Deleting...' : 'Delete'}
            </Button>
          </Stack>
        </Stack>
      </DialogContent>
    </Dialog>
  );
}

AlertRoleDelete.propTypes = {
  role: PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
    name: PropTypes.string.isRequired,
    users_count: PropTypes.number
  }),
  open: PropTypes.bool.isRequired,
  handleClose: PropTypes.func.isRequired
};