// frontend/src/sections/home/DecisionCyclesBlock.jsx

'use client';

import PropTypes from 'prop-types';
import { useRouter } from 'next/navigation';

import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import MainCard from 'components/MainCard';

import {
  CYCLE_DERIVED_STATUS_LABELS,
  CYCLE_STATUS_COLORS,
} from 'api/accounts/decisionCycles';

// ==============================|| DECISION CYCLES BLOCK — my open deals ||============================== //
//
// One row per OPEN decision cycle the rep OWNS (the list is resolved with
// owner_scope=mine&outcome__isnull=true — possession, not account inheritance).
// The row's name/account come from the LIST (the KPI does not carry them); the
// stage / derived status / next action / "X/N stages" come from the
// dc_cycle_state KPI meta, zipped by index. NO percentage — the state and the
// next move are the signal, not a ratio.

// STALLED = the lever: force it to error (red), consistent with the overdue-red
// of the todo tiles. The shared CYCLE_STATUS_COLORS maps STALLED to 'warning'
// (a soft caution); that divergence is logged as tech debt to reconcile in the
// UI-homogenisation sprint — we override locally here rather than mutate the
// shared table (which is consumed elsewhere).
const STATUS_COLOR = { ...CYCLE_STATUS_COLORS, STALLED: 'error' };

// Statuses whose next action is "act now" — the call-to-action turns red.
const ACT_NOW = new Set(['STALLED', 'OVERDUE']);

// A navigable label: default color, primary + underline on HOVER only — the
// repo link convention (matches ActivityTable / accounts list / todo table).
function RowLink({ label, onClick, variant = 'body2', color }) {
  return (
    <Typography
      variant={variant}
      color={color}
      sx={{ cursor: 'pointer', '&:hover': { color: 'primary.main', textDecoration: 'underline' } }}
      onClick={onClick}
    >
      {label}
    </Typography>
  );
}

RowLink.propTypes = {
  label: PropTypes.string,
  onClick: PropTypes.func,
  variant: PropTypes.string,
  color: PropTypes.string,
};

function Dot() {
  return (
    <Typography component="span" variant="body2" color="text.disabled" aria-hidden>
      ·
    </Typography>
  );
}

function RowSkeleton() {
  return (
    <Stack spacing={0.75} sx={{ py: 1 }}>
      <Skeleton variant="text" width="45%" height={22} />
      <Skeleton variant="text" width="70%" height={18} />
    </Stack>
  );
}

function CycleRow({ cycle, result }) {
  const router = useRouter();

  const meta = result?.meta || {};
  const status = result?.value || meta.cycle_status || null;
  const statusLabel = status ? CYCLE_DERIVED_STATUS_LABELS[status] || status : null;
  const statusColor = status ? STATUS_COLOR[status] || 'default' : 'default';

  const accountId = cycle.account; // list serializer: account = id
  const accountName = cycle.account_name || 'Account';
  const stageName = meta.current_step_name || null;
  const validated = meta.validated_steps;
  const total = meta.total_steps;
  const hasStages = typeof validated === 'number' && typeof total === 'number' && total > 0;
  const nextAction = meta.next_action || null;

  return (
    <Stack spacing={0.5} sx={{ py: 1.25 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
        <RowLink
          label={cycle.name || 'Decision cycle'}
          variant="subtitle2"
          onClick={() => router.push(`/accounts/${accountId}/dc/${cycle.id}`)}
        />
        {statusLabel ? <Chip size="small" label={statusLabel} color={statusColor} /> : null}
      </Stack>

      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
        <RowLink
          label={accountName}
          color="text.secondary"
          onClick={() => router.push(`/accounts/${accountId}`)}
        />
        {stageName ? (
          <>
            <Dot />
            <Typography variant="body2" color="text.secondary">
              {stageName}
            </Typography>
          </>
        ) : null}
        {hasStages ? (
          <>
            <Dot />
            <Typography variant="body2" color="text.secondary">
              {validated}/{total} stages
            </Typography>
          </>
        ) : null}
      </Stack>

      {nextAction ? (
        <Typography variant="body2" color={ACT_NOW.has(status) ? 'error.main' : 'text.primary'}>
          {nextAction}
        </Typography>
      ) : null}
    </Stack>
  );
}

CycleRow.propTypes = {
  cycle: PropTypes.object,
  result: PropTypes.object,
};

/**
 * "My decision cycles" — the rep's OPEN cycles, each with its current stage,
 * derived status (STALLED in red = the lever), the next action, and "X/N
 * stages" as secondary. Data-driven visibility: with no open cycle the block
 * renders NOTHING (the caller also gates the section) — there is no role test,
 * an SDR who owns a campaign-spawned cycle sees it here.
 *
 * @param {Array} items - [{ cycle, result }] index-aligned; cycle from the list
 *                        hook, result from the dc_cycle_state batch.
 * @param {boolean} loading - the KPI batch is still resolving (cycles known).
 */
export default function DecisionCyclesBlock({ items = [], loading = false }) {
  if (!loading && items.length === 0) return null; // data-driven: no open cycle -> no block

  return (
    <MainCard title="My decision cycles" contentSX={{ p: 0 }}>
      {loading ? (
        <Box sx={{ px: 2.5 }}>
          <Stack divider={<Divider />}>
            {[0, 1, 2].map((i) => (
              <RowSkeleton key={i} />
            ))}
          </Stack>
        </Box>
      ) : (
        <Box sx={{ px: 2.5 }}>
          <Stack divider={<Divider />}>
            {items.map(({ cycle, result }) => (
              <CycleRow key={cycle.id} cycle={cycle} result={result} />
            ))}
          </Stack>
        </Box>
      )}
    </MainCard>
  );
}

DecisionCyclesBlock.propTypes = {
  items: PropTypes.array,
  loading: PropTypes.bool,
};
