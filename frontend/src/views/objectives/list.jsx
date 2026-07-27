// frontend/src/views/objectives/list.jsx
//
// "My Objectives" — the current user's personal objectives (scoped by tier on
// the backend). List + create/edit modal + delete confirmation. Mirrors the
// territories list page (MainCard header, modal-mounted form, SWR revalidation
// handled by the api helpers).

import { useState } from 'react';

import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import PlusOutlined from '@ant-design/icons/PlusOutlined';

import MainCard from 'components/MainCard';
import CircularWithPath from 'components/@extended/progress/CircularWithPath';

import { useGetObjectives } from 'api/objectives/objectives';
import ObjectiveCard from 'sections/objectives/ObjectiveCard';
import ObjectiveModal from 'sections/objectives/ObjectiveModal';
import ObjectiveDeleteDialog from 'sections/objectives/ObjectiveDeleteDialog';

export default function ObjectivesListPage() {
  const { objectives, objectivesLoading } = useGetObjectives();

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);

  const openCreate = () => {
    setEditing(null);
    setModalOpen(true);
  };
  const openEdit = (objective) => {
    setEditing(objective);
    setModalOpen(true);
  };
  const closeModal = () => {
    setModalOpen(false);
    setEditing(null);
  };

  return (
    <MainCard
      title="My Objectives"
      secondary={
        <Button variant="contained" startIcon={<PlusOutlined />} onClick={openCreate}>
          New objective
        </Button>
      }
    >
      {objectivesLoading ? (
        <Stack direction="row" justifyContent="center" sx={{ py: 5 }}>
          <CircularWithPath />
        </Stack>
      ) : objectives.length === 0 ? (
        <Box sx={{ py: 5, textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            No objectives yet. Create your first one.
          </Typography>
        </Box>
      ) : (
        <Grid container spacing={2}>
          {objectives.map((objective) => (
            <Grid item xs={12} md={6} key={objective.id}>
              <ObjectiveCard objective={objective} onEdit={openEdit} onDelete={setDeleting} />
            </Grid>
          ))}
        </Grid>
      )}

      <ObjectiveModal open={modalOpen} closeModal={closeModal} objective={editing} />
      <ObjectiveDeleteDialog
        open={Boolean(deleting)}
        objective={deleting}
        closeDialog={() => setDeleting(null)}
      />
    </MainCard>
  );
}
