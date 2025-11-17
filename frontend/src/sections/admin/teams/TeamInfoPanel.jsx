// frontend/src/sections/admin/teams/TeamInfoPanel.jsx

import PropTypes from 'prop-types';
import { useState } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

// project imports
import MainCard from 'components/MainCard';

// icons
import { TeamOutlined } from '@ant-design/icons';

// utils
import { formatDateTime } from 'config/formatters';

/**
 * TeamInfoPanel - Affiche les détails d'une team sélectionnée
 * Standardisé selon les patterns exacts des modals Role/User
 */
function TeamInfoPanel({ team, onEdit, onDelete }) {
  const [isEditing, setIsEditing] = useState(false);
  const [formValues, setFormValues] = useState({
    name: '',
    description: ''
  });

  // ==================== HANDLERS ====================

  const handleEditClick = () => {
    if (team) {
      setFormValues({
        name: team.name || '',
        description: team.description || ''
      });
      setIsEditing(true);
    }
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setFormValues({ name: '', description: '' });
  };

  const handleSaveEdit = () => {
    if (onEdit && team) {
      onEdit({ ...team, ...formValues });
    }
    setIsEditing(false);
  };

  const handleFieldChange = (field) => (event) => {
    setFormValues(prev => ({
      ...prev,
      [field]: event.target.value
    }));
  };

  // ==================== EMPTY STATE ====================

  if (!team) {
    return (
      <MainCard content={false} sx={{ height: '100%',  width: '100%'  }}>
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: 400,
            p: 3
          }}
        >
          <TeamOutlined style={{ fontSize: 48, color: '#bdbdbd', marginBottom: 16 }} />
          <Typography variant="h6" color="text.secondary" gutterBottom>
            Select a team
          </Typography>
          <Typography variant="body2" color="text.secondary" align="center">
            Click on a team in the tree view to see its details
          </Typography>
        </Box>
      </MainCard>
    );
  }

  // ==================== TEAM DETAILS ====================

  return (
    <MainCard content={false} sx={{ height: '100%',  width: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* DialogTitle - standard size via theme override */}
      <DialogTitle>Team Details</DialogTitle>
      
      <Divider />

      {/* DialogContent - standard padding + scroll */}
      <DialogContent dividers  sx={{ flex: 1, overflow: 'auto' }}>
        <Grid container spacing={3}>
          
          {/* Team Name */}
          <Grid item xs={12}>
            <Stack spacing={1}>
              <Typography variant="subtitle1">Team Name</Typography>
              {isEditing ? (
                <TextField
                  fullWidth
                  placeholder="Enter team name"
                  value={formValues.name}
                  onChange={handleFieldChange('name')}
                />
              ) : (
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="h6">
                    {team.name}
                  </Typography>
                  {team.children && team.children.length > 0 && (
                    <Chip
                      label={`${team.children.length} sub-team${team.children.length > 1 ? 's' : ''}`}
                      size="small"
                      color="primary"
                      variant="light"
                    />
                  )}
                </Stack>
              )}
            </Stack>
          </Grid>

          {/* Description */}
          <Grid item xs={12}>
            <Stack spacing={1}>
              <Typography variant="subtitle1">Description</Typography>
              {isEditing ? (
                <TextField
                  fullWidth
                  multiline
                  rows={3}
                  placeholder="Enter description"
                  value={formValues.description}
                  onChange={handleFieldChange('description')}
                />
              ) : (
                <Typography variant="body2" color="text.primary">
                  {team.description || 'No description'}
                </Typography>
              )}
            </Stack>
          </Grid>

          {/* Manager */}
          <Grid item xs={12}>
            <Stack spacing={1}>
              <Typography variant="subtitle1">Manager</Typography>
              {team.manager ? (
                <Stack spacing={0.5}>
                  <Typography variant="h6">
                    {team.manager.first_name} {team.manager.last_name}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {team.manager.email}
                  </Typography>
                </Stack>
              ) : (
                <Typography variant="h6" color="text.disabled">
                  No Manager
                </Typography>
              )}
            </Stack>
          </Grid>

          {/* Parent Team */}
          <Grid item xs={12}>
            <Stack spacing={1}>
              <Typography variant="subtitle1">Parent Team</Typography>
              <Typography variant="h6" color={team.parent ? 'text.primary' : 'text.disabled'}>
                {team.parent ? 'Has Parent' : 'No Parent (Root Team)'}
              </Typography>
            </Stack>
          </Grid>

          {/* Member Count */}
          <Grid item xs={12}>
            <Stack spacing={1}>
              <Typography variant="subtitle1">Team Members</Typography>
              <Typography variant="h6">
                {team.member_count || 0} member{team.member_count !== 1 ? 's' : ''}
              </Typography>
            </Stack>
          </Grid>

          {/* Created Date */}
          {team.created_at && (
            <Grid item xs={12}>
              <Stack spacing={1}>
                <Typography variant="subtitle1">Created</Typography>
                <Typography variant="body2" color="text.primary">
                  {formatDateTime(team.created_at)}
                </Typography>
              </Stack>
            </Grid>
          )}

        </Grid>
      </DialogContent>

      <Divider />

      {/* DialogActions - standard layout */}
      <DialogActions sx={{ p: 2.5 }}>
        <Grid container justifyContent="space-between" alignItems="center">
          <Grid item />
          <Grid item>
            <Stack direction="row" spacing={2} alignItems="center">
              {isEditing ? (
                <>
                  <Button color="error" onClick={handleCancelEdit}>
                    Cancel
                  </Button>
                  <Button variant="contained" onClick={handleSaveEdit}>
                    Save Changes
                  </Button>
                </>
              ) : (
                <>
                  <Button variant="outlined" onClick={handleEditClick}>
                    Edit
                  </Button>
                  <Button
                    variant="outlined"
                    color="error"
                    onClick={() => onDelete && onDelete(team)}
                  >
                    Delete
                  </Button>
                </>
              )}
            </Stack>
          </Grid>
        </Grid>
      </DialogActions>
    </MainCard>
  );
}

TeamInfoPanel.propTypes = {
  team: PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    description: PropTypes.string,
    manager: PropTypes.shape({
      id: PropTypes.string,
      first_name: PropTypes.string,
      last_name: PropTypes.string,
      email: PropTypes.string
    }),
    parent: PropTypes.oneOfType([PropTypes.string, PropTypes.object]),
    member_count: PropTypes.number,
    created_at: PropTypes.string,
    children: PropTypes.array
  }),
  onEdit: PropTypes.func,
  onDelete: PropTypes.func
};

export default TeamInfoPanel;