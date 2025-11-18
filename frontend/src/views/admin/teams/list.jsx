// frontend/src/views/admin/teams/list.jsx

'use client';

import { useState, useCallback, useMemo } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';

// project imports
import MainCard from 'components/MainCard';
import GenericTreeView from 'components/tree/GenericTreeView';
import TeamInfoPanel from 'sections/admin/teams/TeamInfoPanel';
import TeamModal from 'sections/admin/teams/TeamModal';
import AlertTeamDelete from 'sections/admin/teams/AlertTeamDelete';
import { DebouncedInput } from 'components/third-party/react-table';

// icons
import { PlusOutlined, FolderOutlined, FileOutlined } from '@ant-design/icons';

// mock data
import { mockTeams, findTeamById } from './mockTeamsData';

/**
 * Teams List Page
 */
export default function TeamsListPage() {

  // ==================== STATE ====================

  const [selectedTeamId, setSelectedTeamId] = useState(null);
  const [search, setSearch] = useState('');
  const [teamModal, setTeamModal] = useState(false);
  const [deleteModal, setDeleteModal] = useState(false);
  const [teamToDelete, setTeamToDelete] = useState(null);

  // ==================== COMPUTED ====================

  const selectedTeam = useMemo(() => {
    if (!selectedTeamId) return null;
    return findTeamById(mockTeams, selectedTeamId);
  }, [selectedTeamId]);

  // ==================== HANDLERS ====================

  const handleTeamSelect = useCallback((nodeId, node) => {
    setSelectedTeamId(nodeId);
  }, []);

  const handleAddTeam = useCallback(() => {
    setTeamModal(true);
  }, []);

  const handleEdit = useCallback((team) => {
    setTeamToEdit(team);
    setTeamModal(true);
  }, []);

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

  const handleDeleteSuccess = useCallback(() => {
      setDeleteModal(false);
      setTeamToDelete(null);
      setSelectedTeamId(null); 
  }, []);


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
            placeholder="Search teams..."
          />

          <Tooltip title="Add New Team">
            <Button
              variant="contained"
              startIcon={<PlusOutlined />}
              onClick={handleAddTeam}
            >
              Add Team
            </Button>
          </Tooltip>
        </Stack>

        {/* TreeView + Info Panel */}
        <Box sx={{ p: 2 }}>
          <Grid container spacing={2}>
            
            <Grid item xs={12} md={4} sx={{ display: 'flex' }}>
              <Box sx={{ width: '100%', minHeight: 500 }}>
                <GenericTreeView
                  data={mockTeams}
                  selectedId={selectedTeamId}
                  onSelect={handleTeamSelect}
                  searchTerm={search}
                  height="100%"
                />
              </Box>
            </Grid>

            <Grid item xs={12} md={8} sx={{ display: 'flex' }}>
              <TeamInfoPanel
                team={selectedTeam}
                onEdit={handleEdit}
                onDelete={handleDelete}
              />
            </Grid>

          </Grid>
        </Box>

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
          handleClose={handleDeleteSuccess}
        />
      )}
    </>
  );
}