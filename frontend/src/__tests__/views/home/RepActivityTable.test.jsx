// frontend/src/__tests__/views/home/RepActivityTable.test.jsx
//
// The table is navigation-only: it defines entity-link cells to the VERIFIED
// routes, makes only the backend-sortable columns sortable, and wires
// sort/search to the data hook (server-side). We stub ReusableTable to capture
// its `columns`/props without rendering the full TanStack table.

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
  useGetTodoActivities: (args) => {
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

import RepActivityTable from 'views/home/components/RepActivityTable';

const colByHeader = (h) => capturedColumns.find((c) => c.header === h);

beforeEach(() => {
  vi.clearAllMocks();
  capturedColumns = null;
  capturedProps = null;
  capturedHookArgs = null;
});
afterEach(() => cleanup());

describe('RepActivityTable', () => {
  it('is navigation-only (no Add button) with the expected columns', () => {
    render(<RepActivityTable window="today" />);
    expect(screen.getByTestId('reusable-table')).toBeInTheDocument();
    expect(capturedProps.showAddButton).toBe(false);
    expect(capturedColumns.map((c) => c.header)).toEqual([
      'Activity',
      'Type',
      'Account',
      'Decision cycle / Campaign',
      'Due',
    ]);
  });

  it('makes only the backend-sortable columns sortable', () => {
    render(<RepActivityTable window="today" />);
    expect(colByHeader('Account').enableSorting).not.toBe(false);
    expect(colByHeader('Due').enableSorting).not.toBe(false);
    expect(colByHeader('Activity').enableSorting).toBe(false);
    expect(colByHeader('Type').enableSorting).toBe(false);
    expect(colByHeader('Decision cycle / Campaign').enableSorting).toBe(false);
  });

  it('maps a column sort to the backend ordering field passed to the hook', () => {
    render(<RepActivityTable window="today" />);
    expect(capturedHookArgs.ordering).toBe('');
    act(() => capturedProps.onSortingChange([{ id: 'account', desc: false }]));
    expect(capturedHookArgs.ordering).toBe('account__company_name');
    act(() => capturedProps.onSortingChange([{ id: 'effective_date', desc: true }]));
    expect(capturedHookArgs.ordering).toBe('-effective_date');
  });

  it('forwards the search term to the hook', () => {
    render(<RepActivityTable window="today" />);
    act(() => capturedProps.onSearchChange('acme'));
    expect(capturedHookArgs.search).toBe('acme');
  });

  it('activity cell links to /activities/{id}', () => {
    render(<RepActivityTable window="today" />);
    render(colByHeader('Activity').cell({ row: { original: { id: 'act1', title: 'Call Bob' } } }));
    fireEvent.click(screen.getByText('Call Bob'));
    expect(pushMock).toHaveBeenCalledWith('/activities/act1');
  });

  it('account cell links to /accounts/{id}', () => {
    render(<RepActivityTable window="today" />);
    render(colByHeader('Account').cell({ row: { original: { account: { id: 'acc1', company_name: 'Acme' } } } }));
    fireEvent.click(screen.getByText('Acme'));
    expect(pushMock).toHaveBeenCalledWith('/accounts/acc1');
  });

  it('context cell links a DC to the dedicated /accounts/{id}/dc/{cycleId} route', () => {
    render(<RepActivityTable window="today" />);
    render(
      colByHeader('Decision cycle / Campaign').cell({
        row: { original: { account: { id: 'acc1' }, decision_cycle: { id: 'dc1', name: 'Cycle X' } } },
      }),
    );
    fireEvent.click(screen.getByText('Cycle X'));
    expect(pushMock).toHaveBeenCalledWith('/accounts/acc1/dc/dc1');
  });

  it('context cell links a campaign to /campaigns/{id} (plural)', () => {
    render(<RepActivityTable window="today" />);
    render(
      colByHeader('Decision cycle / Campaign').cell({
        row: { original: { campaign: { id: 'camp1', name: 'Q3 Push' } } },
      }),
    );
    fireEvent.click(screen.getByText('Q3 Push'));
    expect(pushMock).toHaveBeenCalledWith('/campaigns/camp1');
  });
});
