// frontend/src/sections/home/PersonTaskRow.jsx

import PropTypes from 'prop-types';

import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// ==============================|| PERSON TASK ROW — one team member's pending load ||============================== //

/**
 * One member's pending tasks: name, "X left" (the small actionable number), an
 * overdue chip in red when any are late, and a bar sized relative to the busiest
 * member. Overdue is called out visually because it's what the manager chases.
 *
 * When `onSelect` is provided the row is a drill-down control: clicking it filters
 * the team activity table on this person (`selected` highlights the active one).
 */
export default function PersonTaskRow({ name, overdue = 0, total = 0, max = 0, onSelect, selected = false }) {
  const pct = max > 0 ? Math.round((total / max) * 100) : 0;
  const hasOverdue = overdue > 0;
  const clickable = typeof onSelect === 'function';

  return (
    <Stack
      spacing={0.5}
      onClick={clickable ? onSelect : undefined}
      sx={{
        py: 1,
        px: clickable ? 1 : 0,
        borderRadius: 1,
        cursor: clickable ? 'pointer' : 'default',
        bgcolor: selected ? 'primary.lighter' : 'transparent',
        '&:hover': clickable ? { bgcolor: selected ? 'primary.lighter' : 'action.hover' } : undefined,
      }}
    >
      <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
        <Typography variant="body2" noWrap sx={{ maxWidth: '55%' }} title={name}>
          {name}
        </Typography>
        <Stack direction="row" spacing={1} alignItems="center">
          {hasOverdue ? (
            <Chip size="small" color="error" variant="combined" label={`${overdue} overdue`} />
          ) : null}
          <Typography variant="subtitle2" color={hasOverdue ? 'warning.main' : 'text.primary'}>
            {total} left
          </Typography>
        </Stack>
      </Stack>
      <LinearProgress variant="determinate" value={pct} color={hasOverdue ? 'error' : 'primary'} />
    </Stack>
  );
}

PersonTaskRow.propTypes = {
  name: PropTypes.string,
  overdue: PropTypes.number,
  total: PropTypes.number,
  max: PropTypes.number,
  onSelect: PropTypes.func,
  selected: PropTypes.bool,
};
