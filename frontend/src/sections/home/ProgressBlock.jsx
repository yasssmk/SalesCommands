// frontend/src/sections/home/ProgressBlock.jsx

import PropTypes from 'prop-types';
import NextLink from 'next/link';

import Grid from '@mui/material/Unstable_Grid2';
import Link from '@mui/material/Link';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import MainCard from 'components/MainCard';

import GoalProgressRow from './GoalProgressRow';
import { goalGradient } from 'sections/home/utils/goalGradient';

// ==============================|| PROGRESS BLOCK — my campaigns + territories ||============================== //

// How many territories to surface; the rest stay one click away (never hidden
// silently). Ranking still computes coverage for ALL of them — this caps the
// display only, to protect the todo block above.
const TERRITORY_TOP_N = 3;

const UNAVAILABLE = { pct: 0, mode: 'none', headline: 'Unavailable' };

// campaign_progress / territory_coverage return a SCALAR percentage. Frame it on
// the 0..100 scale so the goal-gradient headline reads "only X% left" near the end.
function pctGradient(result) {
  const value = typeof result?.value === 'number' ? result.value : null;
  if (value == null) return UNAVAILABLE;
  return goalGradient(value, 100, { unit: '%' });
}

function coverageOf(item) {
  const v = item?.result?.value;
  return typeof v === 'number' ? v : Number.POSITIVE_INFINITY; // unavailable ranks last
}

function Rows({ items }) {
  return (
    <Stack divider={null}>
      {items.map(({ entity, result }) => (
        <GoalProgressRow key={entity.id} label={entity.name || 'Untitled'} gradient={pctGradient(result)} />
      ))}
    </Stack>
  );
}

Rows.propTypes = { items: PropTypes.array };

function CardSkeleton() {
  return (
    <Stack spacing={1.5} sx={{ py: 1 }}>
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} variant="rounded" height={40} />
      ))}
    </Stack>
  );
}

function Empty({ text }) {
  return (
    <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
      {text}
    </Typography>
  );
}

Empty.propTypes = { text: PropTypes.string };

/**
 * "My progress" — active campaigns and the least-covered territories. Campaigns
 * are already active-filtered upstream; territories are ranked lowest-coverage
 * first (most action needed) and capped to TERRITORY_TOP_N with a "see all"
 * affordance.
 */
export default function ProgressBlock({
  campaigns = [],
  territories = [],
  territoriesTotal = 0,
  loading = false,
}) {
  const rankedTerritories = [...territories].sort((a, b) => coverageOf(a) - coverageOf(b));
  const topTerritories = rankedTerritories.slice(0, TERRITORY_TOP_N);
  const hiddenCount = (territoriesTotal || territories.length) - topTerritories.length;

  return (
    <Grid container spacing={2}>
      <Grid xs={12} md={6}>
        <MainCard title="Active campaigns">
          {loading ? (
            <CardSkeleton />
          ) : campaigns.length === 0 ? (
            <Empty text="No active campaigns." />
          ) : (
            <Rows items={campaigns} />
          )}
        </MainCard>
      </Grid>
      <Grid xs={12} md={6}>
        <MainCard title="Territory coverage">
          {loading ? (
            <CardSkeleton />
          ) : topTerritories.length === 0 ? (
            <Empty text="No territories yet." />
          ) : (
            <Stack spacing={1}>
              <Rows items={topTerritories} />
              {hiddenCount > 0 ? (
                <Link component={NextLink} href="/territories" variant="caption" underline="hover">
                  See all ({territoriesTotal || territories.length})
                </Link>
              ) : null}
            </Stack>
          )}
        </MainCard>
      </Grid>
    </Grid>
  );
}

ProgressBlock.propTypes = {
  campaigns: PropTypes.array,
  territories: PropTypes.array,
  territoriesTotal: PropTypes.number,
  loading: PropTypes.bool,
};
