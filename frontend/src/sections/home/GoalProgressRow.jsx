// frontend/src/sections/home/GoalProgressRow.jsx

import PropTypes from 'prop-types';
import NextLink from 'next/link';

import Box from '@mui/material/Box';
import Link from '@mui/material/Link';
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
export default function GoalProgressRow({ label, gradient, href }) {
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
        {/* When `href` is given the label is a link (MUI Link + NextLink, the
            repo's row-link convention: text colour, primary + underline on hover).
            These rows never navigate as a whole, so there is no onClick and no
            stopPropagation. Absent href → the label renders exactly as before. */}
        {href ? (
          <Link
            component={NextLink}
            href={href}
            variant="body2"
            noWrap
            underline="hover"
            color="text.primary"
            title={label}
            sx={{ maxWidth: '65%', cursor: 'pointer', '&:hover': { color: 'primary.main' } }}
          >
            {label}
          </Link>
        ) : (
          <Typography variant="body2" noWrap sx={{ maxWidth: '65%' }} title={label}>
            {label}
          </Typography>
        )}
        <Typography variant="subtitle2" color={headlineColor}>
          {g.headline}
        </Typography>
      </Stack>
      {/* The bar's height is ALWAYS reserved so every row is the same height
          regardless of mode. In the 'empty' state the bar stays in the layout but
          is hidden — no visible "0% of nothing", which would re-introduce the cold
          ratio — so the reserved height is the real component's own height, never a
          magic number. */}
      <Box style={{ visibility: empty ? 'hidden' : 'visible' }}>
        <LinearWithLabel value={g.pct} color={g.pct >= 100 ? 'success' : 'primary'} />
      </Box>
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
  // Optional — when set, the label is rendered as a link to this href.
  href: PropTypes.string,
};
