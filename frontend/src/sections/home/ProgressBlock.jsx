// frontend/src/sections/home/ProgressBlock.jsx

import PropTypes from 'prop-types';
import NextLink from 'next/link';

import Grid from '@mui/material/Grid';
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
const EMPTY = { pct: 0, mode: 'empty', done: 0, total: 0, remaining: 0, headline: 'No accounts assigned' };

// A work-queue gradient over the ACTUAL account counts (never the %): campaigns
// and territories are queues of accounts to work, so the remaining is the
// actionable headline ("18 accounts to go" / "All done"). total===0 is a SETUP
// state ("No accounts assigned"), not "0 of N" — kept distinct here so the
// domain noun never leaks into the shared goalGradient. Exported so the manager
// TeamAggregateBlock frames its aggregate rows the same way (one queue vocab).
export function queueGradient(done, total) {
  if (!total) return EMPTY;
  return goalGradient(done, total, { framing: 'queue', noun: 'accounts' });
}

// campaign_progress meta carries accounts_completed / accounts_total.
function campaignGradient(result) {
  if (result?.value == null || !result?.meta) return UNAVAILABLE;
  return queueGradient(result.meta.accounts_completed, result.meta.accounts_total);
}

// territory_coverage meta carries numerator (covered) / denominator (total).
function territoryGradient(result) {
  if (result?.value == null || !result?.meta) return UNAVAILABLE;
  return queueGradient(result.meta.numerator, result.meta.denominator);
}

function coverageOf(item) {
  const v = item?.result?.value;
  return typeof v === 'number' ? v : Number.POSITIVE_INFINITY; // unavailable ranks last
}

function Rows({ items, gradientOf }) {
  return (
    <Stack divider={null}>
      {items.map(({ entity, result }) => (
        <GoalProgressRow key={entity.id} label={entity.name || 'Untitled'} gradient={gradientOf(result)} />
      ))}
    </Stack>
  );
}

Rows.propTypes = { items: PropTypes.array, gradientOf: PropTypes.func };

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
      <Grid item xs={12} md={6}>
        <MainCard title="Active campaigns">
          {loading ? (
            <CardSkeleton />
          ) : campaigns.length === 0 ? (
            <Empty text="No active campaigns." />
          ) : (
            <Rows items={campaigns} gradientOf={campaignGradient} />
          )}
        </MainCard>
      </Grid>
      <Grid item xs={12} md={6}>
        <MainCard title="Territory coverage">
          {loading ? (
            <CardSkeleton />
          ) : topTerritories.length === 0 ? (
            <Empty text="No territories yet." />
          ) : (
            <Stack spacing={1}>
              <Rows items={topTerritories} gradientOf={territoryGradient} />
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
