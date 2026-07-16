// frontend/src/views/home/RepHome.jsx

'use client';

import { useEffect, useMemo } from 'react';

import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import { useKpiBatch } from 'api/bi/kpi';
import { useGetTodoWindows } from 'api/bi/todo';
import { useGetMyCampaigns } from 'api/campaigns/campaigns';
import { useGetTerritories } from 'api/territories/territories';
import { useGetMyActiveQuotas } from 'api/quotas/quotas';
import { displayErrorSnackbar } from 'utils/displayError';
import useLocalStorage from 'hooks/useLocalStorage';

import TodoBlock from 'sections/home/TodoBlock';
import RepActivityTable from 'sections/home/RepActivityTable';
import ProgressBlock from 'sections/home/ProgressBlock';
import QuotaBlock from 'sections/home/QuotaBlock';

// ==============================|| REP HOME ||============================== //

/**
 * The rep's action-oriented Home. Three blocks answer: what do I have to do
 * today / this week? how am I progressing? where am I vs my result?
 *
 * The todo block fires standalone so it paints first, unblocked by the entity
 * lists. Everything else resolves the rep's OWN entities (mine paths — the bare
 * lists are tenant-wide by design), then fires ONE batch of parameterized KPIs.
 */
export default function RepHome() {
  // Block a — window counts drive the table below; the active filter persists.
  const [todoFilter, setTodoFilter] = useLocalStorage('repTodoFilter', 'today');
  const { windows, windowsLoading, windowsError } = useGetTodoWindows({ scope: 'mine' });

  // Entity resolution (mine paths).
  const { campaigns } = useGetMyCampaigns({ filters: { status: 'ACTIVE' } });
  const { territories, territoriesCount } = useGetTerritories({ filters: { owner_scope: 'mine' } });
  const { quotas } = useGetMyActiveQuotas();

  // Build the parameterized KPI requests, keeping the entity beside each so we
  // can zip results back by index (the batch preserves request order).
  const entityReqs = useMemo(() => {
    const reqs = [];
    (campaigns || []).forEach((c) =>
      reqs.push({ kind: 'campaign', entity: c, req: { key: 'campaign_progress', scope: 'mine', params: { campaign_id: c.id } } }),
    );
    (territories || []).forEach((t) =>
      reqs.push({ kind: 'territory', entity: t, req: { key: 'territory_coverage', scope: 'mine', params: { territory_id: t.id } } }),
    );
    (quotas || []).forEach((q) =>
      reqs.push({ kind: 'quota', entity: q, req: { key: 'quota_attainment', scope: 'mine', params: { quota_id: q.id } } }),
    );
    return reqs;
  }, [campaigns, territories, quotas]);

  const { results, resultsLoading, resultsError } = useKpiBatch(entityReqs.map((e) => e.req));

  const enriched = useMemo(
    () => entityReqs.map((e, i) => ({ ...e, result: results[i] || null })),
    [entityReqs, results],
  );
  const campaignResults = enriched.filter((e) => e.kind === 'campaign');
  const territoryResults = enriched.filter((e) => e.kind === 'territory');
  const quotaResults = enriched.filter((e) => e.kind === 'quota');

  // Surface fetch errors via the shared snackbar (never a silent blank block).
  useEffect(() => {
    if (windowsError) displayErrorSnackbar(windowsError);
  }, [windowsError]);
  useEffect(() => {
    if (resultsError) displayErrorSnackbar(resultsError);
  }, [resultsError]);

  return (
    <Stack spacing={4} sx={{ py: 1 }}>
      <Stack spacing={1.5}>
        <Box>
          <Typography variant="h5">What I have to do</Typography>
          <Typography variant="body2" color="text.secondary">
            Pick a window — overdue, today, next 7 days, next 4 weeks. Accepted invitations included.
          </Typography>
        </Box>
        <Stack spacing={2}>
          <TodoBlock
            windows={windows}
            activeFilter={todoFilter}
            onSelect={setTodoFilter}
            loading={windowsLoading}
          />
          <RepActivityTable window={todoFilter} scope="mine" />
        </Stack>
      </Stack>

      <Stack spacing={1.5}>
        <Box>
          <Typography variant="h5">My progress</Typography>
          <Typography variant="body2" color="text.secondary">
            Where your active campaigns and territories stand.
          </Typography>
        </Box>
        <ProgressBlock
          campaigns={campaignResults}
          territories={territoryResults}
          territoriesTotal={territoriesCount}
          loading={resultsLoading}
        />
      </Stack>

      <Stack spacing={1.5}>
        <Box>
          <Typography variant="h5">Where I am</Typography>
          <Typography variant="body2" color="text.secondary">
            Your result against target — and what&apos;s left.
          </Typography>
        </Box>
        <QuotaBlock quotas={quotaResults} loading={resultsLoading} />
      </Stack>
    </Stack>
  );
}
