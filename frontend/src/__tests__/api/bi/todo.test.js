// frontend/src/__tests__/api/bi/todo.test.js

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, cleanup } from '@testing-library/react';

const useSWRMock = vi.fn(() => ({ data: undefined, isLoading: false, error: null, mutate: vi.fn() }));
vi.mock('swr', () => ({ default: (key, a, b) => useSWRMock(key, a, b) }));

vi.mock('hooks/useAuth', () => ({ useAuth: () => ({ tenantId: 'tenant-123' }) }));

vi.mock('api/_swr', () => ({
  tenantKey: (url, tenantId) => (url && tenantId ? [url, tenantId] : null),
}));

import {
  useGetTodoWindows,
  useGetTodoActivities,
  buildTodoUrl,
  buildTeamTodoUrl,
  TODO_WINDOWS,
} from 'api/bi/todo';

beforeEach(() => {
  vi.clearAllMocks();
  useSWRMock.mockImplementation(() => ({ data: undefined, isLoading: false, error: null, mutate: vi.fn() }));
});
afterEach(() => cleanup());

describe('buildTodoUrl', () => {
  it('builds the base url with no options', () => {
    expect(buildTodoUrl()).toBe('/bi/todo/');
  });
  it('appends scope, window, page, page_size', () => {
    expect(buildTodoUrl({ scope: 'mine', window: 'today', page: 2, pageSize: 25 })).toBe(
      '/bi/todo/?scope=mine&window=today&page=2&page_size=25',
    );
  });
});

describe('buildTeamTodoUrl', () => {
  it('builds the base team url with no options', () => {
    expect(buildTeamTodoUrl()).toBe('/bi/todo/team/');
  });
  it('appends scope, team, owner, page, page_size', () => {
    expect(buildTeamTodoUrl({ scope: 'team', team: 't1', owner: 'u9', page: 2, pageSize: 25 })).toBe(
      '/bi/todo/team/?scope=team&team=t1&owner=u9&page=2&page_size=25',
    );
  });
});

describe('TODO_WINDOWS', () => {
  it('matches the backend window keys', () => {
    expect(TODO_WINDOWS).toEqual({
      OVERDUE: 'overdue',
      TODAY: 'today',
      THIS_WEEK: 'this_week',
      THIS_MONTH: 'this_month',
    });
  });
});

describe('useGetTodoWindows', () => {
  it('reads the todo_my_windows KPI, keyed by scope + tenant', () => {
    renderHook(() => useGetTodoWindows({ scope: 'mine' }));
    const [key] = useSWRMock.mock.calls[0];
    expect(key).toEqual(['/bi/kpi/todo_my_windows/?scope=mine', 'tenant-123']);
  });

  it('unwraps the window counts from the KPI value', () => {
    useSWRMock.mockReturnValue({
      data: { data: { value: { overdue: 2, today: 1, this_week: 3, this_month: 5 } } },
      isLoading: false,
      error: null,
      mutate: vi.fn(),
    });
    const { result } = renderHook(() => useGetTodoWindows());
    expect(result.current.windows).toEqual({ overdue: 2, today: 1, this_week: 3, this_month: 5 });
  });
});

describe('useGetTodoActivities', () => {
  it('keys on the /bi/todo/ url (scope + window + page) + tenant', () => {
    renderHook(() => useGetTodoActivities({ scope: 'mine', window: 'overdue', page: 1, pageSize: 10 }));
    const [key] = useSWRMock.mock.calls[0];
    expect(key).toEqual(['/bi/todo/?scope=mine&window=overdue&page=1&page_size=10', 'tenant-123']);
  });

  it('passes a null key when disabled', () => {
    renderHook(() => useGetTodoActivities({ enabled: false }));
    const [key] = useSWRMock.mock.calls[0];
    expect(key).toBeNull();
  });

  it('unwraps paginated rows + count', () => {
    useSWRMock.mockReturnValue({
      data: { data: { results: [{ id: 'a1' }], count: 1 } },
      isLoading: false,
      error: null,
      mutate: vi.fn(),
    });
    const { result } = renderHook(() => useGetTodoActivities({ window: 'today' }));
    expect(result.current.activities).toEqual([{ id: 'a1' }]);
    expect(result.current.activitiesCount).toBe(1);
  });
});
