// frontend/src/views/home/components/PersonTaskRow.jsx

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
 */
export default function PersonTaskRow({ name, overdue = 0, total = 0, max = 0 }) {
  const pct = max > 0 ? Math.round((total / max) * 100) : 0;
  const hasOverdue = overdue > 0;

  return (
    <Stack spacing={0.5} sx={{ py: 1 }}>
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
};
