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
// N6 — the panel's state lives in useActivityNotesPanel (the page calls it
// ONCE): the Source band's « Open notes » pill opens the SAME panel, so the
// button shows it open and its dot follows it.

'use client';

import PropTypes from 'prop-types';
import { useCallback, useState } from 'react';

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
/** N6 — the Source band's pill that opens the same panel (PO label). */
export const OPEN_NOTES_PILL_LABEL = 'Open notes';

const UNSAVED_STATUSES = new Set([NOTE_AUTOSAVE_STATUS.PENDING, NOTE_AUTOSAVE_STATUS.SAVING]);

// ==============================|| THE PANEL'S STATE (N6) ||============================== //

/**
 * The activity's notes panel — ONE state for the page: open, toggle, and its
 * autosave status (the button's dot). Opening an already open panel keeps it
 * as is: the same element (type + props) is reconciled, not remounted — its
 * autosave goes on.
 */
export function useActivityNotesPanel(activityId) {
  const { isNotesPanelOpen, openNotesPanel, closeNotesPanel } = useWorkspaceDrawer();
  const [status, setStatus] = useState(NOTE_AUTOSAVE_STATUS.IDLE);

  const open = useCallback(() => {
    // setStatus is stable: the coque holds this node as is.
    openNotesPanel(<ActivityNotesPanel activityId={activityId} onStatusChange={setStatus} />);
  }, [openNotesPanel, activityId]);

  const toggle = useCallback(() => {
    if (isNotesPanelOpen) {
      closeNotesPanel();
      return;
    }
    open();
  }, [isNotesPanelOpen, closeNotesPanel, open]);

  return { isOpen: isNotesPanelOpen, status, open, toggle };
}

// ==============================|| ACTIVITY NOTES FAB ||============================== //

export default function ActivityNotesFab({ panel }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const isNarrow = useMediaQuery(theme.breakpoints.down('lg'));
  const { isCoqueOpen } = useWorkspaceDrawer();
  const { isOpen: isNotesPanelOpen, status: notesStatus, toggle } = panel;

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
  /** useActivityNotesPanel(activityId) — the page's one notes panel state. */
  panel: PropTypes.shape({
    isOpen: PropTypes.bool.isRequired,
    status: PropTypes.string.isRequired,
    toggle: PropTypes.func.isRequired,
  }).isRequired,
};
