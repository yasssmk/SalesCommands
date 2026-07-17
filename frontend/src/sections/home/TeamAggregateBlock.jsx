// frontend/src/sections/home/TeamAggregateBlock.jsx

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

// ==============================|| TEAM AGGREGATE BLOCK — manager compact aggregate ||============================== //
//
// The COMPACT "by team" view for the manager: a global line ("All teams") + one
// line per managed team, read from ONE aggregate request (campaign_progress_by_team
// or territory_progress_by_team) instead of ~N per-entity calls. Rows use the
// rep's queue framing ("X accounts to go"). Both aggregates share this shape
// (meta.global + meta.per_group + meta.labels), so this block is parameterised
// rather than duplicated — the frontend pendant of bi/definitions/aggregates.py.
//
// `globalNote` is the ONLY per-domain difference: campaigns pass a "counts once"
// caption+tooltip (a shared campaign lands in two team rows but counts once
// globally, so global != sum of rows); territories pass none (one owner per
// territory -> global == sum of rows, a note would be false).
//
// No per-entity rows and no drill-down here: that is the dedicated view (TD-91),
// which does not exist yet — so there is deliberately no "See detail" link.

const GLOBAL_LABEL = 'All teams';

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
 * "By team" manager aggregate — global + per-team, queue-framed.
 *
 * @param {string} title      - the card title ("Team campaigns" / "Team territories").
 * @param {Object} result     - the aggregate KPI result ({ meta:{ labels, per_group, global } }).
 * @param {boolean} loading
 * @param {string} emptyText  - shown when there are no team rows (keeps the card
 *        present, like the rep's ProgressBlock — same two-card row, never a
 *        phantom empty column).
 * @param {?{caption:string, tooltip:string}} globalNote - optional caption+tooltip
 *        under the global row (campaigns only; territories pass none).
 */
export default function TeamAggregateBlock({
  title,
  result = null,
  loading = false,
  emptyText = 'Nothing yet.',
  globalNote = null,
}) {
  const rows = teamRows(result);
  const global = result?.meta?.global || null;

  return (
    <MainCard title={title} contentSX={{ p: 0 }}>
      <Box sx={{ px: 2.5, py: 1 }}>
        {loading ? (
          <Stack divider={<Divider />}>
            {[0, 1, 2].map((i) => (
              <RowSkeleton key={i} />
            ))}
          </Stack>
        ) : rows.length === 0 ? (
          // Empty state, NOT null: the card stays so the manager row mirrors the
          // rep's ProgressBlock (two cards, one showing its empty message).
          <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
            {emptyText}
          </Typography>
        ) : (
          <Stack divider={<Divider />}>
            {/* Global — all managed teams together. */}
            <Box sx={{ py: 0.5 }}>
              <GoalProgressRow
                label={GLOBAL_LABEL}
                gradient={global ? queueGradient(global.done, global.total) : undefined}
              />
              {globalNote ? (
                <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mt: -0.5 }}>
                  <Typography variant="caption" color="text.secondary">
                    {globalNote.caption}
                  </Typography>
                  <Tooltip title={globalNote.tooltip}>
                    <Box component="span" sx={{ display: 'inline-flex', color: 'text.disabled', cursor: 'help' }}>
                      <InfoCircleOutlined style={{ fontSize: 12 }} />
                    </Box>
                  </Tooltip>
                </Stack>
              ) : null}
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

TeamAggregateBlock.propTypes = {
  title: PropTypes.string,
  result: PropTypes.object,
  loading: PropTypes.bool,
  emptyText: PropTypes.string,
  globalNote: PropTypes.shape({
    caption: PropTypes.string,
    tooltip: PropTypes.string,
  }),
};
