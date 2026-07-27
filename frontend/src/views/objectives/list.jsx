'use client';

// frontend/src/views/objectives/list.jsx
//
// "My Objectives" — the current user's personal objectives (scoped by tier on
// the backend). List + create/edit modal + delete confirmation. Mirrors the
// territories list page (MainCard header, modal-mounted form, SWR revalidation
// handled by the api helpers).

import { useMemo, useState } from 'react';

import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';

import PlusOutlined from '@ant-design/icons/PlusOutlined';

import MainCard from 'components/MainCard';
import CircularWithPath from 'components/@extended/progress/CircularWithPath';

import { useGetObjectives } from 'api/objectives/objectives';
import ObjectiveCard from 'sections/objectives/ObjectiveCard';
import ObjectiveModal from 'sections/objectives/ObjectiveModal';
import ObjectiveDeleteDialog from 'sections/objectives/ObjectiveDeleteDialog';

// "Focus now" ordering: soonest END date first, then lowest attainment first
// (both from the payload — period_end and progress_ratio, never recomputed).
// Same shape as ProgressBlock.rank / TargetsTab: a pure comparator in a useMemo.
function focusOrder(a, b) {
  const endA = a.period_end || '';
  const endB = b.period_end || '';
  if (endA !== endB) return endA < endB ? -1 : 1; // ISO dates compare lexically
  const rA = a.progress_ratio == null ? Infinity : Number(a.progress_ratio);
  const rB = b.progress_ratio == null ? Infinity : Number(b.progress_ratio);
  return rA - rB;
}

export default function ObjectivesListPage() {
  const { objectives, objectivesLoading } = useGetObjectives();

  // Active/All toggle — mirror of the campaign TargetsTab toggle (exclusive,
  // size="small", no-empty guard). "active" = only CURRENT-window objectives.
  const [view, setView] = useState('active');

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);

  const visibleObjectives = useMemo(() => {
    const filtered =
      view === 'active' ? objectives.filter((o) => o.state === 'CURRENT') : objectives;
    // copy before sort — never mutate the SWR data in place.
    return [...filtered].sort(focusOrder);
  }, [objectives, view]);

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
        <Stack direction="row" spacing={1} alignItems="center">
          <ToggleButtonGroup
            value={view}
            exclusive
            size="small"
            onChange={(_, value) => {
              if (value) setView(value);
            }}
            aria-label="Objectives view filter"
          >
            <ToggleButton value="active" aria-label="Active">
              Active
            </ToggleButton>
            <ToggleButton value="all" aria-label="All">
              All
            </ToggleButton>
          </ToggleButtonGroup>
          <Button variant="contained" startIcon={<PlusOutlined />} onClick={openCreate}>
            New objective
          </Button>
        </Stack>
      }
    >
      {objectivesLoading ? (
        <Stack direction="row" justifyContent="center" sx={{ py: 5 }}>
          <CircularWithPath />
        </Stack>
      ) : visibleObjectives.length === 0 ? (
        <Box sx={{ py: 5, textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            {objectives.length === 0
              ? 'No objectives yet. Create your first one.'
              : 'No active objectives. Switch to All to see past and future ones.'}
          </Typography>
        </Box>
      ) : (
        <Grid container spacing={2}>
          {visibleObjectives.map((objective) => (
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
