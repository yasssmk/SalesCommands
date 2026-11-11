// frontend/src/sections/activities/workspace/ActivityNotesFab.jsx
//
// Sprint « Source / Notes » — notes panel, N5: the floating « Notes » button
// of the Activity page (rendered ONLY by views/activities/workspace, on every
// activity type). New element: no floating action button in the app yet —
// MUI Fab + the Badge already used (components/table/Table.jsx), aphoriQ
// tokens, theme.zIndex.speedDial.
//   - fixed at the bottom right; while the coque is open in PUSH mode it moves
//     left by the coque's width (aphoriQ.drawer.width) + its margin, so the
//     coque never covers it (in overlay mode the backdrop covers the page);
//   - click → opens the notes panel (the coque's bottom zone); click again →
//     closes it (its note is flushed — useNoteAutosave);
//   - the Badge dot: a note pending / being saved (primary) or in error
//     (error).

'use client';

import PropTypes from 'prop-types';
import { useState } from 'react';

import { useTheme } from '@mui/material/styles';
import useMediaQuery from '@mui/material/useMediaQuery';
import Badge from '@mui/material/Badge';
import Fab from '@mui/material/Fab';
import Tooltip from '@mui/material/Tooltip';

import FormOutlined from '@ant-design/icons/FormOutlined';

import { useWorkspaceDrawer } from 'contexts/WorkspaceDrawerContext';
import { NOTE_AUTOSAVE_STATUS } from 'hooks/useNoteAutosave';
import ActivityNotesPanel from 'sections/activities/workspace/ActivityNotesPanel';

// ==============================|| CONSTANTS ||============================== //

/** The button's tooltip and accessible name (PO label). */
export const NOTES_FAB_TOOLTIP = 'Notes';

const UNSAVED_STATUSES = new Set([NOTE_AUTOSAVE_STATUS.PENDING, NOTE_AUTOSAVE_STATUS.SAVING]);

// ==============================|| ACTIVITY NOTES FAB ||============================== //

export default function ActivityNotesFab({ activityId }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const isNarrow = useMediaQuery(theme.breakpoints.down('lg'));
  const { isCoqueOpen, isNotesPanelOpen, openNotesPanel, closeNotesPanel } = useWorkspaceDrawer();
  const [notesStatus, setNotesStatus] = useState(NOTE_AUTOSAVE_STATUS.IDLE);

  const toggle = () => {
    if (isNotesPanelOpen) {
      closeNotesPanel();
      return;
    }
    // setNotesStatus is stable: the coque holds this node as is.
    openNotesPanel(<ActivityNotesPanel activityId={activityId} onStatusChange={setNotesStatus} />);
  };

  const inError = notesStatus === NOTE_AUTOSAVE_STATUS.ERROR;
  const unsaved = UNSAVED_STATUSES.has(notesStatus);
  const edge = theme.spacing(3);
  // Push: clear the coque (its width + its right margin, WorkspaceDrawer).
  const right =
    isCoqueOpen && !isNarrow ? `calc(${aq.drawer.width}px + ${theme.spacing(1.5)} + ${edge})` : edge;

  return (
    <Tooltip title={NOTES_FAB_TOOLTIP} placement="left">
      <Fab
        color="primary"
        size="medium"
        aria-label={NOTES_FAB_TOOLTIP}
        aria-pressed={isNotesPanelOpen}
        onClick={toggle}
        data-testid="activity-notes-fab"
        sx={{
          position: 'fixed',
          bottom: edge,
          right,
          zIndex: theme.zIndex.speedDial,
          transition: theme.transitions.create('right'),
        }}
      >
        <Badge
          variant="dot"
          color={inError ? 'error' : 'primary'}
          invisible={!inError && !unsaved}
          overlap="circular"
          data-testid="activity-notes-fab-badge"
          sx={{ '& .MuiBadge-dot': { border: `${aq.border.width.thin}px solid ${aq.surface.level2}` } }}
        >
          <FormOutlined style={{ fontSize: theme.iconSizes.xl }} />
        </Badge>
      </Fab>
    </Tooltip>
  );
}

ActivityNotesFab.propTypes = {
  activityId: PropTypes.string.isRequired,
};
