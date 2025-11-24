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
import AsyncUserSelect from 'components/AsyncSelection/AsyncUserSelect';

// icons
import { TeamOutlined } from '@ant-design/icons';

// utils
import { formatDateTime } from 'config/formatters';

/**
 * TeamInfoPanel - Affiche les détails d'une team sélectionnée
 * Standardisé selon les patterns exacts des modals Role/User
 */
function TeamInfoPanel({ team, onEdit, onDelete, allTeams  }) {
  const [isEditing, setIsEditing] = useState(false);
  const [formValues, setFormValues] = useState({
    name: '',
    description: '',
    manager: null,      // User object or null
    parent_team: null   // Team object or null
  });

  // ===============API=============================


  const flatTeams = useMemo(() => allTeams || [], [allTeams]);
  
  // Filter out current team to prevent circular reference
  const availableParentTeams = useMemo(() => {
    if (!team) return allTeams;
    return allTeams.filter(t => t.id !== team.id);
  }, [allTeams, team]);



  /**
   * Get all descendant team IDs recursively
   * Reconstructs hierarchy from parent_team relationships
   */
  const getAllDescendantIds = useMemo(() => {
    if (!team || !allTeams || allTeams.length === 0) return [];

    // Build parent_id -> children map from allTeams
    const childrenMap = {};
    allTeams.forEach(t => {
      if (t.parent_team) {
        const parentId = typeof t.parent_team === 'string' ? t.parent_team : t.parent_team.id;
        if (!childrenMap[parentId]) {
          childrenMap[parentId] = [];
        }
        childrenMap[parentId].push(t);
      }
    });

    // Recursively collect IDs
    const collectIds = (teamId) => {
      const ids = [teamId];
      
      const children = childrenMap[teamId] || [];
      
      children.forEach(child => {
        ids.push(...collectIds(child.id));
      });
      
      return ids;
    };

    return collectIds(team.id);
  }, [team, allTeams]);

  /**
   * Build users filter URL with hierarchical teams
   * Returns URL with team IDs (current + all descendants)
   */
  const usersFilterUrl = useMemo(() => {
    if (!team) return '/admin/users';

    // Join all team IDs with commas
    const teamIds = getAllDescendantIds.join(',');
    return `/admin/users?team=${teamIds}`;
  }, [team, getAllDescendantIds]);
  // ==================== HANDLERS ====================

  const handleEditClick = () => {
    if (team) {
      setFormValues({
        name: team.name || '',
        description: team.description || '',
        manager: team.manager || null,
        parent_team: team.parent_team || null
      });
      setIsEditing(true);
    }
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setFormValues({ name: '', description: '', manager: null, parent_team: null });
  };

  const handleSaveEdit = () => {
    if (!team) return;

    const payload = {
      id: team.id,
      name: formValues.name.trim(),
      description: formValues.description?.trim() || '',
      manager: formValues.manager?.id || null,
      parent_team: formValues.parent_team?.id || null
    };

    console.log('Team to update (payload):', payload);

    if (onEdit) {
      onEdit(payload);
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
                <AsyncUserSelect
                    value={formValues.manager}
                    onChange={(event, newValue) => {
                      setFormValues(prev => ({ ...prev, manager: newValue }));
                    }}
                    placeholder="Search by name or email..."
                  />
                ) : (
                <>
                  {team.manager ? (
                    // Direct manager
                    <Stack spacing={0.5}>
                      <Typography variant="h6">
                        {team.manager.first_name} {team.manager.last_name}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {team.manager.email}
                      </Typography>
                    </Stack>
                  ) : team.effective_manager ? (
                    // Inherited manager from parent hierarchy
                    <Stack spacing={0.5}>
                      <Stack direction="row" spacing={1} alignItems="center">
                        <Typography variant="h6" color="text.secondary">
                          {team.effective_manager.first_name} {team.effective_manager.last_name}
                        </Typography>
                        <Chip
                          label="Inherited"
                          size="small"
                          color="warning"
                          variant="outlined"
                        />
                      </Stack>
                      <Typography variant="body2" color="text.secondary">
                        {team.effective_manager.email}
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
                  {team.parent_team ? (
                    <Typography variant="h6" color="text.primary">
                      {team.parent_team.name}
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

          {/* Active Members */}
          <Grid item xs={12} md={6}>
            <Stack spacing={1}>
              <Typography variant="subtitle1">Active Members</Typography>
              <Link
                href={usersFilterUrl}
                underline="hover"
                sx={{ cursor: 'pointer' }}
              >
                <Typography variant="h6" color="success.main">
                  {team.active_members_count || 0} member{team.active_members_count > 1 ? 's' : ''}
                </Typography>
              </Link>
            </Stack>
          </Grid>

          {/* Total Members */}
          <Grid item xs={12} md={6}>
            <Stack spacing={1}>
              <Typography variant="subtitle1">Total Members</Typography>
              <Link
                href={usersFilterUrl}
                underline="hover"
                sx={{ cursor: 'pointer' }}
              >
                <Typography variant="h6" color="primary">
                  {team.members_count || 0} member{team.members_count > 1 ? 's' : ''}
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
    effective_manager: PropTypes.shape({
      id: PropTypes.string,
      first_name: PropTypes.string,
      last_name: PropTypes.string,
      email: PropTypes.string
    }),
    manager_inherited: PropTypes.bool,
    parent: PropTypes.oneOfType([PropTypes.string, PropTypes.object]),
    member_count: PropTypes.number,
    created_at: PropTypes.string,
    children: PropTypes.array
  }),
};


export default TeamInfoPanel;