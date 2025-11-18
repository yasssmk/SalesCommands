// frontend/src/sections/admin/teams/TeamInfoPanel.jsx

import PropTypes from 'prop-types';
import { useState, useMemo } from 'react';

// material-ui
import Autocomplete from '@mui/material/Autocomplete';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import Link from '@mui/material/Link';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

// project imports
import MainCard from 'components/MainCard';

// api hooks
import { useGetUsers } from 'api/admin/users';

// mock data (TEMPORARY - teams only)
import { mockTeams, flattenTeams } from 'views/admin/teams/mockTeamsData';


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
    description: '',
    manager: null,      // User object or null
    parent_team: null   // Team object or null
  });

  // ===============API=============================

  const { users = [], usersLoading } = useGetUsers({ 
    pageSize: 1000  // ✅ Fetch up to 1000 users for search
  });

  const allTeams = useMemo(() => flattenTeams(mockTeams), []); // MOCK DATA
  
  // Filter out current team to prevent circular reference
  const availableParentTeams = useMemo(() => {
    if (!team) return allTeams;
    return allTeams.filter(t => t.id !== team.id);
  }, [allTeams, team]);

  // ==================== HANDLERS ====================

  const handleEditClick = () => {
    console.log(" USERS LIST : ", {users})
    if (team) {
      setFormValues({
        name: team.name || '',
        description: team.description || '',
        manager: team.manager || null,
        parent_team: team.parent || null
      });
      setIsEditing(true);
    }
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setFormValues({ name: '', description: '', manager: null, parent_team: null });
  };

  const handleSaveEdit = () => {

    console.log('Team to update:', {
      id: team.id,
      name: formValues.name.trim(),
      description: formValues.description.trim(),
      manager: formValues.manager?.id || null,
      parent_team: formValues.parent_team?.id || null
    });

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
              {isEditing ? (
                <Autocomplete
                  fullWidth
                  options={users}  // ✅ Tous les users (jusqu'à 1000)
                  getOptionLabel={(option) => 
                    `${option.first_name} ${option.last_name} (${option.email}, ${option.role_name})`
                  }
                  value={formValues.manager}
                  onChange={(event, newValue) => {
                    setFormValues(prev => ({ ...prev, manager: newValue }));
                  }}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      placeholder="Search by name or email..."
                    />
                  )}
                  isOptionEqualToValue={(option, value) => option.id === value?.id}
                  noOptionsText="No users found"
                  loading={usersLoading}
                  filterOptions={(options, { inputValue }) => {
                    if (!inputValue) {
                      return options.slice(0, 5);  // Vide : 5 premiers
                    }
                    
                    // Filtrer parmi TOUS les users (1000), retourner 5 résultats
                    const searchLower = inputValue.toLowerCase();
                    return options
                      .filter(user => 
                        user.first_name?.toLowerCase().includes(searchLower) ||
                        user.last_name?.toLowerCase().includes(searchLower) ||
                        user.email?.toLowerCase().includes(searchLower)
                      )
                      .slice(0, 5);  // Max 5 résultats affichés
                  }}
                />
              ) : (
                <>
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
                </>
              )}
            </Stack>
          </Grid>

          {/* Parent Team */}
          <Grid item xs={12}>
            <Stack spacing={1}>
              <Typography variant="subtitle1">Parent Team</Typography>
              {isEditing ? (
                <Autocomplete
                  fullWidth
                  options={availableParentTeams}  
                  getOptionLabel={(option) => option.name}
                  value={formValues.parent_team}
                  onChange={(event, newValue) => {
                    setFormValues(prev => ({ ...prev, parent_team: newValue }));
                  }}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      placeholder="Search team name..."
                    />
                  )}
                  isOptionEqualToValue={(option, value) => option.id === value?.id}
                  noOptionsText="No teams found"
                  filterOptions={(options, { inputValue }) => {
                    if (!inputValue) {
                      // Si pas de recherche, afficher les 5 premières teams
                      return options.slice(0, 5);
                    }
                    
                    // Filtrer sur TOUTES les teams, puis prendre les 5 premiers résultats
                    const searchLower = inputValue.toLowerCase();
                    return options
                      .filter(team => team.name?.toLowerCase().includes(searchLower))
                      .slice(0, 5);  // ✅ Max 5 résultats APRÈS filtrage
                  }}
                />
              ) : (
                <>
                  {team.parent ? (
                    <Typography variant="h6" color="text.primary">
                      {typeof team.parent === 'object' ? team.parent.name : 'Has Parent'}
                    </Typography>
                  ) : (
                    <Typography variant="h6" color="text.disabled">
                      No Parent (Root Team)
                    </Typography>
                  )}
                </>
              )}
            </Stack>
          </Grid>

          {/* Member Count */}
          <Grid item xs={12}>
            <Stack spacing={1}>
              <Typography variant="subtitle1">Team Members</Typography>
              <Link
                href={`/admin/users?team=${team.id}`}
                underline="hover"
                sx={{ cursor: 'pointer' }}
              >
                <Typography variant="h6" color="primary">
                  {team.member_count || 0} member{team.member_count !== 1 ? 's' : ''}
                </Typography>
              </Link>
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
                    Save
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