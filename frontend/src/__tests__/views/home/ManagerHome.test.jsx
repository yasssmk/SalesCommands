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

// Roster + the two aggregates (useKpi) + the DC batch (useKpiBatch). Capture the
// aggregates' scope and the batch requests so we can assert scope:'team' reaches
// the KPIs and that NO per-entity progress request remains.
let kpiBatchReqs = null;
let campaignKpiOpts = null;
let territoryKpiOpts = null;
function _aggregate(labels, perGroup, global) {
  return { kpi: { value: {}, meta: { dimension: 'team', labels, per_group: perGroup, global } }, kpiLoading: false };
}
vi.mock('api/bi/kpi', () => ({
  useKpi: (key, opts) => {
    if (key === 'todo_team_by_owner') {
      return { kpi: { value: { u1: 3, u2: 3 }, meta: { labels: { u1: 'Alice', u2: 'Bob' } } } };
    }
    if (key === 'campaign_progress_by_team') {
      campaignKpiOpts = opts;
      // Distinct labels: must not collide with the quota-group team names
      // (Alpha/Beta) or the DC block team (AMER) rendered alongside.
      return _aggregate(
        { tc1: 'Squad One', tc2: 'Squad Two' },
        { tc1: { total: 6, done: 3, progress_pct: 50 }, tc2: { total: 8, done: 2, progress_pct: 25 } },
        { total: 10, done: 5, progress_pct: 50 },
      );
    }
    if (key === 'territory_progress_by_team') {
      territoryKpiOpts = opts;
      return _aggregate(
        { tr1: 'Region One', tr2: 'Region Two' },
        { tr1: { total: 5, done: 4, progress_pct: 80 }, tr2: { total: 10, done: 3, progress_pct: 30 } },
        { total: 15, done: 7, progress_pct: 46.7 },
      );
    }
    return { kpi: null };
  },
  useKpiBatch: (reqs) => {
    kpiBatchReqs = reqs;
    const results = (reqs || []).map((r) => {
      if (r.key === 'dc_cycle_state') {
        return { value: 'IN_PROGRESS', meta: { cycle_status: 'IN_PROGRESS', current_step_name: 'Qualification', validated_steps: 1, total_steps: 5 } };
      }
      return null;
    });
    return { results, resultsLoading: false, resultsError: null };
  },
}));
vi.mock('utils/displayError', () => ({ displayErrorSnackbar: vi.fn() }));

