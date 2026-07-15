// frontend/src/views/home/components/TeamTodoBlock.jsx

import PropTypes from 'prop-types';

import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import MainCard from 'components/MainCard';

import PersonTaskRow from './PersonTaskRow';

// ==============================|| TEAM TODO BLOCK — were today's tasks done, with names ||============================== //

/**
 * Manager bloc 1: each team member's pending tasks (today + overdue), by name,
 * overdue-first. People with nothing pending are omitted — the manager sees who
 * still has work, not a roll-call. Empty means the team is caught up.
 *
 * Each row is a drill-down: clicking it calls `onSelectPerson(id)` to filter the
 * team activity table on that person (`selectedPersonId` highlights the active
 * one); clicking the active row again clears the filter.
 */
export default function TeamTodoBlock({ people = [], loading = false, onSelectPerson, selectedPersonId = null }) {
  const max = people.reduce((m, p) => Math.max(m, p.total || 0), 0);

  return (
    <MainCard title="Open tasks by person (today + overdue)">
      {loading ? (
        <Stack spacing={1.5} sx={{ py: 1 }}>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} variant="rounded" height={44} />
          ))}
        </Stack>
      ) : people.length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
          All caught up across the team today 🎉
        </Typography>
      ) : (
        <Stack>
          {people.map((p) => (
            <PersonTaskRow
              key={p.id}
              name={p.name}
              overdue={p.overdue}
              total={p.total}
              max={max}
              selected={String(p.id) === String(selectedPersonId)}
              onSelect={onSelectPerson ? () => onSelectPerson(p.id) : undefined}
            />
          ))}
        </Stack>
      )}
    </MainCard>
  );
}

TeamTodoBlock.propTypes = {
  people: PropTypes.array,
  loading: PropTypes.bool,
  onSelectPerson: PropTypes.func,
  selectedPersonId: PropTypes.string,
};
