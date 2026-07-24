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
import { useGetDecisionCycles } from 'api/accounts/decisionCycles';
import { displayErrorSnackbar } from 'utils/displayError';
import useLocalStorage from 'hooks/useLocalStorage';

import TodoBlock from 'sections/home/TodoBlock';
import RepActivityTable from 'sections/home/RepActivityTable';
import ProgressBlock from 'sections/home/ProgressBlock';
import DecisionCyclesBlock from 'sections/home/DecisionCyclesBlock';
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
  const { campaigns, campaignsCount, campaignsLoading } = useGetMyCampaigns({ filters: { status: 'ACTIVE' } });
  const { territories, territoriesCount, territoriesLoading } = useGetTerritories({ filters: { owner_scope: 'mine' } });
  const { quotas } = useGetMyActiveQuotas();
  // My OPEN decision cycles — possession (owner_scope=mine), open == outcome
  // IS NULL. The bare list is tenant-wide (read=client); these two params are
  // the "mine + open" path. is_active is NOT "open" (see the outcome filter).
  const { cycles: openCycles, cyclesError } = useGetDecisionCycles({
    filters: { owner_scope: 'mine', outcome__isnull: true },
  });

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
    (openCycles || []).forEach((c) =>
      reqs.push({ kind: 'dc', entity: c, req: { key: 'dc_cycle_state', scope: 'mine', params: { cycle_id: c.id } } }),
    );
    return reqs;
  }, [campaigns, territories, quotas, openCycles]);

  const { results, resultsLoading, resultsError } = useKpiBatch(entityReqs.map((e) => e.req));

  const enriched = useMemo(
    () => entityReqs.map((e, i) => ({ ...e, result: results[i] || null })),
    [entityReqs, results],
  );
  const campaignResults = enriched.filter((e) => e.kind === 'campaign');
  const territoryResults = enriched.filter((e) => e.kind === 'territory');
  const quotaResults = enriched.filter((e) => e.kind === 'quota');
  const cycleItems = useMemo(
    () => enriched.filter((e) => e.kind === 'dc').map((e) => ({ cycle: e.entity, result: e.result })),
    [enriched],
  );
  const hasOpenCycles = (openCycles || []).length > 0;

  // The progress cards must show their skeleton for the WHOLE load — the entity
  // lists (campaigns/territories) AND the KPI batch. The batch key is null while
  // the entity lists resolve, so resultsLoading is briefly false; without the
  // entity-loading flags the empty state ("No active campaigns.") flashes before
  // the entities arrive. Gate on both so the empty state only shows once loading
  // has settled and there is genuinely nothing.
  const progressLoading = campaignsLoading || territoriesLoading || resultsLoading;

  // Surface fetch errors via the shared snackbar (never a silent blank block).
  useEffect(() => {
    if (windowsError) displayErrorSnackbar(windowsError);
  }, [windowsError]);
  useEffect(() => {
    if (resultsError) displayErrorSnackbar(resultsError);
  }, [resultsError]);
  useEffect(() => {
    if (cyclesError) displayErrorSnackbar(cyclesError);
  }, [cyclesError]);

  // The section Stacks use `useFlexGap` so their spacing is CSS gap, not the
  // default child-margin reset (`& > * { margin: 0 }`). That reset would strip
  // the Grid blocks' negative-margin compensation and shift them off the
  // full-width table's edges — see the aligned reference (users/list keeps its
  // Grid out of a Stack).
  return (
    <Stack spacing={4} sx={{ py: 1 }}>
      <Stack spacing={1.5} useFlexGap>
        <Box>
          <Typography variant="h5">What I have to do</Typography>
          <Typography variant="body2" color="text.secondary">
            Pick a window — overdue, today, next 7 days, next 4 weeks. Accepted invitations included.
          </Typography>
        </Box>
        <Stack spacing={2} useFlexGap>
          <TodoBlock
            windows={windows}
            activeFilter={todoFilter}
            onSelect={setTodoFilter}
            loading={windowsLoading}
          />
          <RepActivityTable window={todoFilter} scope="mine" />
        </Stack>
      </Stack>

      <Stack spacing={1.5} useFlexGap>
        <Box>
          <Typography variant="h5">My progress</Typography>
          <Typography variant="body2" color="text.secondary">
            Where your active campaigns and territories stand.
          </Typography>
        </Box>
        <ProgressBlock
          campaigns={campaignResults}
          territories={territoryResults}
          campaignsTotal={campaignsCount}
          territoriesTotal={territoriesCount}
          loading={progressLoading}
        />
      </Stack>

      {/* Data-driven: the section appears only when the rep OWNS ≥1 open cycle
          — no role test. Hidden entirely (heading included) when there is none. */}
      {hasOpenCycles ? (
        <Stack spacing={1.5} useFlexGap>
          <Box>
            <Typography variant="h5">My decision cycles</Typography>
            <Typography variant="body2" color="text.secondary">
              Where each open deal stands — and the next move.
            </Typography>
          </Box>
          <DecisionCyclesBlock items={cycleItems} loading={resultsLoading} />
        </Stack>
      ) : null}

      <Stack spacing={1.5} useFlexGap>
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
