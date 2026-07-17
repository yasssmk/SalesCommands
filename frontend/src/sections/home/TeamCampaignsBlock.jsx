// frontend/src/sections/home/TeamCampaignsBlock.jsx

'use client';

import PropTypes from 'prop-types';

import Box from '@mui/material/Box';
import Divider from '@mui/material/Divider';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

import InfoCircleOutlined from '@ant-design/icons/InfoCircleOutlined';

import MainCard from 'components/MainCard';

import GoalProgressRow from './GoalProgressRow';
import { queueGradient } from './ProgressBlock';

// ==============================|| TEAM CAMPAIGNS BLOCK — manager aggregate ||============================== //
//
// The COMPACT campaign view for the manager: a global line + one line per
// managed team, from the ONE campaign_progress_by_team request (not ~100
// per-campaign calls). Rows use the SAME queue framing as the rep's progress
// ("X accounts to go") — a team's remaining accounts is its actionable backlog.
// No per-campaign rows and no owner drill-down here: that is the dedicated DC/
// campaign view (TD-91), which does not exist yet — so there is deliberately no
// "See detail" link (a button that leads nowhere is worse than none).

const GLOBAL_TOOLTIP =
  'Shared campaigns (owned by one team, run by another) count once here, so the global is not the sum of the team rows.';

function teamRows(result) {
  const meta = result?.meta || {};
  const labels = meta.labels || {};
  const perGroup = meta.per_group || {};
  return Object.entries(perGroup)
    .map(([id, g]) => ({ id, name: labels[id] || 'Team', total: g.total, done: g.done, pct: g.progress_pct }))
    .sort((a, b) => a.pct - b.pct); // lowest progress first — most action needed
}

function RowSkeleton() {
  return <Skeleton variant="rounded" height={40} sx={{ my: 0.5 }} />;
}

/**
 * "Team campaigns" — the manager's aggregate. Global + per-team, queue-framed.
 *
 * @param {Object} result - the campaign_progress_by_team KPI result ({ meta:{
 *                          labels, per_group, global } }).
 * @param {boolean} loading
 */
export default function TeamCampaignsBlock({ result = null, loading = false }) {
  const rows = teamRows(result);
  const global = result?.meta?.global || null;

  if (!loading && rows.length === 0) return null; // data-driven: no team campaigns -> no block

  return (
    <MainCard title="Team campaigns" contentSX={{ p: 0 }}>
      <Box sx={{ px: 2.5, py: 1 }}>
        {loading ? (
          <Stack divider={<Divider />}>
            {[0, 1, 2].map((i) => (
              <RowSkeleton key={i} />
            ))}
          </Stack>
        ) : (
          <Stack divider={<Divider />}>
            {/* Global — all managed teams together. */}
            <Box sx={{ py: 0.5 }}>
              <GoalProgressRow
                label="All teams"
                gradient={global ? queueGradient(global.done, global.total) : undefined}
              />
              <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mt: -0.5 }}>
                <Typography variant="caption" color="text.secondary">
                  Shared campaigns count once
                </Typography>
                <Tooltip title={GLOBAL_TOOLTIP}>
                  <Box component="span" sx={{ display: 'inline-flex', color: 'text.disabled', cursor: 'help' }}>
                    <InfoCircleOutlined style={{ fontSize: 12 }} />
                  </Box>
                </Tooltip>
              </Stack>
            </Box>

            {/* Per managed team, lowest progress first. */}
            {rows.map((r) => (
              <GoalProgressRow key={r.id} label={r.name} gradient={queueGradient(r.done, r.total)} />
            ))}
          </Stack>
        )}
      </Box>
    </MainCard>
  );
}

TeamCampaignsBlock.propTypes = {
  result: PropTypes.object,
  loading: PropTypes.bool,
};
