// frontend/src/views/home/ManagerHome.jsx

'use client';

import { useMemo } from 'react';

import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import MainCard from 'components/MainCard';

import { useUserPermissions } from 'hooks/useUserPermissions';
import { useGetTeams } from 'api/admin/teams';
import { useKpiBatch } from 'api/bi/kpi';

import Section from './components/Section';
import TeamTodoBlock from './components/TeamTodoBlock';
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

// ==============================|| MANAGER HOME ||============================== //

/**
 * The manager's observer view: were today's tasks done (per person, with names)
 * and per-person quota progress. No personal-todo block — the manager watches
 * the team, they don't get their own action list here.
 */
export default function ManagerHome() {
  const { currentUserId } = useUserPermissions();
  const { teams } = useGetTeams();

  const managedTeams = useMemo(
    () => (teams || []).filter((t) => t?.manager && String(t.manager.id) === String(currentUserId)),
    [teams, currentUserId],
  );

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

  return (
    <Stack spacing={4} sx={{ py: 1 }}>
      <Section title="Were today's tasks done?" subtitle="Open tasks per person — overdue called out first.">
        <TeamTodoBlock people={people} loading={todoLoading} />
      </Section>

      <Section title="Progress by person" subtitle="Each member's quota attainment for the current period.">
        {managedTeams.length === 0 ? (
          <MainCard>
            <Typography variant="body2" color="text.secondary">
              No team to display yet.
            </Typography>
          </MainCard>
        ) : (
          <Stack spacing={2}>
            {managedTeams.map((t) => (
              <TeamQuotaGroup key={t.id} teamId={t.id} teamName={t.name} />
            ))}
          </Stack>
        )}
      </Section>
    </Stack>
  );
}
