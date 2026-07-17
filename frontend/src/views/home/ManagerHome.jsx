// frontend/src/views/home/ManagerHome.jsx

'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import MainCard from 'components/MainCard';

import { useUserPermissions } from 'hooks/useUserPermissions';
import useTeamTodoFilters from 'hooks/useTeamTodoFilters';
import useLocalStorage from 'hooks/useLocalStorage';
import { useGetTeams } from 'api/admin/teams';
import { useGetTodoWindows } from 'api/bi/todo';
import { useGetCampaigns } from 'api/campaigns/campaigns';
import { useGetTerritories } from 'api/territories/territories';
import { useGetDecisionCycles } from 'api/accounts/decisionCycles';
import { useKpi, useKpiBatch } from 'api/bi/kpi';
import { displayErrorSnackbar } from 'utils/displayError';

import TodoBlock from 'sections/home/TodoBlock';
import TeamActivityTable from 'sections/home/TeamActivityTable';
import TeamTodoFilterPanel from 'sections/home/TeamTodoFilterPanel';
import ProgressBlock from 'sections/home/ProgressBlock';
import DecisionCyclesBlock from 'sections/home/DecisionCyclesBlock';
import TeamQuotaGroup from 'sections/home/TeamQuotaGroup';

// The full roster of owners with open tasks (a no-window todo_team_by_owner):
// the Owner filter's options + the chip name, sorted by name.
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
 * The manager's Home — the SAME screen as the rep, widened to the team scope:
 * the 4 window tiles (team totals) drive a team activity table. There is no
 * per-person block; "who's behind" is reached by sorting/filtering the table on
 * Owner. Extra dimensions the rep lacks: a Team filter and an Owner filter (+
 * their chips). Quota stays per person below — a quota is inherently personal.
 */
