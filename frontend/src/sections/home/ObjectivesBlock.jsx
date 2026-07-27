// frontend/src/sections/home/ObjectivesBlock.jsx

'use client';

import { useMemo } from 'react';
import PropTypes from 'prop-types';

import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import MainCard from 'components/MainCard';

import { useUserPermissions } from 'hooks/useUserPermissions';
import { useGetObjectives } from 'api/objectives/objectives';
import { goalGradient } from 'sections/home/utils/goalGradient';
import { metricLabel, isMonetaryMetric } from 'sections/objectives/metricLabels';
import GoalProgressRow from './GoalProgressRow';
import { PROGRESS_TOP_N, RowsZone, SeeAll } from './ProgressBlock';

// ==============================|| OBJECTIVES BLOCK — my active objectives ||============================== //

// Route of the "My Objectives" page (app/(protected)/objectives/page.jsx →
// URL /objectives; same constant as ProfileTab.OBJECTIVES_ROUTE). The "See all"
// footer links here.
export const OBJECTIVES_ROUTE = '/objectives';

// "Focus now" ordering WITHIN the current group: soonest END date first, then
// lowest attainment first — both straight from the payload (period_end,
// progress_ratio), never recomputed. Same secondary keys as the My Objectives
// page's focusOrder and ProgressBlock's byDeadlineThenProgress; the state key is
// dropped here because every row is already CURRENT.
function byEndThenAttainment(a, b) {
  const endA = a.period_end || '';
  const endB = b.period_end || '';
  if (endA !== endB) return endA < endB ? -1 : 1; // ISO dates compare lexically
  const rA = a.progress_ratio == null ? Infinity : Number(a.progress_ratio);
  const rB = b.progress_ratio == null ? Infinity : Number(b.progress_ratio);
  return rA - rB;
}

// Map ONE objective payload to GoalProgressRow inputs — the SAME mapping the My
// Objectives page's ObjectiveCard uses (goalGradient over current/target, the
// non-clamped progress_ratio as the over-achievement signal), so the row renders
// identically (bar, gold over-achievement, remaining-work headline). No href —
// Home objective rows are not clickable.
function ObjectiveRow({ objective }) {
  const { metric, target_value, current_value, progress_ratio } = objective;
  const monetary = isMonetaryMetric(metric);
  const target = Number(target_value) || 0;
  const current = Number(current_value) || 0;
  const unit = monetary ? '$' : '';
  const gradient = goalGradient(current, target, { unit });
  const ratio = progress_ratio == null ? null : Number(progress_ratio);
  return (
    <GoalProgressRow label={metricLabel(metric)} gradient={gradient} overAchievementRatio={ratio} />
  );
}

ObjectiveRow.propTypes = { objective: PropTypes.object };

function CardSkeleton() {
  return (
    <Stack spacing={1.5} sx={{ py: 1 }}>
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} variant="rounded" height={40} />
      ))}
    </Stack>
  );
}

/**
 * "My objectives" — the connected user's CURRENT objectives (window covers
 * today). Mirror of ProgressBlock: a MainCard with a fixed-height RowsZone capped
 * to PROGRESS_TOP_N and a permanent "See all" footer.
 *
 * These are the user's OWN objectives, never their team's: the list is filtered
 * server-side on `owner = currentUserId` (a manager's read scope is the team, so
 * without this filter the block would show the whole team). The attainment on
 * each row is still the backend's — computed over the owner's recursive subtree
 * for a manager — read from the payload, not recomputed here.
 *
 * "Current" is a DERIVED state (no server filter for it — the viewset filters
 * metric/source_campaign/owner only), so the CURRENT slice is taken client-side
 * on the payload `state`, exactly as the My Objectives page does.
 */
export default function ObjectivesBlock() {
  const { currentUserId } = useUserPermissions();

  // Own objectives only (owner filter), and enough rows that the client-side
  // CURRENT slice below is never truncated by pagination (page_size up to the
  // documented max). filters is memoised + read as a stable object; the hook
  // itself JSON.stringifies it, so no refetch loop from an inline literal.
  const filters = useMemo(
    () => (currentUserId ? { owner: currentUserId, page_size: 100 } : {}),
    [currentUserId],
  );
  const { objectives, objectivesLoading } = useGetObjectives({
    filters,
    enabled: Boolean(currentUserId),
  });

  // Keep the skeleton until the user id is known too — with the fetch gated off
  // (enabled:false) SWR is not "loading", which would otherwise flash the empty
  // state before the real request fires.
  const loading = !currentUserId || objectivesLoading;

  const topCurrent = useMemo(() => {
    const currents = (objectives || []).filter((o) => o.state === 'CURRENT');
    return [...currents].sort(byEndThenAttainment).slice(0, PROGRESS_TOP_N);
  }, [objectives]);

  return (
    <MainCard title="Active objectives">
      <RowsZone testid="objectives-rows-zone">
        {loading ? (
          <CardSkeleton />
        ) : topCurrent.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
            No active objectives.
          </Typography>
        ) : (
          <Stack divider={null}>
            {topCurrent.map((objective) => (
              <ObjectiveRow key={objective.id} objective={objective} />
            ))}
          </Stack>
        )}
      </RowsZone>
      {/* Permanent "See all" (mirror of ProgressBlock). No reliable server total
          of CURRENT objectives exists (the count is all-states, and a client
          tally is pagination-bounded), so the count is dropped → "See all" nu,
          the documented ProgressBlock fallback. */}
      <SeeAll href={OBJECTIVES_ROUTE} />
    </MainCard>
  );
}
