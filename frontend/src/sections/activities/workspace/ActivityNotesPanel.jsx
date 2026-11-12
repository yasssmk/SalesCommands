// frontend/src/sections/activities/workspace/ActivityNotesPanel.jsx
//
// Sprint « Source / Notes » — notes panel, N4: the content of the coque's
// NOTES zone (the zone's own header says « Notes », N3). A thin wrapper —
// needed because the coque holds a FROZEN node (openNotesPanel(<…/>)): it
// reads the activity itself through SWR (useGetActivity, the page's own
// cache), so it follows the server's note and status.
//   - EditableTextBlock in autosave mode, wired to useNoteAutosave;
//   - the indicator « Saved · HH:mm » (« Saved · d MMM HH:mm » if not today);
//   - read-only on a CANCELLED activity (isActivitySignalsLocked) — or once
//     the server refused the note (the activity became CANCELLED meanwhile);
//   - N5, optional `onStatusChange(status)`: the autosave status, for the
//     floating Notes button's dot (back to idle when the panel closes — its
//     note is flushed then).

'use client';

import PropTypes from 'prop-types';
import { useEffect, useRef } from 'react';
import { format, isToday } from 'date-fns';

import Typography from '@mui/material/Typography';

import EditableTextBlock from 'components/EditableTextBlock';
import { NOTES_PANEL_TITLE } from 'components/WorkspaceDrawer';
import { useGetActivity } from 'api/accounts/activities';
import useNoteAutosave, { NOTE_AUTOSAVE_STATUS } from 'hooks/useNoteAutosave';
import { isActivitySignalsLocked, NOTES_FIELD } from 'utils/activitySignalsLock';

// ==============================|| CONSTANTS ||============================== //

export const NOTES_SAVED_LABEL = 'Saved';
export const NOTES_SAVED_TIME_FORMAT = 'HH:mm';
export const NOTES_SAVED_DATE_TIME_FORMAT = 'd MMM HH:mm';
export const NOTES_PANEL_PLACEHOLDER =
  'Capture key takeaways, observations, decisions made during the call...';
const NOTES_PANEL_ROWS = 8;

/** « Saved · 10:15 » today, « Saved · 3 Nov 10:15 » otherwise. */
export function formatNotesSavedAt(savedAt) {
  const date = new Date(savedAt);
  const pattern = isToday(date) ? NOTES_SAVED_TIME_FORMAT : NOTES_SAVED_DATE_TIME_FORMAT;
  return `${NOTES_SAVED_LABEL} · ${format(date, pattern)}`;
}

// ==============================|| ACTIVITY NOTES PANEL ||============================== //

export default function ActivityNotesPanel({ activityId, onStatusChange }) {
  const { activity, mutateActivity } = useGetActivity(activityId);
  // N4b: the hook's `note` — the server's, never older than our last write.
  const { note, status, savedAt, locked, schedule } = useNoteAutosave({
    activityId,
    initialValue: activity?.outcome_notes ?? '',
    serverUpdatedAt: activity?.updated_at,
    locked: isActivitySignalsLocked(activity),
    mutateActivity,
  });

  // N5 — report the status (latest callback; idle once closed).
  const onStatusChangeRef = useRef(onStatusChange);
  onStatusChangeRef.current = onStatusChange;
  useEffect(() => {
    onStatusChangeRef.current?.(status);
  }, [status]);
  useEffect(() => () => onStatusChangeRef.current?.(NOTE_AUTOSAVE_STATUS.IDLE), []);

  if (!activity) return null;

  const indicator =
    status === NOTE_AUTOSAVE_STATUS.SAVED && savedAt ? (
      <Typography variant="caption" color="text.secondary" data-testid="notes-saved-indicator">
        {formatNotesSavedAt(savedAt)}
      </Typography>
    ) : null;

  return (
    <EditableTextBlock
      label=""
      field={NOTES_FIELD}
      initialValue={note}
      rows={NOTES_PANEL_ROWS}
      placeholder={NOTES_PANEL_PLACEHOLDER}
      isLocked={locked}
      autosave
      onValueChange={schedule}
      indicator={indicator}
      ariaLabel={NOTES_PANEL_TITLE}
    />
  );
}

ActivityNotesPanel.propTypes = {
  activityId: PropTypes.string.isRequired,
  /** Optional (N5) — (status) => void: the autosave status. */
  onStatusChange: PropTypes.func,
};
