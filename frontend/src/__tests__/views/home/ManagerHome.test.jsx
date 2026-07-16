// frontend/src/__tests__/views/home/ManagerHome.test.jsx

import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';

// ==============================|| MOCKS ||============================== //

vi.mock('next/font/google', () => ({
  Public_Sans: () => ({ className: 'mock-public-sans', style: { fontFamily: 'mock' } }),
}));
vi.mock('components/MainCard', () => ({
  default: ({ children, title, onClick }) => (
    <div data-testid="main-card" onClick={onClick}>{title ? <div>{title}</div> : null}{children}</div>
  ),
}));

vi.mock('hooks/useUserPermissions', () => ({
  useUserPermissions: () => ({ currentUserId: 'mgr1' }),
}));
// Stateful useLocalStorage so the window filter actually updates on a tile click.
vi.mock('hooks/useLocalStorage', async () => {
  const React = await import('react');
  return { default: (_key, initial) => React.useState(initial) };
});

// Two teams — only the one managed by mgr1 must render a quota group.
vi.mock('api/admin/teams', () => ({
  useGetTeams: () => ({
    teams: [
      { id: 't1', name: 'Alpha', manager: { id: 'mgr1' } },
      { id: 't2', name: 'Beta', manager: { id: 'someone-else' } },
    ],
  }),
}));

// Quota group is untouched by E2 — stub it (its internals are covered elsewhere).
vi.mock('sections/home/TeamQuotaGroup', () => ({
  default: ({ teamName }) => <div data-testid="quota-group">{teamName}</div>,
}));

// The tiles: capture the options so we can assert the TEAM windows KPI is used.
let windowsOpts = null;
vi.mock('api/bi/todo', () => ({
  TODO_WINDOWS: { OVERDUE: 'overdue', TODAY: 'today', NEXT_7_DAYS: 'next_7_days', NEXT_4_WEEKS: 'next_4_weeks' },
  useGetTodoWindows: (opts) => {
    windowsOpts = opts;
    return { windows: { overdue: 2, today: 5, next_7_days: 8, next_4_weeks: 12 }, windowsLoading: false };
  },
}));

// Roster: the no-window per-owner breakdown feeds the Owner filter + chip.
vi.mock('api/bi/kpi', () => ({
  useKpi: (key) => {
    if (key === 'todo_team_by_owner') {
      return { kpi: { value: { u1: 3, u2: 3 }, meta: { labels: { u1: 'Alice', u2: 'Bob' } } } };
    }
    return { kpi: null };
  },
}));

// Stub the team table (pulls ReusableTable + the team todo hook); capture props.
let teamTableProps = null;
vi.mock('sections/home/TeamActivityTable', () => ({
  default: (props) => {
    teamTableProps = props;
    return <div data-testid="team-activity-table" />;
  },
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import ManagerHome, { managedTeamSubtree, rosterFromKpi } from 'views/home/ManagerHome';

beforeEach(() => {
  windowsOpts = null;
  teamTableProps = null;
});
afterEach(() => cleanup());

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

describe('ManagerHome — same screen as the rep, team scope', () => {
  it('renders the 4 window tiles + the team table + the per-member quota section', () => {
    render(<ManagerHome />);

    expect(screen.getByText('What the team has to do')).toBeInTheDocument();
    // the 4 tiles (real TodoBlock)
    expect(screen.getByText('Overdue')).toBeInTheDocument();
    expect(screen.getByText('Today')).toBeInTheDocument();
    expect(screen.getByText('Next 7 days')).toBeInTheDocument();
    expect(screen.getByText('Next 4 weeks')).toBeInTheDocument();
    // the table
    expect(screen.getByTestId('team-activity-table')).toBeInTheDocument();
    // the quota section — only the managed team (Alpha), not Beta
    expect(screen.getByText('Progress by person')).toBeInTheDocument();
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.queryByText('Beta')).not.toBeInTheDocument();
  });

  it('feeds the tiles from the TEAM windows KPI, not the rep one', () => {
    render(<ManagerHome />);
    expect(windowsOpts).toEqual({ scope: 'team', kpiKey: 'todo_team_windows' });
  });

  it('a tile drives the table window (default today; clicking Overdue switches it)', () => {
    render(<ManagerHome />);
    expect(teamTableProps.window).toBe('today'); // persisted default
    fireEvent.click(screen.getByText('Overdue'));
    expect(teamTableProps.window).toBe('overdue');
  });

  it('the roster feeds the Owner filter options + the chip name', () => {
    render(<ManagerHome />);
    // roster flows into the filter panel's person options...
    const roster = teamTableProps.advancedFilterPanel.props.personOptions;
    expect(roster).toEqual([
      { id: 'u1', name: 'Alice' },
      { id: 'u2', name: 'Bob' },
    ]);
    // ...and the subtree into the team options (both dimensions available).
    expect(teamTableProps.advancedFilterPanel.props.teamOptions.map((t) => t.id)).toEqual(['t1']);
  });

  it('window + team + owner coexist as three independent dimensions on the table', () => {
    render(<ManagerHome />);
    // all three props are wired; window is the persisted one, team/owner start empty
    expect(teamTableProps).toHaveProperty('window');
    expect(teamTableProps).toHaveProperty('team');
    expect(teamTableProps).toHaveProperty('owner');
    // changing the window does not touch team/owner
    fireEvent.click(screen.getByText('Next 7 days'));
    expect(teamTableProps.window).toBe('next_7_days');
    expect(teamTableProps.team).toBeUndefined();
    expect(teamTableProps.owner).toBeUndefined();
  });

  it('removing the Owner chip via the table clears the owner filter (no crash without the drill-down)', () => {
    render(<ManagerHome />);
    // The table's chip-remove path still works; owner starts empty so this is a no-op that must not throw.
    expect(() => teamTableProps.onAdvancedFilterRemove('owner')).not.toThrow();
    expect(teamTableProps.owner).toBeUndefined();
  });
});

describe('rosterFromKpi', () => {
  it('builds the owner options from a no-window breakdown, sorted by name', () => {
    const roster = rosterFromKpi({ value: { u2: 3, u1: 5 }, meta: { labels: { u1: 'Alice', u2: 'Bob' } } });
    expect(roster).toEqual([
      { id: 'u1', name: 'Alice' },
      { id: 'u2', name: 'Bob' },
    ]);
  });

  it('is empty for a missing result', () => {
    expect(rosterFromKpi(undefined)).toEqual([]);
  });
});
