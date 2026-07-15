// frontend/src/__tests__/views/home/ManagerHome.test.jsx

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';

// ==============================|| MOCKS ||============================== //

vi.mock('next/font/google', () => ({
  Public_Sans: () => ({ className: 'mock-public-sans', style: { fontFamily: 'mock' } }),
}));
vi.mock('components/MainCard', () => ({
  default: ({ children, title }) => (
    <div data-testid="main-card">{title ? <div>{title}</div> : null}{children}</div>
  ),
}));

vi.mock('hooks/useUserPermissions', () => ({
  useUserPermissions: () => ({ currentUserId: 'mgr1' }),
}));

// Two teams — only the one managed by mgr1 must render a quota group.
vi.mock('api/admin/teams', () => ({
  useGetTeams: () => ({
    teams: [
      { id: 't1', name: 'Alpha', manager: { id: 'mgr1' } },
      { id: 't2', name: 'Beta', manager: { id: 'someone-else' } },
    ],
  }),
}));

vi.mock('api/quotas/quotas', () => ({
  useGetTeamQuotas: () => ({
    quotas: [{ id: 9, user_id: 'u1', user_name: 'Alice', target_type: 'meetings', name: 'Meetings Q3' }],
    quotasLoading: false,
  }),
}));

// useKpiBatch serves both blocks — branch on the request key.
vi.mock('api/bi/kpi', () => ({
  useKpiBatch: (reqs) => {
    const key = reqs?.[0]?.key;
    if (key === 'todo_team_by_owner') {
      return {
        results: [
          { value: { u1: 2 }, meta: { labels: { u1: 'Alice' } } }, // overdue window
          { value: { u1: 1, u2: 3 }, meta: { labels: { u1: 'Alice', u2: 'Bob' } } }, // today window
        ],
        resultsLoading: false,
        resultsError: null,
      };
    }
    if (key === 'quota_attainment') {
      return {
        results: [{ value: 80, meta: { current: 8, target: 10, target_type: 'meetings' } }],
        resultsLoading: false,
        resultsError: null,
      };
    }
    return { results: [], resultsLoading: false, resultsError: null };
  },
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import ManagerHome, { mergeTodo } from 'views/home/ManagerHome';

afterEach(() => cleanup());

describe('mergeTodo', () => {
  it('merges overdue + today by owner, resolves names, sorts overdue-first, drops zeros', () => {
    const people = mergeTodo([
      { value: { u1: 2 }, meta: { labels: { u1: 'Alice' } } },
      { value: { u1: 1, u2: 3 }, meta: { labels: { u1: 'Alice', u2: 'Bob' } } },
    ]);
    expect(people).toHaveLength(2);
    // Alice: 2 overdue + 1 today = 3 total, ranked first (overdue-first).
    expect(people[0]).toMatchObject({ name: 'Alice', overdue: 2, total: 3 });
    expect(people[1]).toMatchObject({ name: 'Bob', overdue: 0, total: 3 });
  });

  it('omits people with nothing pending', () => {
    const people = mergeTodo([{ value: {} }, { value: {} }]);
    expect(people).toEqual([]);
  });
});

describe('ManagerHome', () => {
  it('renders both blocks: per-person tasks (with names + overdue) and per-member quota', () => {
    render(<ManagerHome />);

    expect(screen.getByText("Were today's tasks done?")).toBeInTheDocument();
    expect(screen.getByText('Progress by person')).toBeInTheDocument();

    // Bloc 1 — names + overdue callout. (Alice also appears in bloc 2's quota
    // card, hence getAllByText.)
    expect(screen.getAllByText('Alice').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Bob')).toBeInTheDocument();
    expect(screen.getByText('2 overdue')).toBeInTheDocument();

    // Bloc 2 — only the managed team (Alpha), member name + remaining framing.
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.queryByText('Beta')).not.toBeInTheDocument();
    expect(screen.getByText('Meetings Q3')).toBeInTheDocument();
    expect(screen.getByText('Only 2 left')).toBeInTheDocument();
  });
});
