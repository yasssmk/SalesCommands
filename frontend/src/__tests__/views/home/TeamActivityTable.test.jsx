// frontend/src/__tests__/views/home/TeamActivityTable.test.jsx
//
// The manager table reuses the shared TodoActivityTable and prepends Person +
// Team columns. We stub ReusableTable to capture its `columns`/props and exercise
// the cells, the sortability config, and the sort -> ordering wiring.

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
  it('prepends Person + Team columns before the base columns', () => {
    render(<TeamActivityTable />);
    expect(screen.getByTestId('reusable-table')).toBeInTheDocument();
    expect(capturedProps.showAddButton).toBe(false);
    expect(capturedColumns.map((c) => c.header)).toEqual([
      'Person',
      'Team',
      'Activity',
      'Type',
      'Account',
      'Decision cycle / Campaign',
      'Due',
    ]);
  });

  it('makes Person sortable (owner__last_name) but Team non-sortable (no backend field)', () => {
    render(<TeamActivityTable />);
    expect(colByHeader('Person').enableSorting).not.toBe(false); // sortable (default)
    expect(colByHeader('Team').enableSorting).toBe(false);
    // Account + Due are sortable too; Activity/Type/context are not.
    expect(colByHeader('Account').enableSorting).not.toBe(false);
    expect(colByHeader('Due').enableSorting).not.toBe(false);
    expect(colByHeader('Activity').enableSorting).toBe(false);
  });

  it('requests team scope and forwards team + owner narrowing', () => {
    render(<TeamActivityTable team="team-1" owner="owner-9" />);
    expect(capturedHookArgs).toMatchObject({ scope: 'team', team: 'team-1', owner: 'owner-9' });
  });

  it('maps a column sort to the backend ordering field passed to the hook', () => {
    render(<TeamActivityTable />);
    expect(capturedHookArgs.ordering).toBe('');
    // Sort by Person descending -> -owner__last_name.
    act(() => capturedProps.onSortingChange([{ id: 'owner', desc: true }]));
    expect(capturedHookArgs.ordering).toBe('-owner__last_name');
    // Sort by Account ascending -> account__company_name.
    act(() => capturedProps.onSortingChange([{ id: 'account', desc: false }]));
    expect(capturedHookArgs.ordering).toBe('account__company_name');
  });

  it('forwards the search term to the hook', () => {
    render(<TeamActivityTable />);
    act(() => capturedProps.onSearchChange('acme'));
    expect(capturedHookArgs.search).toBe('acme');
  });

  it('Person cell shows the owner full name; Team cell shows the team name', () => {
    render(<TeamActivityTable />);
    render(colByHeader('Person').cell({ row: { original: { owner: { id: 'u1', full_name: 'Fabien Roux' } } } }));
    expect(screen.getByText('Fabien Roux')).toBeInTheDocument();
    render(colByHeader('Team').cell({ row: { original: { team: { id: 't1', name: 'France' } } } }));
    expect(screen.getByText('France')).toBeInTheDocument();
  });

  it('activity/account/context cells link to the verified routes', () => {
    render(<TeamActivityTable />);
    render(colByHeader('Activity').cell({ row: { original: { id: 'act1', title: 'Call Bob' } } }));
    fireEvent.click(screen.getByText('Call Bob'));
    expect(pushMock).toHaveBeenCalledWith('/activities/act1');

    render(colByHeader('Account').cell({ row: { original: { account: { id: 'acc1', company_name: 'Acme' } } } }));
    fireEvent.click(screen.getByText('Acme'));
    expect(pushMock).toHaveBeenCalledWith('/accounts/acc1');

    render(
      colByHeader('Decision cycle / Campaign').cell({
        row: { original: { account: { id: 'acc1' }, decision_cycle: { id: 'dc1', name: 'Cycle X' } } },
      }),
    );
    fireEvent.click(screen.getByText('Cycle X'));
    expect(pushMock).toHaveBeenCalledWith('/accounts/acc1/dc/dc1');
  });
});
