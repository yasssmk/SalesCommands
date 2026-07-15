// frontend/src/__tests__/views/home/ManagerHome.test.jsx

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';

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
vi.mock('hooks/useLocalStorage', () => ({ default: () => ['', vi.fn()] }));

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

// Stub the team activity table (pulls ReusableTable + the team todo hook) and
// capture its props so we can assert the person drill-down flows through.
let teamTableProps = null;
vi.mock('views/home/components/TeamActivityTable', () => ({
  default: (props) => {
    teamTableProps = props;
    return <div data-testid="team-activity-table" />;
  },
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

import ManagerHome, { mergeTodo, managedTeamSubtree } from 'views/home/ManagerHome';

afterEach(() => {
  cleanup();
  teamTableProps = null;
});

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

describe('managedTeamSubtree', () => {
  // EMEA(me) └ France(managed by Bob!) └ Paris ; Sales US(Carol) └ NYC
  const teams = [
    { id: 'emea', name: 'EMEA', manager: { id: 'me' }, parent_team: null },
    { id: 'france', name: 'France', manager: { id: 'bob' }, parent_team: { id: 'emea' } },
    { id: 'paris', name: 'Paris', manager: null, parent_team: { id: 'france' } },
    { id: 'us', name: 'Sales US', manager: { id: 'carol' }, parent_team: null },
    { id: 'nyc', name: 'NYC', manager: null, parent_team: { id: 'us' } },
  ];

  it('includes a sub-team that has its OWN manager (the trap) and deep descendants', () => {
    const ids = managedTeamSubtree(teams, 'me').map((t) => t.id);
    // France is Bob-managed but descends from EMEA (mine) -> INCLUDED. Paris (depth 2) too.
    expect(new Set(ids)).toEqual(new Set(['emea', 'france', 'paris']));
  });

  it("excludes another manager's tree entirely", () => {
    const ids = managedTeamSubtree(teams, 'me').map((t) => t.id);
    expect(ids).not.toContain('us');
    expect(ids).not.toContain('nyc');
  });

  it('returns nothing when the user manages no team, or has no id', () => {
    expect(managedTeamSubtree(teams, 'nobody')).toEqual([]);
    expect(managedTeamSubtree(teams, null)).toEqual([]);
    expect(managedTeamSubtree(undefined, 'me')).toEqual([]);
  });
});

describe('ManagerHome', () => {
  it('renders the three blocks: per-person tasks, team activity table, per-member quota', () => {
    render(<ManagerHome />);

    expect(screen.getByText("Were today's tasks done?")).toBeInTheDocument();
    expect(screen.getByText('Team activity')).toBeInTheDocument();
    expect(screen.getByText('Progress by person')).toBeInTheDocument();

    // Bloc 1 — names + overdue callout. (Alice also appears in bloc 3's quota
    // card, hence getAllByText.)
    expect(screen.getAllByText('Alice').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Bob')).toBeInTheDocument();
    expect(screen.getByText('2 overdue')).toBeInTheDocument();

    // Bloc 2 — the team activity drill-down table is mounted.
    expect(screen.getByTestId('team-activity-table')).toBeInTheDocument();

    // Bloc 3 — only the managed team (Alpha), member name + remaining framing.
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.queryByText('Beta')).not.toBeInTheDocument();
    expect(screen.getByText('Meetings Q3')).toBeInTheDocument();
    expect(screen.getByText('Only 2 left')).toBeInTheDocument();
  });

  it('clicking a person filters the team activity table on that owner (drill-down)', () => {
    render(<ManagerHome />);

    // No owner filter initially.
    expect(teamTableProps.owner).toBeUndefined();

    // Click Alice's bloc-1 row (index 0 — bloc 3 also renders "Alice").
    fireEvent.click(screen.getAllByText('Alice')[0]);
    expect(teamTableProps.owner).toBe('u1');

    // Clicking the active person again clears the filter.
    fireEvent.click(screen.getAllByText('Alice')[0]);
    expect(teamTableProps.owner).toBeUndefined();
  });
});
