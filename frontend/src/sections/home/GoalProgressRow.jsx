// frontend/src/sections/home/GoalProgressRow.jsx

import PropTypes from 'prop-types';

import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import LinearWithLabel from 'components/@extended/progress/LinearWithLabel';

// ==============================|| GOAL PROGRESS ROW — label + bar + framed headline ||============================== //

/**
 * One progress line: the entity label, a determinate bar, and the
 * goal-gradient headline ("32 done" early / "only 8 left" near the end). The
 * `gradient` is a pre-computed result of goalGradient(); rendering is decoupled
 * from framing so callers own the units and thresholds.
 */
export default function GoalProgressRow({ label, gradient }) {
  const g = gradient || { pct: 0, mode: 'none', headline: '' };
  const remaining = g.mode === 'remaining';
  const empty = g.mode === 'empty'; // no work to size — a setup state, not "0 done"

  const headlineColor = g.mode === 'done'
    ? 'success.main'
    : remaining
      ? 'warning.main'
      : empty
        ? 'text.secondary' // muted: distinct from an actionable count
        : 'text.primary';  // neutral: 'queue' ("18 accounts to go") + accumulated

  return (
    <Stack spacing={0.5} sx={{ py: 1 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="baseline" spacing={1}>
        <Typography variant="body2" noWrap sx={{ maxWidth: '65%' }} title={label}>
          {label}
        </Typography>
        <Typography variant="subtitle2" color={headlineColor}>
          {g.headline}
        </Typography>
      </Stack>
      {/* No bar for the empty state — "0% of nothing" would re-introduce the cold ratio. */}
      {empty ? null : <LinearWithLabel value={g.pct} color={g.pct >= 100 ? 'success' : 'primary'} />}
    </Stack>
  );
}

GoalProgressRow.propTypes = {
  label: PropTypes.string,
  gradient: PropTypes.shape({
    pct: PropTypes.number,
    mode: PropTypes.string,
    headline: PropTypes.string,
  }),
};
