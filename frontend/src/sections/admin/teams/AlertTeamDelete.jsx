// frontend/src/sections/admin/teams/AlertTeamDelete.jsx

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
import { displaySuccessSnackbar, displayErrorSnackbar } from 'utils/displayError';
import { deleteTeam } from 'api/admin/teams';

// assets
import DeleteFilled from '@ant-design/icons/DeleteFilled';
import WarningOutlined from '@ant-design/icons/WarningOutlined';

// ==============================|| TEAM - DELETE ||============================== //

/**
 * AlertTeamDelete Component
 * 
 * Confirmation dialog for team deletion with business logic validation.
 * 
 * Business Rules:
 * - Cannot delete a team with child teams (must delete/reassign children first)
 * - Cannot delete a team with assigned members (must reassign users first)
 * - Shows appropriate warning message based on blocking condition
 * - Disables delete button if children_count > 0 OR members_count > 0
 * 
 * @component
 */
export default function AlertTeamDelete({ team, open, handleClose }) {
  const [deleting, setDeleting] = useState(false);

  // Check blocking conditions
  const hasChildren = (team?.children?.length > 0) || (team?.children_count > 0);
  const hasMembers = team?.members_count > 0 || team?.member_count > 0;
  const canDelete = !hasChildren && !hasMembers;

  const deleteHandler = async () => {
    if (!canDelete || !team?.id) return;

    try {
      setDeleting(true);

      const res = await deleteTeam(team.id);

      if (res?.success) {
        displaySuccessSnackbar('Team deleted successfully');
        // Parent will reset selection and close the dialog
        handleClose?.();
      } else {
        displayErrorSnackbar(res || 'Failed to delete team.');
        // Do NOT close modal on error
      }
    } catch (err) {
      console.error('Delete team error:', err);
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
      aria-labelledby="team-delete-title"
      aria-describedby="team-delete-description"
    >
      <DialogContent sx={{ mt: 2, my: 1 }}>
        <Stack alignItems="center" spacing={3.5}>
          <Avatar color="error" sx={{ width: 72, height: 72, fontSize: '1.75rem' }}>
            <DeleteFilled />
          </Avatar>

          <Stack spacing={2} sx={{ width: 1 }}>
            <Typography variant="h4" align="center">
              {hasChildren || hasMembers ? 'Cannot Delete Team' : 'Are you sure you want to delete?'}
            </Typography>

            {/* ==================== BLOCKING CONDITION: HAS CHILDREN ==================== */}
            {hasChildren ? (
              <Alert severity="warning" icon={<WarningOutlined />}>
                <Typography variant="body2">
                  This team has <strong>{team?.children?.length || team?.children_count || 0} child team(s)</strong>.
                  <br />
                  Please delete or reassign child teams before deleting this team.
                </Typography>
              </Alert>
            ) : hasMembers ? (
              /* ==================== BLOCKING CONDITION: HAS MEMBERS ==================== */
              <Alert severity="warning" icon={<WarningOutlined />}>
                <Typography variant="body2">
                  This team has <strong>{team?.members_count || team?.member_count || 0} member(s)</strong>.
                  <br />
                  Please reassign users before deleting this team.
                </Typography>
              </Alert>
            ) : (
              /* ==================== CAN DELETE ==================== */
              <Typography align="center">
                By deleting
                <Typography variant="subtitle1" component="span">
                  {' '}
                  &quot;{team?.name}&quot;{' '}
                </Typography>
                team, all associated data will be removed.
                <br />
                This action cannot be undone.
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
              {canDelete ? 'Cancel' : 'Close'}
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

AlertTeamDelete.propTypes = {
  team: PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    members_count: PropTypes.number,
    member_count: PropTypes.number,
    children: PropTypes.array,
    children_count: PropTypes.number
  }),
  open: PropTypes.bool.isRequired,
  handleClose: PropTypes.func.isRequired
};