// Team decision cycles list — capture the options (owner_scope=team guard); the
// return is mutable so the visibility test can make it empty.
let cyclesOpts = null;
let decisionCyclesReturn = { cycles: [] };
vi.mock('api/accounts/decisionCycles', () => ({
  useGetDecisionCycles: (opts) => {
    cyclesOpts = opts;
    return decisionCyclesReturn;
  },
  // The real DecisionCyclesBlock imports these status maps from this module.
  CYCLE_DERIVED_STATUS_LABELS: { IN_PROGRESS: 'In Progress', STALLED: 'Stalled', OVERDUE: 'Overdue', NOT_STARTED: 'Not Started' },
  CYCLE_STATUS_COLORS: { IN_PROGRESS: 'info', STALLED: 'warning', OVERDUE: 'error', NOT_STARTED: 'default' },
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

const TEAM_CYCLE = {
  id: 'dc-1', name: 'Globex deal', account: 'acc-1', account_name: 'Globex',
  owner_name: 'Bob Li', owner_email: 'bob@a.test', team: { id: 't9', name: 'AMER' },
};

beforeEach(() => {
  windowsOpts = null;
  teamTableProps = null;
  kpiBatchReqs = null;
  campaignKpiOpts = null;
  territoryKpiOpts = null;
  cyclesOpts = null;
  decisionCyclesReturn = { cycles: [TEAM_CYCLE] };
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

describe('ManagerHome — team progress (two compact aggregates, no per-entity batch)', () => {
  it('fetches BOTH progress dimensions as aggregates at scope=team (campaign + territory)', () => {
    render(<ManagerHome />);
    expect(campaignKpiOpts).toEqual({ scope: 'team' });
    expect(territoryKpiOpts).toEqual({ scope: 'team' });
  });

  it('THE SCALE FIX: neither per-entity progress request survives in the batch', () => {
    render(<ManagerHome />);
    // both per-entity paths are gone entirely — the whole point of the aggregates.
    expect(kpiBatchReqs.filter((r) => r.key === 'campaign_progress')).toEqual([]);
    expect(kpiBatchReqs.filter((r) => r.key === 'territory_coverage')).toEqual([]);
  });

  it('renders the compact campaign aggregate (global + per-team, queue framing, counts-once note)', () => {
    render(<ManagerHome />);
    expect(screen.getByText('Team progress')).toBeInTheDocument();
    expect(screen.getByText('Team campaigns')).toBeInTheDocument();
    // campaign global 5/10 -> "5 accounts to go"; team Squad Two 2/8 -> "6".
    expect(screen.getByText('5 accounts to go')).toBeInTheDocument();
    expect(screen.queryByText('50% done')).not.toBeInTheDocument();
    // campaigns DO flag the shared-campaign global.
    expect(screen.getByText('Shared campaigns count once')).toBeInTheDocument();
  });

  it('renders the compact territory aggregate — NO campaigns/territory cards, NO counts-once note', () => {
    render(<ManagerHome />);
    expect(screen.getByText('Team territories')).toBeInTheDocument();
    // territory global 7/15 -> "8 accounts to go"; Region Two 3/10 -> "7".
    expect(screen.getByText('8 accounts to go')).toBeInTheDocument();
    // the per-entity ProgressBlock cards are gone entirely.
    expect(screen.queryByText('Active campaigns')).not.toBeInTheDocument();
    expect(screen.queryByText('Territory coverage')).not.toBeInTheDocument();
    // (the territory block carries NO counts-once note of its own — proven in
    // isolation in blocks.smoke; on the full page the CAMPAIGN note is present.)
  });

  it('the batch carries only the decision-cycle requests now (1 cycle here)', () => {
    render(<ManagerHome />);
    expect(kpiBatchReqs).toHaveLength(1);
    expect(kpiBatchReqs[0].key).toBe('dc_cycle_state');
  });
});

describe('ManagerHome — team decision cycles (the rep block, team scope + showOwner)', () => {
  it('reads the OPEN team cycles at owner_scope=team (never the tenant-wide bare list)', () => {
    render(<ManagerHome />);
    expect(cyclesOpts).toEqual({ filters: { owner_scope: 'team', outcome__isnull: true } });
  });

  it('runs dc_cycle_state at scope=team, one request per open cycle', () => {
    render(<ManagerHome />);
    expect(kpiBatchReqs.filter((r) => r.key === 'dc_cycle_state')).toEqual([
      { key: 'dc_cycle_state', scope: 'team', params: { cycle_id: 'dc-1' } },
    ]);
  });

  it('renders the block with showOwner (Owner · Team) + the team title', () => {
    render(<ManagerHome />);
    // section heading + the block's card title both read "Team decision cycles".
    expect(screen.getAllByText('Team decision cycles').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Globex deal')).toBeInTheDocument();
    expect(screen.getByText('Bob Li')).toBeInTheDocument();   // showOwner line
    expect(screen.getByText('AMER')).toBeInTheDocument();     // team on the same line
  });

  it('DATA-DRIVEN VISIBILITY: no open team cycle -> no block, no heading', () => {
    decisionCyclesReturn = { cycles: [] };
    render(<ManagerHome />);
    expect(screen.queryByText('Team decision cycles')).not.toBeInTheDocument();
    // and dc_cycle_state is not requested when there are no cycles
    expect(kpiBatchReqs.filter((r) => r.key === 'dc_cycle_state')).toEqual([]);
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
