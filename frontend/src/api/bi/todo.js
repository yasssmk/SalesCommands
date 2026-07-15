// frontend/src/api/bi/todo.js

import { useMemo } from 'react';
import useSWR from 'swr';

import { useAuth } from 'hooks/useAuth';
import { tenantKey } from 'api/_swr';
import { useKpi } from 'api/bi/kpi';

// ==============================|| TODO — windows (counts) + rows ||============================== //

export const TODO_WINDOWS = {
  OVERDUE: 'overdue',
  TODAY: 'today',
  THIS_WEEK: 'this_week',
  THIS_MONTH: 'this_month',
};

export const endpoints = {
  todo: '/bi/todo/',
  teamTodo: '/bi/todo/team/',
};

/**
 * useGetTodoWindows — the 4 tile counts (overdue / today / this week / this
 * month) from the todo_my_windows KPI. Reuses useKpi so it inherits the BI
 * endpoint conventions; windows and the /bi/todo/ rows share one backend
 * population, so a tile count equals its window's row count by construction.
 */
export function useGetTodoWindows(options = {}) {
  const { scope = 'mine', enabled = true } = options;
  const { kpi, kpiLoading, kpiError, mutateKpi } = useKpi('todo_my_windows', { scope, enabled });

  return useMemo(
    () => ({
      windows: kpi?.value || {},
      windowsLoading: kpiLoading,
      windowsError: kpiError,
      mutateWindows: mutateKpi,
    }),
    [kpi, kpiLoading, kpiError, mutateKpi],
  );
}

export function buildTodoUrl({ scope, window, page, pageSize } = {}) {
  const qs = new URLSearchParams();
  if (scope) qs.append('scope', scope);
  if (window) qs.append('window', window);
  if (page) qs.append('page', page);
  if (pageSize) qs.append('page_size', pageSize);
  const q = qs.toString();
  return q ? `${endpoints.todo}?${q}` : endpoints.todo;
}

/**
 * useGetTodoActivities — the todo ROWS for one window, paginated, from
 * GET /bi/todo/. Same population as the tiles, sorted by effective_date.
 */
export function useGetTodoActivities(options = {}) {
  const { tenantId } = useAuth();
  const { scope = 'mine', window, page = 1, pageSize = 10, enabled = true } = options;

  const url = useMemo(
    () => buildTodoUrl({ scope, window, page, pageSize }),
    [scope, window, page, pageSize],
  );

  const swrKey = useMemo(
    () => (enabled ? tenantKey(url, tenantId) : null),
    [enabled, url, tenantId],
  );

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    dedupingInterval: 5000,
  });

  return useMemo(
    () => ({
      activities: data?.data?.results || data?.results || [],
      activitiesCount: data?.data?.count || data?.count || 0,
      activitiesLoading: isLoading,
      activitiesError: error,
      activitiesValidating: isValidating,
      mutateActivities: mutate,
      swrKey,
    }),
    [data, isLoading, error, isValidating, mutate, swrKey],
  );
}

export function buildTeamTodoUrl({ scope, team, owner, page, pageSize } = {}) {
  const qs = new URLSearchParams();
  if (scope) qs.append('scope', scope);
  if (team) qs.append('team', team);
  if (owner) qs.append('owner', owner);
  if (page) qs.append('page', page);
  if (pageSize) qs.append('page_size', pageSize);
  const q = qs.toString();
  return q ? `${endpoints.teamTodo}?${q}` : endpoints.teamTodo;
}

/**
 * useGetTeamTodoActivities — the MANAGER view's team todo ROWS, paginated, from
 * GET /bi/todo/team/. Same population as the todo_team_by_owner counts (open
 * activities, role-scoped, no personal invited-accepted union); narrowable to a
 * team subtree (team) and/or a single person (owner — the per-person drill-down
 * behind clicking a name in bloc 1). Mirrors useGetTodoActivities' return shape.
 */
export function useGetTeamTodoActivities(options = {}) {
  const { tenantId } = useAuth();
  const { scope = 'team', team, owner, page = 1, pageSize = 10, enabled = true } = options;

  const url = useMemo(
    () => buildTeamTodoUrl({ scope, team, owner, page, pageSize }),
    [scope, team, owner, page, pageSize],
  );

  const swrKey = useMemo(
    () => (enabled ? tenantKey(url, tenantId) : null),
    [enabled, url, tenantId],
  );

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    dedupingInterval: 5000,
  });

  return useMemo(
    () => ({
      activities: data?.data?.results || data?.results || [],
      activitiesCount: data?.data?.count || data?.count || 0,
      activitiesLoading: isLoading,
      activitiesError: error,
      activitiesValidating: isValidating,
      mutateActivities: mutate,
      swrKey,
    }),
    [data, isLoading, error, isValidating, mutate, swrKey],
  );
}
