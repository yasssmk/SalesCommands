// frontend/src/__tests__/views/home/TeamActivityTable.test.jsx
//
// The manager table reuses TodoActivityTable and prepends Person + Team columns.
// We stub ReusableTable to capture its `columns`/props and exercise the cells,
// sortability, and the sort -> ordering wiring.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup, act } from '@testing-library/react';

let capturedColumns = null;
let capturedProps = null;
vi.mock('components/table/Table', () => ({
  default: (props) => {
    capturedColumns = props.columns;
    capturedProps = props;
    return <div data-testid="reusable-table" />;
  },
}));

const pushMock = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: pushMock }) }));
vi.mock('hooks/useLocalStorage', () => ({ default: () => [10, vi.fn()] }));

let capturedHookArgs = null;
vi.mock('api/bi/todo', () => ({
  useGetTeamTodoActivities: (args) => {
    capturedHookArgs = args;
    return {
      activities: [],
      activitiesCount: 0,
      activitiesLoading: false,
      activitiesError: null,
      swrKey: null,
    };
  },
}));

import TeamActivityTable from 'sections/home/TeamActivityTable';

const colByHeader = (h) => capturedColumns.find((c) => c.header === h);

beforeEach(() => {
  vi.clearAllMocks();
  capturedColumns = null;
  capturedProps = null;
  capturedHookArgs = null;
});
afterEach(() => cleanup());

describe('TeamActivityTable', () => {
  it('prepends Owner + Team before the base columns (Context/Name split), no data actions', () => {
    render(<TeamActivityTable />);
    expect(screen.getByTestId('reusable-table')).toBeInTheDocument();
    expect(capturedProps.showAddButton).toBe(false);
    // Home is navigation-only: Import disabled (Export stays under the ⋮ menu).
    expect(capturedProps.enableImport).toBe(false);
    expect(capturedColumns.map((c) => c.header)).toEqual([
      'Owner',
      'Team',
      'Activity',
      'Type',
      'Account',
      'Context',
      'Name',
      'Due',
    ]);
  });

  it('every column is server-sortable (Team now maps to owner__team__name)', () => {
    render(<TeamActivityTable />);
    ['Owner', 'Team', 'Activity', 'Type', 'Account', 'Context', 'Name', 'Due'].forEach((h) => {
      expect(colByHeader(h).enableSorting).not.toBe(false);
    });
  });

  it('requests team scope and forwards team + owner narrowing', () => {
    render(<TeamActivityTable team="team-1" owner="owner-9" />);
    expect(capturedHookArgs).toMatchObject({ scope: 'team', team: 'team-1', owner: 'owner-9' });
  });

  it('maps each column sort to its backend ordering field (incl. Person/Team)', () => {
    render(<TeamActivityTable />);
    const cases = [
      ['owner', 'owner__last_name'],
      ['team', 'owner__team__name'],
      ['title', 'title'],
      ['activity_type', 'activity_type'],
      ['account', 'account__company_name'],
      ['context', 'context_kind'],
      ['name', 'context_name'],
      ['effective_date', 'effective_date'],
    ];
    cases.forEach(([id, field]) => {
      act(() => capturedProps.onSortingChange([{ id, desc: false }]));
      expect(capturedHookArgs.ordering).toBe(field);
    });
    act(() => capturedProps.onSortingChange([{ id: 'team', desc: true }]));
    expect(capturedHookArgs.ordering).toBe('-owner__team__name');
  });

  it('forwards the search term to the hook', () => {
    render(<TeamActivityTable />);
    act(() => capturedProps.onSearchChange('acme'));
    expect(capturedHookArgs.search).toBe('acme');
  });

  it('Owner shows owner name; Team shows team name; Context/Name split with links', () => {
    render(<TeamActivityTable />);
    render(colByHeader('Owner').cell({ row: { original: { owner: { id: 'u1', full_name: 'Fabien Roux' } } } }));
    expect(screen.getByText('Fabien Roux')).toBeInTheDocument();
    render(colByHeader('Team').cell({ row: { original: { team: { id: 't1', name: 'France' } } } }));
    expect(screen.getByText('France')).toBeInTheDocument();
    render(colByHeader('Context').cell({ row: { original: { campaign: { id: 'camp1', name: 'Q3 Push' } } } }));
    expect(screen.getByText('Campaign')).toBeInTheDocument();
    render(colByHeader('Name').cell({ row: { original: { campaign: { id: 'camp1', name: 'Q3 Push' } } } }));
    fireEvent.click(screen.getByText('Q3 Push'));
    expect(pushMock).toHaveBeenCalledWith('/campaigns/camp1');
  });

  it('activity/account cells link to the verified routes', () => {
    render(<TeamActivityTable />);
    render(colByHeader('Activity').cell({ row: { original: { id: 'act1', title: 'Call Bob' } } }));
    fireEvent.click(screen.getByText('Call Bob'));
    expect(pushMock).toHaveBeenCalledWith('/activities/act1');

    render(colByHeader('Account').cell({ row: { original: { account: { id: 'acc1', company_name: 'Acme' } } } }));
    fireEvent.click(screen.getByText('Acme'));
    expect(pushMock).toHaveBeenCalledWith('/accounts/acc1');
  });
});
