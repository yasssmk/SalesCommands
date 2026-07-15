// frontend/src/views/home/components/TeamQuotaGroup.jsx

'use client';

import PropTypes from 'prop-types';
import { useMemo } from 'react';

import Grid from '@mui/material/Unstable_Grid2';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import MainCard from 'components/MainCard';
import LinearWithLabel from 'components/@extended/progress/LinearWithLabel';

import { useGetTeamQuotas } from 'api/quotas/quotas';
import { useKpiBatch } from 'api/bi/kpi';
import { goalGradient } from 'views/home/utils/goalGradient';
import { unitFor, labelForType } from 'views/home/utils/quotaFormat';

// ==============================|| TEAM QUOTA GROUP — one team's per-member attainment ||============================== //

/**
 * Manager bloc 2 (one per managed team): each member's quota attainment for the
 * current period, framed as what's LEFT near the finish. Fetches the team's
 * active quotas (client-scoped, narrowed by team), then batches quota_attainment
 * per quota (scope=team, so a member's quota is reachable). Names come from the
 * quota's user_name; no roster call needed.
 */
export default function TeamQuotaGroup({ teamId, teamName }) {
  const { quotas, quotasLoading } = useGetTeamQuotas(teamId);

  const reqs = useMemo(
    () => (quotas || []).map((q) => ({ key: 'quota_attainment', scope: 'team', params: { quota_id: q.id } })),
    [quotas],
  );
  const { results, resultsLoading } = useKpiBatch(reqs);
  const loading = quotasLoading || resultsLoading;

  const cards = useMemo(
    () => (quotas || []).map((q, i) => ({ quota: q, result: results[i] || null })),
    [quotas, results],
  );

  return (
    <MainCard title={teamName}>
      {loading ? (
        <Grid container spacing={2}>
          {[0, 1].map((i) => (
            <Grid xs={12} sm={6} key={i}>
              <Skeleton variant="rounded" height={110} />
            </Grid>
          ))}
        </Grid>
      ) : cards.length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
          No active quotas in this team.
        </Typography>
      ) : (
        <Grid container spacing={2}>
          {cards.map(({ quota, result }) => {
            const meta = result?.meta || {};
            const targetType = meta.target_type || quota.target_type;
            const unit = unitFor(targetType);
            const hasCounts = meta.current != null && meta.target != null;
            const g = hasCounts ? goalGradient(meta.current, meta.target, { unit }) : null;

            return (
              <Grid xs={12} sm={6} key={quota.id}>
                <Stack spacing={0.5} sx={{ p: 1 }}>
                  <Typography variant="subtitle2" noWrap title={quota.user_name}>
                    {quota.user_name || 'Member'}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {quota.name || labelForType(targetType)}
                  </Typography>
                  {g ? (
                    <>
                      <Typography
                        variant="h5"
                        color={g.mode === 'done' ? 'success.main' : g.mode === 'remaining' ? 'warning.main' : 'primary.main'}
                      >
                        {g.headline}
                      </Typography>
                      <LinearWithLabel value={g.pct} color={g.pct >= 100 ? 'success' : 'primary'} />
                    </>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      {typeof result?.value === 'number' ? `${result.value}% attained` : 'Not available'}
                    </Typography>
                  )}
                </Stack>
              </Grid>
            );
          })}
        </Grid>
      )}
    </MainCard>
  );
}

TeamQuotaGroup.propTypes = {
  teamId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  teamName: PropTypes.string,
};