export default function ManagerHome() {
  const { currentUserId } = useUserPermissions();
  const { teams } = useGetTeams();

  const subtree = useMemo(
    () => managedTeamSubtree(teams, currentUserId),
    [teams, currentUserId],
  );
  // The quota groups list the roots the manager owns directly.
  const managedRoots = useMemo(
    () => (teams || []).filter((t) => t?.manager && String(t.manager.id) === String(currentUserId)),
    [teams, currentUserId],
  );

  // The shared filter state (team + owner), driven by the standard filter panel.
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

  // Window is the third dimension (with team + owner). Persisted under a key
  // distinct from the rep's 'repTodoFilter' so the two Homes never collide.
  const [windowFilter, setWindowFilter] = useLocalStorage('managerTodoFilter', 'today');

  // Tiles: team totals per window, from todo_team_windows (the /bi/todo/team/
  // population — NOT todo_my_windows, which would fold in the manager's personal
  // accepted invitations). Same source as the table -> tile count == rows.
  const { windows, windowsLoading } = useGetTodoWindows({ scope: 'team', kpiKey: 'todo_team_windows' });

  // Roster: the no-window per-owner breakdown feeds the Owner filter's options
  // AND resolves the Owner chip's name. (This is the ONLY todo_team_by_owner
  // call left — the per-person overdue/today batches are gone with the block.)
  const { kpi: rosterKpi } = useKpi('todo_team_by_owner', { scope: 'team' });
  const roster = useMemo(() => rosterFromKpi(rosterKpi), [rosterKpi]);

  // Team progress + team decision cycles — the SAME blocks as the rep, in team
  // scope. The entity LISTS are read=client, so owner_scope=team is REQUIRED (a
  // bare list would be tenant-wide). Then ONE batch of parameterized KPIs at
  // scope='team'.
  const { campaigns } = useGetCampaigns({ filters: { owner_scope: 'team', status: 'ACTIVE' } });
  const { territories, territoriesCount } = useGetTerritories({ filters: { owner_scope: 'team' } });
  // My team's OPEN decision cycles. owner_scope=team routes through the mixin
  // (unchanged by the C6 fix, which only diverted 'mine'); open == outcome IS NULL.
  const { cycles: openCycles } = useGetDecisionCycles({
    filters: { owner_scope: 'team', outcome__isnull: true },
  });

  const entityReqs = useMemo(() => {
    const reqs = [];
    (campaigns || []).forEach((c) =>
      reqs.push({ kind: 'campaign', entity: c, req: { key: 'campaign_progress', scope: 'team', params: { campaign_id: c.id } } }),
    );
    (territories || []).forEach((t) =>
      reqs.push({ kind: 'territory', entity: t, req: { key: 'territory_coverage', scope: 'team', params: { territory_id: t.id } } }),
    );
    (openCycles || []).forEach((c) =>
      reqs.push({ kind: 'dc', entity: c, req: { key: 'dc_cycle_state', scope: 'team', params: { cycle_id: c.id } } }),
    );
    return reqs;
  }, [campaigns, territories, openCycles]);

  // useKpiBatch chunks at BATCH_CAP (20) client-side, so a team with many
  // campaigns+territories+cycles fans out over several POSTs and still zips by index.
  const { results, resultsLoading, resultsError } = useKpiBatch(entityReqs.map((e) => e.req));
  const enriched = useMemo(
    () => entityReqs.map((e, i) => ({ ...e, result: results[i] || null })),
    [entityReqs, results],
  );
  const campaignResults = enriched.filter((e) => e.kind === 'campaign');
  const territoryResults = enriched.filter((e) => e.kind === 'territory');
  const cycleItems = useMemo(
    () => enriched.filter((e) => e.kind === 'dc').map((e) => ({ cycle: e.entity, result: e.result })),
    [enriched],
  );
  const hasOpenCycles = (openCycles || []).length > 0;

  useEffect(() => {
    if (resultsError) displayErrorSnackbar(resultsError);
  }, [resultsError]);

  // Filter chips (rendered by the table): one per active filter, resolved to a name.
  const advancedFilters = useMemo(() => {
    const chips = [];
    if (filters.team) {
      const t = subtree.find((x) => String(x.id) === String(filters.team));
      chips.push({ key: 'team', label: 'Team', value: t?.name || 'Team' });
    }
    if (filters.owner) {
      const p = roster.find((x) => String(x.id) === String(filters.owner));
      chips.push({ key: 'owner', label: 'Owner', value: p?.name || 'Owner' });
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
      {/* Tiles + table share a useFlexGap Stack so the tile Grid's negative
          margins are not stripped by the default child-margin reset (same as
          RepHome). */}
      <Stack spacing={1.5} useFlexGap>
        <Box>
          <Typography variant="h5">What the team has to do</Typography>
          <Typography variant="body2" color="text.secondary">
            Pick a window — overdue, today, next 7 days, next 4 weeks. Filter or sort by team and owner to zoom in.
          </Typography>
        </Box>
        <Stack spacing={2} useFlexGap>
          <TodoBlock
            windows={windows}
            activeFilter={windowFilter}
            onSelect={setWindowFilter}
            loading={windowsLoading}
          />
          <TeamActivityTable
            team={apiFilters.team}
            owner={apiFilters.owner}
            window={windowFilter}
            advancedFilterPanel={filterPanel}
            advancedFilters={advancedFilters}
            advancedFilterCount={activeFiltersCount}
            onAdvancedFilterOpen={handleOpenPanel}
            onAdvancedFilterRemove={handleRemoveFilter}
            onAdvancedFilterClear={clearFilters}
          />
        </Stack>
      </Stack>

      <Stack spacing={1.5} useFlexGap>
        <Box>
          <Typography variant="h5">Team progress</Typography>
          <Typography variant="body2" color="text.secondary">
            Where your team&apos;s active campaigns and territories stand.
          </Typography>
        </Box>
        <ProgressBlock
          campaigns={campaignResults}
          territories={territoryResults}
          territoriesTotal={territoriesCount}
          loading={resultsLoading}
        />
      </Stack>

      {/* Data-driven: the section appears only when the team OWNS >=1 open cycle
          — no role test. Owner · Team line via showOwner ("who carries this"). */}
      {hasOpenCycles ? (
        <Stack spacing={1.5} useFlexGap>
          <Box>
            <Typography variant="h5">Team decision cycles</Typography>
            <Typography variant="body2" color="text.secondary">
              Where each open team deal stands — and who carries it.
            </Typography>
          </Box>
          <DecisionCyclesBlock
            items={cycleItems}
            loading={resultsLoading}
            showOwner
            title="Team decision cycles"
          />
        </Stack>
      ) : null}

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
