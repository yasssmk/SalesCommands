// frontend/src/views/admin/teams/list.jsx

'use client';

import { useState, useCallback, useMemo } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import CircularProgress from '@mui/material/CircularProgress';

// project imports
import MainCard from 'components/MainCard';
import GenericTreeView from 'components/tree/GenericTreeView';
import TeamInfoPanel from 'sections/admin/teams/TeamInfoPanel';
import TeamModal from 'sections/admin/teams/TeamModal';
import AlertTeamDelete from 'sections/admin/teams/AlertTeamDelete';
import { DebouncedInput } from 'components/third-party/react-table';

// api hooks
import { useGetTeams, updateTeam, deleteTeam } from 'api/admin/teams';

// utils
import { displayErrorSnackbar } from 'utils/displayError';

// icons
import { PlusOutlined } from '@ant-design/icons';

/**
 * Teams List Page
 */
export default function TeamsListPage() {

  // ==================== STATE ====================

  const [selectedTeamId, setSelectedTeamId] = useState(null);
  const [selectedTeam, setSelectedTeam] = useState(null);
  const [search, setSearch] = useState('');
  const [ordering, setOrdering] = useState('name');
  const [teamModal, setTeamModal] = useState(false);
  const [deleteModal, setDeleteModal] = useState(false);
  const [teamToDelete, setTeamToDelete] = useState(null);

  // ==================== API DATA ====================

  const { teams, teamsLoading, teamsError } = useGetTeams({
    search,
    ordering
  });

  // ==================== ERROR HANDLING ====================

  // Display error if API fails
  useMemo(() => {
    if (teamsError) {
      displayErrorSnackbar(teamsError);
    }
  }, [teamsError]);

  // ==================== HANDLERS ====================

  const handleTeamSelect = useCallback((nodeId, node) => {
  setSelectedTeamId(nodeId);
  setSelectedTeam(node);
}, []);

  const handleAddTeam = useCallback(() => {
    setTeamModal(true);
  }, []);

  const handleEdit = useCallback(
  async (payload) => {
    // payload: { id, name, description, manager, parent_team }
    try {
      const { id, ...data } = payload;

      const result = await updateTeam(id, data);

      if (!result.success) {
        displayErrorSnackbar(result.error || 'Failed to update team.');
        return;
      }
      // Optionally: you can show a success snackbar here
      // and SWR will revalidate using your existing logic
    } catch (err) {
      console.error('Update team error:', err);
      displayErrorSnackbar('An unexpected error occurred while updating the team.');
    }
  },
  []
);


  const handleDelete = useCallback((team) => {
    setTeamToDelete(team);
    setDeleteModal(true);
  }, []);

  const handleCloseModal = useCallback(() => {
    setTeamModal(false);
    setTeamToEdit(null);
  }, []);

  const handleCloseDeleteModal = useCallback(() => {
    setDeleteModal(false);
    setTeamToDelete(null);
  }, []);

  const handleConfirmDelete = useCallback(async () => {
    if (!teamToDelete) return;

    try {
      const result = await deleteTeam(teamToDelete.id);

      if (!result.success) {
        displayErrorSnackbar(result.error || 'Failed to delete team.');
        return;
      }

      // If delete succeeded:
      setDeleteModal(false);
      setTeamToDelete(null);
      setSelectedTeamId(null);
      // SWR revalidation is already handled in deleteTeam (revalidateMultiple)
    } catch (err) {
      console.error('Delete team error:', err);
      displayErrorSnackbar('An unexpected error occurred while deleting the team.');
    }
  }, [teamToDelete]);


  // ==================== RENDER ====================

  return (
    <>
      <MainCard content={false}>
        
        {/* Header Actions */}
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={2}
          alignItems="center"
          justifyContent="space-between"
          sx={{ padding: 2 }}
        >
          <DebouncedInput
            value={search}
            onFilterChange={(value) => setSearch(String(value))}
            placeholder={`Search ${teams?.length || 0} teams...`}
          />

          <Tooltip title="Add New Team">
            <span>
              <Button
                variant="contained"
                startIcon={<PlusOutlined />}
                onClick={handleAddTeam}
                disabled={teamsLoading}
              >
                Add Team
              </Button>
            </span>
          </Tooltip>
        </Stack>

        {/* Loading State */}
        {teamsLoading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400, p: 3 }}>
            <CircularProgress />
          </Box>
        )}

        {/* Error State */}
        {!teamsLoading && teamsError && (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400, p: 3 }}>
            <Typography variant="body1" color="error">
              Failed to load teams. Please try refreshing the page.
            </Typography>
          </Box>
        )}

        {/* Empty State */}
        {!teamsLoading && !teamsError && (!teams || teams.length === 0) && (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 400, p: 3 }}>
            <Typography variant="h6" color="text.secondary" gutterBottom>
              No teams found
            </Typography>
            <Typography variant="body2" color="text.secondary" align="center">
              {search ? `No results for "${search}"` : 'Start by creating your first team'}
            </Typography>
          </Box>
        )}

        {/* TreeView + Info Panel */}
        {!teamsLoading && !teamsError && teams && teams.length > 0 && (
          <Box sx={{ p: 2 }}>
            <Grid container spacing={2}>
              
              <Grid item xs={12} md={4} sx={{ display: 'flex' }}>
                <Box sx={{ width: '100%', minHeight: 500 }}>
                  <GenericTreeView
                    data={teams}
                    selectedId={selectedTeamId}
                    onSelect={handleTeamSelect}
                    searchTerm={search}
                    height="100%"
                    parentField="parent_team"
                  />
                </Box>
              </Grid>

            <Grid item xs={12} md={8} sx={{ display: 'flex' }}>
                <TeamInfoPanel
                  team={selectedTeam}
                  onEdit={handleEdit}
                  onDelete={handleDelete}
                  allTeams={teams}
                />
              </Grid>

            </Grid>
          </Box>
        )}

      </MainCard>

      <TeamModal
        open={teamModal}
        modalToggler={setTeamModal}
        team={null}
      />

      {/* Delete Team Confirmation */}
      {teamToDelete && (
        <AlertTeamDelete
        team={teamToDelete}
        open={deleteModal}
        onCancel={handleCloseDeleteModal}
        onConfirm={handleConfirmDelete}
      />
      )}
    </>
  );
}