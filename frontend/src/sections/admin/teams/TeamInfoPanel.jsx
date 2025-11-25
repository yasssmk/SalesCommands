// frontend/src/sections/admin/teams/TeamInfoPanel.jsx

import PropTypes from 'prop-types';
import { useState, useMemo, useEffect } from 'react';

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

// third-party
import * as Yup from 'yup';
import { useFormik, Form, FormikProvider } from 'formik';

// project imports
import MainCard from 'components/MainCard';
import AsyncUserSelect from 'components/AsyncSelection/AsyncUserSelect';
import { displaySuccessSnackbar } from 'utils/displayError';
import { handleFormikError } from 'utils/formErrorHandler';

// api
import { updateTeam } from 'api/admin/teams';

// icons
import { TeamOutlined } from '@ant-design/icons';

// utils
import { formatDateTime } from 'config/formatters';

// ==============================|| VALIDATION SCHEMA ||============================== //

const EditSchema = Yup.object().shape({
  name: Yup.string()
    .required('Team name is required')
    .min(2, 'Team name must be at least 2 characters')
    .max(100, 'Team name must not exceed 100 characters'),
  description: Yup.string()
    .max(500, 'Description must not exceed 500 characters'),
  manager: Yup.object().nullable(),
  parent_team: Yup.object().nullable()
});

// ==============================|| TEAM INFO PANEL ||============================== //

/**
 * TeamInfoPanel - Display and edit team details
 * 
 * Uses Formik for edit mode with proper error handling via handleFormikError
 */
