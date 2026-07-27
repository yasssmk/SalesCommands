// frontend/src/sections/home/GoalProgressRow.jsx

import PropTypes from 'prop-types';
import NextLink from 'next/link';

import Box from '@mui/material/Box';
import Link from '@mui/material/Link';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import StarFilled from '@ant-design/icons/StarFilled';

import LinearWithLabel from 'components/@extended/progress/LinearWithLabel';

// ==============================|| GOAL PROGRESS ROW — label + bar + framed headline ||============================== //

/**
 * One progress line: the entity label, a determinate bar, and the
 * goal-gradient headline ("32 done" early / "only 8 left" near the end). The
 * `gradient` is a pre-computed result of goalGradient(); rendering is decoupled
 * from framing so callers own the units and thresholds.
 *
 * OPTIONAL over-achievement (`overAchievementRatio`): when a caller passes a
 * ratio > 1 (e.g. the objectives page reading the API's non-clamped
 * progress_ratio), the row shows the REAL percentage (e.g. "130%", not "100%"),
 * a star, and a full bar in the theme's `warning.dark`. When the prop is absent
 * or <= 1 the row renders EXACTLY as before — the Home consumers pass nothing,
 * so their output is unchanged.
 */
export default function GoalProgressRow({ label, gradient, href, overAchievementRatio }) {
  const g = gradient || { pct: 0, mode: 'none', headline: '' };
  const remaining = g.mode === 'remaining';
  const empty = g.mode === 'empty'; // no work to size — a setup state, not "0 done"

  const over = overAchievementRatio != null && overAchievementRatio > 1;
  // Real, uncapped percentage for the over-achievement bar (130 for 1.30).
  const overPct = over ? Math.round(overAchievementRatio * 100) : null;

  const headlineColor = over
    ? 'warning.dark'
    : g.mode === 'done'
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
        <Stack direction="row" alignItems="center" spacing={0.5}>
          {over && (
            <Box
              component="span"
              aria-label="over-achieved"
              sx={{ color: 'warning.dark', display: 'inline-flex', alignItems: 'center' }}
            >
              <StarFilled />
            </Box>
          )}
          <Typography variant="subtitle2" color={headlineColor}>
            {g.headline}
          </Typography>
        </Stack>
      </Stack>
      {/* The bar's height is ALWAYS reserved so every row is the same height
          regardless of mode. In the 'empty' state the bar stays in the layout but
          is hidden — no visible "0% of nothing", which would re-introduce the cold
          ratio — so the reserved height is the real component's own height, never a
          magic number. */}
      <Box style={{ visibility: empty ? 'hidden' : 'visible' }} data-over-achieved={over || undefined}>
        {over ? (
          // Over-achievement: the bar's VISUAL value is capped to 100 so it is a
          // FULL bar keeping the SAME fill token as a normal 100% bar
          // (color="success") at ANY percentage — MUI's determinate bar shifts
          // off-screen (renders empty) for value > 100, so an uncapped 300 would
          // look like the empty state. The LABEL still shows the REAL, uncapped
          // percentage (via labelValue). Only the star (above) and the % label
          // carry the theme's gold (warning.dark) to signal the overrun.
          <LinearWithLabel
            value={Math.min(overPct, 100)}
            labelValue={overPct}
            color="success"
            labelColor="warning.dark"
          />
        ) : (
          <LinearWithLabel value={g.pct} color={g.pct >= 100 ? 'success' : 'primary'} />
        )}
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
  // Optional — the API's non-clamped attainment ratio. > 1 triggers the
  // over-achievement rendering; absent / <= 1 keeps the row exactly as before.
  overAchievementRatio: PropTypes.number,
};
