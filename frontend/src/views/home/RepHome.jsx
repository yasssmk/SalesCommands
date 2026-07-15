// frontend/src/views/home/RepHome.jsx

'use client';

import PropTypes from 'prop-types';
import { useEffect, useMemo } from 'react';

import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import { useKpi, useKpiBatch } from 'api/bi/kpi';
import { useGetMyCampaigns } from 'api/campaigns/campaigns';
import { useGetTerritories } from 'api/territories/territories';
import { useGetMyActiveQuotas } from 'api/quotas/quotas';
import { displayErrorSnackbar } from 'utils/displayError';

import TodoBlock from './components/TodoBlock';
import ProgressBlock from './components/ProgressBlock';
import QuotaBlock from './components/QuotaBlock';

// ==============================|| SECTION WRAPPER ||============================== //

function Section({ title, subtitle, children }) {
  return (
    <Stack spacing={1.5}>
      <Box>
        <Typography variant="h5">{title}</Typography>
        {subtitle ? (
          <Typography variant="body2" color="text.secondary">
            {subtitle}
          </Typography>
        ) : null}
      </Box>
      {children}
    </Stack>
  );
}

Section.propTypes = {
  title: PropTypes.string,
  subtitle: PropTypes.string,
  children: PropTypes.node,
};

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
  // Block a — standalone, paints first.
  const { kpi: todo, kpiLoading: todoLoading, kpiError: todoError } = useKpi('todo_my_activities', {
    scope: 'mine',
  });

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
    if (todoError) displayErrorSnackbar(todoError);
  }, [todoError]);
  useEffect(() => {
    if (resultsError) displayErrorSnackbar(resultsError);
  }, [resultsError]);

  return (
    <Stack spacing={4} sx={{ py: 1 }}>
      <Section title="What I have to do" subtitle="Today, overdue and this week — accepted invitations included.">
        <TodoBlock value={todo?.value} loading={todoLoading} />
      </Section>

      <Section title="My progress" subtitle="Where your active campaigns and territories stand.">
        <ProgressBlock
          campaigns={campaignResults}
          territories={territoryResults}
          territoriesTotal={territoriesCount}
          loading={resultsLoading}
        />
      </Section>

      <Section title="Where I am" subtitle="Your result against target — and what's left.">
        <QuotaBlock quotas={quotaResults} loading={resultsLoading} />
      </Section>
    </Stack>
  );
}
