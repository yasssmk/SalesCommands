// frontend/src/__tests__/views/home/TeamActivityTable.test.jsx
//
// The manager table reuses the shared TodoActivityTable and prepends a "Person"
// column. We stub ReusableTable to capture its `columns` and exercise the Person
// cell + each entity-link cell to the VERIFIED routes.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';

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

import TeamActivityTable from 'views/home/components/TeamActivityTable';

const colByHeader = (h) => capturedColumns.find((c) => c.header === h);

beforeEach(() => {
  vi.clearAllMocks();
  capturedColumns = null;
  capturedProps = null;
  capturedHookArgs = null;
});
afterEach(() => cleanup());

describe('TeamActivityTable', () => {
  it('is navigation-only with a leading Person column before the base columns', () => {
    render(<TeamActivityTable />);
    expect(screen.getByTestId('reusable-table')).toBeInTheDocument();
    expect(capturedProps.showAddButton).toBe(false);
    expect(capturedColumns.map((c) => c.header)).toEqual([
      'Person',
      'Activity',
      'Type',
      'Account',
      'Decision cycle / Campaign',
      'Due',
    ]);
  });

  it('requests team scope and forwards the team + owner narrowing', () => {
    render(<TeamActivityTable team="team-1" owner="owner-9" />);
    expect(capturedHookArgs).toMatchObject({ scope: 'team', team: 'team-1', owner: 'owner-9' });
  });

  it('Person cell shows the owner full name', () => {
    render(<TeamActivityTable />);
    render(colByHeader('Person').cell({ row: { original: { owner: { id: 'u1', full_name: 'Fabien Roux' } } } }));
    expect(screen.getByText('Fabien Roux')).toBeInTheDocument();
  });

  it('activity cell links to /activities/{id}', () => {
    render(<TeamActivityTable />);
    render(colByHeader('Activity').cell({ row: { original: { id: 'act1', title: 'Call Bob' } } }));
    fireEvent.click(screen.getByText('Call Bob'));
    expect(pushMock).toHaveBeenCalledWith('/activities/act1');
  });

  it('account cell links to /accounts/{id}', () => {
    render(<TeamActivityTable />);
    render(colByHeader('Account').cell({ row: { original: { account: { id: 'acc1', company_name: 'Acme' } } } }));
    fireEvent.click(screen.getByText('Acme'));
    expect(pushMock).toHaveBeenCalledWith('/accounts/acc1');
  });

  it('context cell links a DC to /accounts/{id}/dc/{cycleId} and a campaign to /campaigns/{id}', () => {
    render(<TeamActivityTable />);
    render(
      colByHeader('Decision cycle / Campaign').cell({
        row: { original: { account: { id: 'acc1' }, decision_cycle: { id: 'dc1', name: 'Cycle X' } } },
      }),
    );
    fireEvent.click(screen.getByText('Cycle X'));
    expect(pushMock).toHaveBeenCalledWith('/accounts/acc1/dc/dc1');

    cleanup();
    render(<TeamActivityTable />);
    render(
      colByHeader('Decision cycle / Campaign').cell({
        row: { original: { campaign: { id: 'camp1', name: 'Q3 Push' } } },
      }),
    );
    fireEvent.click(screen.getByText('Q3 Push'));
    expect(pushMock).toHaveBeenCalledWith('/campaigns/camp1');
  });
});
