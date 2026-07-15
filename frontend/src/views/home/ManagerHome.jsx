// frontend/src/views/home/ManagerHome.jsx

'use client';

import { useCallback, useMemo, useState } from 'react';

import Chip from '@mui/material/Chip';
import MenuItem from '@mui/material/MenuItem';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import MainCard from 'components/MainCard';

import { useUserPermissions } from 'hooks/useUserPermissions';
import useLocalStorage from 'hooks/useLocalStorage';
import { useGetTeams } from 'api/admin/teams';
import { useKpiBatch } from 'api/bi/kpi';

import Section from './components/Section';
import TeamTodoBlock from './components/TeamTodoBlock';
import TeamActivityTable from './components/TeamActivityTable';
import TeamQuotaGroup from './components/TeamQuotaGroup';

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

/**
 * The manager's managed team SUBTREE, reconstructed client-side exactly like the
 * backend's get_all_descendant_team_ids: start from the teams the user manages
 * DIRECTLY (roots), then walk DOWN via parent_team collecting every descendant —
 * regardless of a sub-team's own manager. (A sub-team managed by someone else is
 * still in the subtree because it descends from a team the user manages; keying
 * on manager.id or effective_manager.id alone would wrongly drop it.) The
 * returned list drives the team selector; it is display-only — the server's role
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
 * a team activity drill-down table, and per-person quota progress. No
 * personal-todo block — the manager watches the team, they don't get their own
 * action list here.
 */
export default function ManagerHome() {
  const { currentUserId } = useUserPermissions();
  const { teams } = useGetTeams();

  const subtree = useMemo(
    () => managedTeamSubtree(teams, currentUserId),
    [teams, currentUserId],
  );
  // Bloc 2 quota groups list the roots the manager owns directly.
  const managedRoots = useMemo(
    () => (teams || []).filter((t) => t?.manager && String(t.manager.id) === String(currentUserId)),
    [teams, currentUserId],
  );

  // Bloc 3 drill-down state: the selected team (persisted — a stable working
  // context) and the selected person (ephemeral — a transient drill-down).
  const [selectedTeam, setSelectedTeam] = useLocalStorage('managerTodoTeam', '');
  const [selectedOwner, setSelectedOwner] = useState(null);

  // Bloc 1 — today + overdue, per person. One batch (team scope covers the whole
  // hierarchy server-side), split into two windows so overdue can be flagged.
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
    ],
    [today, yesterday],
  );

  const { results: todoResults, resultsLoading: todoLoading } = useKpiBatch(todoReqs);
  const people = useMemo(() => mergeTodo(todoResults), [todoResults]);

  // Clicking a person toggles the owner filter; clicking the active one clears it.
  const handleSelectPerson = useCallback(
    (id) => setSelectedOwner((prev) => (String(prev) === String(id) ? null : id)),
    [],
  );

  // Picking a team is a fresh context — drop the person drill-down.
  const handleSelectTeam = useCallback(
    (value) => {
      setSelectedTeam(value);
      setSelectedOwner(null);
    },
    [setSelectedTeam],
  );

  // The selected team may have disappeared (re-org); fall back to "all".
  const teamValue = useMemo(
    () => (subtree.some((t) => String(t.id) === String(selectedTeam)) ? selectedTeam : ''),
    [subtree, selectedTeam],
  );
  const selectedOwnerName = useMemo(
    () => people.find((p) => String(p.id) === String(selectedOwner))?.name || null,
    [people, selectedOwner],
  );

  return (
    <Stack spacing={4} sx={{ py: 1 }}>
      <Section title="Were today's tasks done?" subtitle="Open tasks per person — overdue called out first. Click a name to see their tasks below.">
        <TeamTodoBlock
          people={people}
          loading={todoLoading}
          onSelectPerson={handleSelectPerson}
          selectedPersonId={selectedOwner}
        />
      </Section>

      <Section title="Team activity" subtitle="The open tasks behind the numbers — filter by team, or click a person above.">
        <Stack spacing={2}>
          <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
            <TextField
              select
              size="small"
              label="Team"
              value={teamValue}
              onChange={(e) => handleSelectTeam(e.target.value)}
              sx={{ minWidth: 220 }}
            >
              <MenuItem value="">All my teams</MenuItem>
              {subtree.map((t) => (
                <MenuItem key={t.id} value={t.id}>
                  {t.name}
                </MenuItem>
              ))}
            </TextField>
            {selectedOwner ? (
              <Chip
                label={`Person: ${selectedOwnerName || 'selected'}`}
                onDelete={() => setSelectedOwner(null)}
                color="primary"
                variant="combined"
                size="small"
              />
            ) : null}
          </Stack>
          <TeamActivityTable team={teamValue || undefined} owner={selectedOwner || undefined} />
        </Stack>
      </Section>

      <Section title="Progress by person" subtitle="Each member's quota attainment for the current period.">
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
      </Section>
    </Stack>
  );
}
