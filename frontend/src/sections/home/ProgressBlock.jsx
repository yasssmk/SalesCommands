// frontend/src/sections/home/ProgressBlock.jsx

import PropTypes from 'prop-types';
import NextLink from 'next/link';

import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Link from '@mui/material/Link';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import MainCard from 'components/MainCard';

import GoalProgressRow from './GoalProgressRow';
import { goalGradient } from 'sections/home/utils/goalGradient';

// ==============================|| PROGRESS BLOCK — my campaigns + territories ||============================== //

// How many rows each card surfaces; the rest stay one click away (never hidden
// silently — the hidden count is kept per card). Shared by BOTH cards so they
// have an identical, stable footprint. Ranking still runs over ALL entities —
// this caps the display only, to protect the todo block above.
const PROGRESS_TOP_N = 5;

// Reserved height of ONE GoalProgressRow, used to hold the rows zone at a fixed
// height (PROGRESS_TOP_N rows) across loading / empty / populated — so the two
// cards never differ in height and the block never jumps as data settles.
// Derived from the row's own box (constant across modes since the bar space is
// always reserved): vertical padding (py:1 → 2 × 8px = 16) + the subtitle2
// headline line (~22px) + the inner gap (spacing 0.5 → 4px) + the progress-bar
// row (~18px) ≈ 60px, rounded up to a safe upper bound so 5 real rows never
// exceed the reserved zone (only over-reservation preserves equal heights).
const ROW_HEIGHT = 64;
const ROWS_MIN_HEIGHT = PROGRESS_TOP_N * ROW_HEIGHT;

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

// The KPI value already on the row (same source the gradient reads). A missing
// value ranks last — used for the territory ranking and the campaign date tie-break.
function coverageOf(item) {
  const v = item?.result?.value;
  return typeof v === 'number' ? v : Number.POSITIVE_INFINITY; // unavailable ranks last
}

// Campaign ordering: soonest deadline first (planned_end_date is non-nullable on
// the model, so no null branch), then LOWER progress first on a date tie — read
// from the same KPI source as the row's gradient (coverageOf), so a missing KPI
// ranks last exactly as it does for territories.
function byDeadlineThenProgress(a, b) {
  const da = a?.entity?.planned_end_date;
  const db = b?.entity?.planned_end_date;
  if (da !== db) return da < db ? -1 : 1; // ISO 'YYYY-MM-DD' sorts lexicographically
  return coverageOf(a) - coverageOf(b);
}

// Cap a ranked list to PROGRESS_TOP_N and report how many stay hidden (kept per
// card so a "see all" affordance can surface them — never hidden silently).
export function rank(sortedItems, total) {
  const top = sortedItems.slice(0, PROGRESS_TOP_N);
  const hiddenCount = (total || sortedItems.length) - top.length;
  return { top, hiddenCount };
}

function Rows({ items, gradientOf, hrefOf }) {
  return (
    <Stack divider={null}>
      {items.map(({ entity, result }) => (
        <GoalProgressRow
          key={entity.id}
          label={entity.name || 'Untitled'}
          gradient={gradientOf(result)}
          href={hrefOf ? hrefOf(entity) : undefined}
        />
      ))}
    </Stack>
  );
}

Rows.propTypes = { items: PropTypes.array, gradientOf: PropTypes.func, hrefOf: PropTypes.func };

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

// The rows zone: a fixed-height slot (PROGRESS_TOP_N rows) shared by the
// populated / empty / loading states so the card never jumps and both cards
// match. The height is RESERVED on the container — no phantom rows (which would
// leave dangling dividers and empty a11y rows).
function RowsZone({ testid, children }) {
  return (
    <Box data-testid={testid} style={{ minHeight: ROWS_MIN_HEIGHT }}>
      {children}
    </Box>
  );
}

RowsZone.propTypes = { testid: PropTypes.string, children: PropTypes.node };

// Permanent "See all" footer, present on BOTH cards (symmetric) regardless of how
// many rows are hidden — even at 0 entity. `total` is the real entity count; it
// is 0 while loading or when there are none, so the count is dropped ("See all")
// rather than showing a misleading "(0)".
function SeeAll({ href, total }) {
  return (
    <Box sx={{ mt: 1 }}>
      <Link component={NextLink} href={href} variant="caption" underline="hover">
        {total > 0 ? `See all (${total})` : 'See all'}
      </Link>
    </Box>
  );
}

SeeAll.propTypes = { href: PropTypes.string, total: PropTypes.number };

/**
 * "My progress" — the rep's active campaigns and least-covered territories. Both
 * cards rank and cap to PROGRESS_TOP_N and reserve the same fixed-height rows
 * zone: campaigns are ordered by soonest deadline then lowest progress;
 * territories are ordered lowest-coverage first (most action needed). Each row's
 * name links to its workspace; both cards carry a permanent "See all" footer
 * (campaigns → the ACTIVE-filtered list, territories → the list).
 */
export default function ProgressBlock({
  campaigns = [],
  territories = [],
  campaignsTotal = 0,
  territoriesTotal = 0,
  loading = false,
}) {
  const rankedCampaigns = [...campaigns].sort(byDeadlineThenProgress);
  const campaignRank = rank(rankedCampaigns, campaignsTotal);

  const rankedTerritories = [...territories].sort((a, b) => coverageOf(a) - coverageOf(b));
  const territoryRank = rank(rankedTerritories, territoriesTotal);

  return (
    <Grid container spacing={2}>
      <Grid item xs={12} md={6}>
        <MainCard title="Active campaigns">
          <RowsZone testid="progress-rows-zone-campaigns">
            {loading ? (
              <CardSkeleton />
            ) : campaignRank.top.length === 0 ? (
              <Empty text="No active campaigns." />
            ) : (
              <Rows items={campaignRank.top} gradientOf={campaignGradient} hrefOf={(e) => `/campaigns/${e.id}`} />
            )}
          </RowsZone>
          <SeeAll href="/campaigns?status=ACTIVE" total={campaignsTotal} />
        </MainCard>
      </Grid>
      <Grid item xs={12} md={6}>
        <MainCard title="Territory coverage">
          <RowsZone testid="progress-rows-zone-territories">
            {loading ? (
              <CardSkeleton />
            ) : territoryRank.top.length === 0 ? (
              <Empty text="No territories yet." />
            ) : (
              <Rows items={territoryRank.top} gradientOf={territoryGradient} hrefOf={(e) => `/territories/${e.id}`} />
            )}
          </RowsZone>
          <SeeAll href="/territories" total={territoriesTotal} />
        </MainCard>
      </Grid>
    </Grid>
  );
}

ProgressBlock.propTypes = {
  campaigns: PropTypes.array,
  territories: PropTypes.array,
  campaignsTotal: PropTypes.number,
  territoriesTotal: PropTypes.number,
  loading: PropTypes.bool,
};
