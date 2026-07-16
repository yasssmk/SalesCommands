// frontend/src/views/home/ManagerHome.jsx

'use client';

import { useCallback, useMemo, useState } from 'react';

import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import MainCard from 'components/MainCard';

import { useUserPermissions } from 'hooks/useUserPermissions';
import useTeamTodoFilters from 'hooks/useTeamTodoFilters';
import { useGetTeams } from 'api/admin/teams';
import { useKpiBatch } from 'api/bi/kpi';

import TeamTodoBlock from 'sections/home/TeamTodoBlock';
import TeamActivityTable from 'sections/home/TeamActivityTable';
import TeamTodoFilterPanel from 'sections/home/TeamTodoFilterPanel';
import TeamQuotaGroup from 'sections/home/TeamQuotaGroup';

// Local ISO date (not UTC) — "today" must match the user's calendar day.
function localISODate(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

// Merge the overdue and today todo breakdowns into one per-person list.
export function mergeTodo(results) {
  const [overdueR, todayR] = results || [];
  const overdue = overdueR?.value || {};
  const today = todayR?.value || {};
  const labels = { ...(todayR?.meta?.labels || {}), ...(overdueR?.meta?.labels || {}) };
  const ids = new Set([...Object.keys(overdue), ...Object.keys(today)]);

  return [...ids]
    .map((id) => {
      const o = overdue[id] || 0;
      const t = today[id] || 0;
      return { id, name: labels[id] || 'Unknown', overdue: o, today: t, total: o + t };
    })
    .filter((p) => p.total > 0)
    .sort((a, b) => b.overdue - a.overdue || b.total - a.total);
}

// The full roster of owners with open tasks (a no-window todo_team_by_owner):
// the Person filter's options, sorted by name.
export function rosterFromKpi(result) {
  const value = result?.value || {};
  const labels = result?.meta?.labels || {};
  return Object.keys(value)
    .map((id) => ({ id, name: labels[id] || 'Unknown' }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

/**
 * The manager's managed team SUBTREE, reconstructed client-side exactly like the
 * backend's get_all_descendant_team_ids: start from the teams the user manages
 * DIRECTLY (roots), then walk DOWN via parent_team collecting every descendant —
 * regardless of a sub-team's own manager. (A sub-team managed by someone else is
 * still in the subtree because it descends from a team the user manages; keying
 * on manager.id or effective_manager.id alone would wrongly drop it.) The
 * returned list drives the team filter; it is display-only — the server's role
 * scope is the real boundary, so a selection can only ever narrow, never widen.
 */
export function managedTeamSubtree(teams, userId) {
  const list = teams || [];
  const uid = userId != null ? String(userId) : null;
  if (!uid) return [];

  // parentTeamId -> [child team, ...]
  const childrenByParent = new Map();
  list.forEach((t) => {
    const pid = t?.parent_team?.id != null ? String(t.parent_team.id) : null;
    if (!pid) return;
    if (!childrenByParent.has(pid)) childrenByParent.set(pid, []);
    childrenByParent.get(pid).push(t);
  });

  const roots = list.filter((t) => t?.manager?.id != null && String(t.manager.id) === uid);

  const seen = new Set();
  const result = [];
  const visit = (team) => {
    const id = String(team.id);
    if (seen.has(id)) return; // guard cycles + diamonds
    seen.add(id);
    result.push(team);
    (childrenByParent.get(id) || []).forEach(visit);
  };
  roots.forEach(visit);
  return result;
}

// ==============================|| MANAGER HOME ||============================== //

/**
 * The manager's observer view: were today's tasks done (per person, with names),
 * a team activity drill-down table with the standard filter (team + person), and
 * per-person quota progress. No personal-todo block — the manager watches the
 * team, they don't get their own action list here.
 */
export default function ManagerHome() {
  const { currentUserId } = useUserPermissions();
  const { teams } = useGetTeams();

  const subtree = useMemo(
    () => managedTeamSubtree(teams, currentUserId),
    [teams, currentUserId],
  );
  // Bloc 3 quota groups list the roots the manager owns directly.
  const managedRoots = useMemo(
    () => (teams || []).filter((t) => t?.manager && String(t.manager.id) === String(currentUserId)),
    [teams, currentUserId],
  );

  // The shared filter state (team + owner): the standard filter panel AND the
  // bloc-1 per-person drill-down both drive it.
  const {
    filters,
    pendingFilters,
    apiFilters,
    activeFiltersCount,
    updatePendingFilter,
    applyFilters,
    clearFilters,
    resetPendingFilters,
    applyFilterImmediate,
  } = useTeamTodoFilters();
  const [filterPanelOpen, setFilterPanelOpen] = useState(false);

  // Bloc 1 — today + overdue, per person; + a no-window breakdown for the Person
  // filter roster. One batch (team scope covers the whole hierarchy server-side).
  const { today, yesterday } = useMemo(() => {
    const now = new Date();
    return {
      today: localISODate(now),
      yesterday: localISODate(new Date(now.getTime() - 86400000)),
    };
  }, []);

  const todoReqs = useMemo(
    () => [
      { key: 'todo_team_by_owner', scope: 'team', period: 'custom', period_start: '1970-01-01', period_end: yesterday },
      { key: 'todo_team_by_owner', scope: 'team', period: 'custom', period_start: today, period_end: today },
      { key: 'todo_team_by_owner', scope: 'team' }, // roster: all open, by owner
    ],
    [today, yesterday],
  );

  const { results: todoResults, resultsLoading: todoLoading } = useKpiBatch(todoReqs);
  const people = useMemo(() => mergeTodo(todoResults), [todoResults]);
  const roster = useMemo(() => rosterFromKpi(todoResults?.[2]), [todoResults]);

  // Clicking a person toggles the owner filter (immediate — no Apply step);
  // clicking the active one clears it.
  const handleSelectPerson = useCallback(
    (id) => {
      applyFilterImmediate({ owner: String(filters.owner) === String(id) ? '' : id });
    },
    [applyFilterImmediate, filters.owner],
  );

  // Filter chips (rendered by the table): one per active filter, resolved to a name.
  const advancedFilters = useMemo(() => {
    const chips = [];
    if (filters.team) {
      const t = subtree.find((x) => String(x.id) === String(filters.team));
      chips.push({ key: 'team', label: 'Team', value: t?.name || 'Team' });
    }
    if (filters.owner) {
      const p = roster.find((x) => String(x.id) === String(filters.owner));
      chips.push({ key: 'owner', label: 'Person', value: p?.name || 'Person' });
    }
    return chips;
  }, [filters, subtree, roster]);

  const handleRemoveFilter = useCallback(
    (key) => applyFilterImmediate({ [key]: '' }),
    [applyFilterImmediate],
  );
  const handleOpenPanel = useCallback(() => {
    resetPendingFilters(); // panel opens reflecting the applied state
    setFilterPanelOpen(true);
  }, [resetPendingFilters]);

  const filterPanel = (
    <TeamTodoFilterPanel
      open={filterPanelOpen}
      onClose={() => setFilterPanelOpen(false)}
      pendingFilters={pendingFilters}
      teamOptions={subtree}
      personOptions={roster}
      onFilterChange={updatePendingFilter}
      onApply={applyFilters}
      onClear={clearFilters}
    />
  );

  return (
    <Stack spacing={4} sx={{ py: 1 }}>
      <Stack spacing={1.5}>
        <Box>
          <Typography variant="h5">Were today&apos;s tasks done?</Typography>
          <Typography variant="body2" color="text.secondary">
            Open tasks per person — overdue called out first. Click a name to see their tasks below.
          </Typography>
        </Box>
        <TeamTodoBlock
          people={people}
          loading={todoLoading}
          onSelectPerson={handleSelectPerson}
          selectedPersonId={filters.owner || null}
        />
      </Stack>

      <Stack spacing={1.5}>
        <Box>
          <Typography variant="h5">Team activity</Typography>
          <Typography variant="body2" color="text.secondary">
            The open tasks behind the numbers — filter by team or person, or click a name above.
          </Typography>
        </Box>
        <TeamActivityTable
          team={apiFilters.team}
          owner={apiFilters.owner}
          advancedFilterPanel={filterPanel}
          advancedFilters={advancedFilters}
          advancedFilterCount={activeFiltersCount}
          onAdvancedFilterOpen={handleOpenPanel}
          onAdvancedFilterRemove={handleRemoveFilter}
          onAdvancedFilterClear={clearFilters}
        />
      </Stack>

      <Stack spacing={1.5}>
        <Box>
          <Typography variant="h5">Progress by person</Typography>
          <Typography variant="body2" color="text.secondary">
            Each member&apos;s quota attainment for the current period.
          </Typography>
        </Box>
        {managedRoots.length === 0 ? (
          <MainCard>
            <Typography variant="body2" color="text.secondary">
              No team to display yet.
            </Typography>
          </MainCard>
        ) : (
          <Stack spacing={2}>
            {managedRoots.map((t) => (
              <TeamQuotaGroup key={t.id} teamId={t.id} teamName={t.name} />
            ))}
          </Stack>
        )}
      </Stack>
    </Stack>
  );
}
