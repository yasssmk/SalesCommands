// frontend/src/__tests__/views/home/RepActivityTable.test.jsx
//
// The table is navigation-only: entity-link cells to the VERIFIED routes, every
// column sortable server-side, and sort/search wired to the data hook. We stub
// ReusableTable to capture its `columns`/props without rendering TanStack.

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

import RepActivityTable from 'sections/home/RepActivityTable';

const colByHeader = (h) => capturedColumns.find((c) => c.header === h);

beforeEach(() => {
  vi.clearAllMocks();
  capturedColumns = null;
  capturedProps = null;
  capturedHookArgs = null;
});
afterEach(() => cleanup());

describe('RepActivityTable', () => {
  it('is navigation-only (no Add/Import/Export) with Context + Name split out', () => {
    render(<RepActivityTable window="today" />);
    expect(screen.getByTestId('reusable-table')).toBeInTheDocument();
    expect(capturedProps.showAddButton).toBe(false);
    // Home is navigation-only: Import disabled (Export stays under the ⋮ menu).
    expect(capturedProps.enableImport).toBe(false);
    expect(capturedColumns.map((c) => c.header)).toEqual([
      'Activity',
      'Type',
      'Account',
      'Context',
      'Name',
      'Due',
    ]);
  });

  it('every column is server-sortable', () => {
    render(<RepActivityTable window="today" />);
    ['Activity', 'Type', 'Account', 'Context', 'Name', 'Due'].forEach((h) => {
      expect(colByHeader(h).enableSorting).not.toBe(false);
    });
  });

  it('maps each column sort to its backend ordering field', () => {
    render(<RepActivityTable window="today" />);
    expect(capturedHookArgs.ordering).toBe('');
    const cases = [
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
    act(() => capturedProps.onSortingChange([{ id: 'name', desc: true }]));
    expect(capturedHookArgs.ordering).toBe('-context_name');
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

  it('Context cell shows the nature (Decision Cycle / Campaign); Name links to the right route', () => {
    render(<RepActivityTable window="today" />);
    // DC: Context = "Decision Cycle", Name links to the dedicated DC route.
    render(colByHeader('Context').cell({ row: { original: { decision_cycle: { id: 'dc1', name: 'Cycle X' } } } }));
    expect(screen.getByText('Decision Cycle')).toBeInTheDocument();
    render(
      colByHeader('Name').cell({
        row: { original: { account: { id: 'acc1' }, decision_cycle: { id: 'dc1', name: 'Cycle X' } } },
      }),
    );
    fireEvent.click(screen.getByText('Cycle X'));
    expect(pushMock).toHaveBeenCalledWith('/accounts/acc1/dc/dc1');

    // Campaign: Context = "Campaign", Name links to /campaigns/{id} (plural).
    render(colByHeader('Context').cell({ row: { original: { campaign: { id: 'camp1', name: 'Q3 Push' } } } }));
    expect(screen.getByText('Campaign')).toBeInTheDocument();
    render(colByHeader('Name').cell({ row: { original: { campaign: { id: 'camp1', name: 'Q3 Push' } } } }));
    fireEvent.click(screen.getByText('Q3 Push'));
    expect(pushMock).toHaveBeenCalledWith('/campaigns/camp1');
  });
});