function TeamInfoPanel({ team, onEditSuccess, onDelete, allTeams }) {
  const [isEditing, setIsEditing] = useState(false);

  // Filter out current team and descendants to prevent circular reference
  const availableParentTeams = useMemo(() => {
    if (!team || !allTeams) return allTeams || [];
    
    // Get all descendant IDs to exclude
    const getDescendantIds = (teamId, teamsMap) => {
      const ids = new Set([teamId]);
      const children = allTeams.filter(t => {
        const parentId = typeof t.parent_team === 'string' ? t.parent_team : t.parent_team?.id;
        return parentId === teamId;
      });
      children.forEach(child => {
        const childDescendants = getDescendantIds(child.id, teamsMap);
        childDescendants.forEach(id => ids.add(id));
      });
      return ids;
    };
    
    const excludeIds = getDescendantIds(team.id);
    return allTeams.filter(t => !excludeIds.has(t.id));
  }, [allTeams, team]);

  // Get all descendant team IDs for users filter URL
  const getAllDescendantIds = useMemo(() => {
    if (!team || !allTeams || allTeams.length === 0) return [];

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

  const usersFilterUrl = useMemo(() => {
    if (!team) return '/admin/users';
    const teamIds = getAllDescendantIds.join(',');
    return `/admin/users?team=${teamIds}`;
  }, [team, getAllDescendantIds]);

  // Active members URL with is_active filter
  const activeUsersFilterUrl = useMemo(() => {
    if (!team) return '/admin/users?active=true';
    const teamIds = getAllDescendantIds.join(',');
    return `/admin/users?team=${teamIds}&active=true`;
  }, [team, getAllDescendantIds]);

  // Total members URL without is_active filter
  const totalUsersFilterUrl = useMemo(() => {
    if (!team) return '/admin/users';
    const teamIds = getAllDescendantIds.join(',');
    return `/admin/users?team=${teamIds}`;
  }, [team, getAllDescendantIds]);

  // ==============================|| FORMIK SETUP ||============================== //

  const formik = useFormik({
    initialValues: {
      name: team?.name || '',
      description: team?.description || '',
      manager: team?.manager || null,
      parent_team: team?.parent_team || null
    },
    validationSchema: EditSchema,
    enableReinitialize: true,
    onSubmit: async (values) => {
      if (!team) return;

      try {
        const payload = {
          name: values.name.trim(),
          description: values.description?.trim() || null,
          manager: values.manager?.id || null,
          parent_team: values.parent_team?.id || null
        };

        const result = await updateTeam(team.id, payload);

        if (result.success) {
          displaySuccessSnackbar('Team updated successfully');
          setIsEditing(false);
          // Notify parent of success for state update
          onEditSuccess?.(result.data?.data || result.data);
        } else {
          handleFormikError(result, formik);
        }
      } catch (err) {
        handleFormikError(err, formik);
      }
    }
  });

  const { errors, touched, handleSubmit, getFieldProps, setFieldValue, values, isSubmitting, resetForm } = formik;

  // Reset form when team changes
  useEffect(() => {
    if (team) {
      resetForm({
        values: {
          name: team.name || '',
          description: team.description || '',
          manager: team.manager || null,
          parent_team: team.parent_team || null
        }
      });
      setIsEditing(false);
    }
  }, [team?.id, resetForm]);

  // ==================== HANDLERS ====================

  const handleEditClick = () => {
    setIsEditing(true);
  };

  const handleCancelEdit = () => {
    resetForm();
    setIsEditing(false);
  };

  // ==================== EMPTY STATE ====================

  if (!team) {
    return (
      <MainCard content={false} sx={{ height: '100%', width: '100%' }}>
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
    <MainCard content={false} sx={{ height: '100%', width: '100%', display: 'flex', flexDirection: 'column' }}>
      <FormikProvider value={formik}>
        <Form autoComplete="off" noValidate onSubmit={handleSubmit}>
          <DialogTitle>Team Details</DialogTitle>
          
          <Divider />

          <DialogContent dividers sx={{ flex: 1, overflow: 'auto' }}>
            <Grid container spacing={3}>
              
              {/* Team Name */}
              <Grid item xs={12}>
                <Stack spacing={1}>
                  <Typography variant="subtitle1">Team Name</Typography>
                  {isEditing ? (
                    <TextField
                      fullWidth
                      placeholder="Enter team name"
                      {...getFieldProps('name')}
                      error={Boolean(touched.name && errors.name)}
                      helperText={touched.name && errors.name}
                    />
                  ) : (
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Typography variant="h6">{team.name}</Typography>
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
                      {...getFieldProps('description')}
                      error={Boolean(touched.description && errors.description)}
                      helperText={touched.description && errors.description}
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
                      value={values.manager}
                      onChange={(event, newValue) => {
                        setFieldValue('manager', newValue);
                      }}
                      placeholder="Search by name or email..."
                      error={Boolean(touched.manager && errors.manager)}
                      helperText={touched.manager && errors.manager}
                      filters={{ role_tier: 'manager,admin' }}
                      pageSize={5}
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
                      ) : team.effective_manager ? (
                        <Stack spacing={0.5}>
                          <Stack direction="row" spacing={1} alignItems="center">
                            <Typography variant="h6" color="text.secondary">
                              {team.effective_manager.first_name} {team.effective_manager.last_name}
                            </Typography>
                            <Chip label="Inherited" size="small" color="warning" variant="outlined" />
                          </Stack>
                          <Typography variant="body2" color="text.secondary">
                            {team.effective_manager.email}
                          </Typography>
                        </Stack>
                      ) : (
                        <Typography variant="h6" color="text.disabled">No Manager</Typography>
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
                      value={values.parent_team}
                      onChange={(event, newValue) => {
                        setFieldValue('parent_team', newValue);
                      }}
                      renderInput={(params) => (
                        <TextField
                          {...params}
                          placeholder="Search team name..."
                          error={Boolean(touched.parent_team && errors.parent_team)}
                          helperText={touched.parent_team && errors.parent_team}
                        />
                      )}
                      isOptionEqualToValue={(option, value) => option.id === value?.id}
                      noOptionsText="No teams found"
                      filterOptions={(options, { inputValue }) => {
                        if (!inputValue) return options.slice(0, 5);
                        const searchLower = inputValue.toLowerCase();
                        return options
                          .filter(t => t.name?.toLowerCase().includes(searchLower))
                          .slice(0, 5);
                      }}
                    />
                  ) : (
                    <>
                      {team.parent_team ? (
                        <Typography variant="h6" color="text.primary">{team.parent_team.name}</Typography>
                      ) : (
                        <Typography variant="h6" color="text.disabled">No Parent (Root Team)</Typography>
                      )}
                    </>
                  )}
                </Stack>
              </Grid>

              {/* Active Members */}
              <Grid item xs={12} md={6}>
                <Stack spacing={1}>
                  <Typography variant="subtitle1">Active Users</Typography>
                  <Link href={activeUsersFilterUrl} underline="hover" sx={{ cursor: 'pointer' }}>
                    <Typography variant="h6" >
                      {team.active_members_count || 0} user{team.active_members_count > 1 ? 's' : ''}
                    </Typography>
                  </Link>
                </Stack>
              </Grid>

              {/* Total Members */}
              <Grid item xs={12} md={6}>
                <Stack spacing={1}>
                  <Typography variant="subtitle1">Total Users</Typography>
                  <Link href={totalUsersFilterUrl} underline="hover" sx={{ cursor: 'pointer' }}>
                    <Typography variant="h6" >
                      {team.members_count || 0} user{team.members_count > 1 ? 's' : ''}
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

          <DialogActions sx={{ p: 2.5 }}>
            <Grid container justifyContent="space-between" alignItems="center">
              <Grid item />
              <Grid item>
                <Stack direction="row" spacing={2} alignItems="center">
                  {isEditing ? (
                    <>
                      <Button color="error" onClick={handleCancelEdit} disabled={isSubmitting}>
                        Cancel
                      </Button>
                      <Button type="submit" variant="contained" disabled={isSubmitting}>
                        {isSubmitting ? 'Saving...' : 'Save'}
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
        </Form>
      </FormikProvider>
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
    parent_team: PropTypes.oneOfType([PropTypes.string, PropTypes.object]),
    members_count: PropTypes.number,
    active_members_count: PropTypes.number,
    created_at: PropTypes.string,
    children: PropTypes.array
  }),
  onEditSuccess: PropTypes.func,
  onDelete: PropTypes.func,
  allTeams: PropTypes.array
};

export default TeamInfoPanel;