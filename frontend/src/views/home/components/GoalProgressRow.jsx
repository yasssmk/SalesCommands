// frontend/src/views/home/components/GoalProgressRow.jsx

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

  return (
    <Stack spacing={0.5} sx={{ py: 1 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="baseline" spacing={1}>
        <Typography variant="body2" noWrap sx={{ maxWidth: '65%' }} title={label}>
          {label}
        </Typography>
        <Typography
          variant="subtitle2"
          color={g.mode === 'done' ? 'success.main' : remaining ? 'warning.main' : 'text.primary'}
        >
          {g.headline}
        </Typography>
      </Stack>
      <LinearWithLabel value={g.pct} color={g.pct >= 100 ? 'success' : 'primary'} />
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
