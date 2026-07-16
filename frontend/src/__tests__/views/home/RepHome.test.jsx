// frontend/src/__tests__/views/home/RepHome.test.jsx
//
// Compile + render check for the RepHome orchestration: it must mount, wire the
// three blocks, and surface the todo value. Data hooks are mocked.

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';

vi.mock('next/font/google', () => ({
  Public_Sans: () => ({ className: 'mock-public-sans', style: { fontFamily: 'mock' } }),
}));
vi.mock('components/MainCard', () => ({
  default: ({ children, title }) => (
    <div data-testid="main-card">{title ? <div>{title}</div> : null}{children}</div>
  ),
}));

vi.mock('api/bi/kpi', () => ({
  useKpiBatch: () => ({ results: [], resultsLoading: false, resultsError: null }),
}));
vi.mock('api/bi/todo', () => ({
  useGetTodoWindows: () => ({
    windows: { overdue: 1, today: 2, next_7_days: 3, next_4_weeks: 5 },
    windowsLoading: false,
    windowsError: null,
  }),
  TODO_WINDOWS: { OVERDUE: 'overdue', TODAY: 'today', NEXT_7_DAYS: 'next_7_days', NEXT_4_WEEKS: 'next_4_weeks' },
}));
// Stub the table (pulls ReusableTable/TanStack) so this test isolates the block wiring.
vi.mock('views/home/components/RepActivityTable', () => ({
  default: () => <div data-testid="rep-activity-table" />,
}));
vi.mock('api/campaigns/campaigns', () => ({ useGetMyCampaigns: () => ({ campaigns: [] }) }));
vi.mock('api/territories/territories', () => ({ useGetTerritories: () => ({ territories: [], territoriesCount: 0 }) }));
vi.mock('api/quotas/quotas', () => ({ useGetMyActiveQuotas: () => ({ quotas: [] }) }));
vi.mock('utils/displayError', () => ({ displayErrorSnackbar: vi.fn() }));

import RepHome from 'views/home/RepHome';

afterEach(() => cleanup());

describe('RepHome', () => {
  it('renders the three blocks with their section headings', () => {
    render(<RepHome />);
    expect(screen.getByText('What I have to do')).toBeInTheDocument();
    expect(screen.getByText('My progress')).toBeInTheDocument();
    expect(screen.getByText('Where I am')).toBeInTheDocument();
    // Block a — window tiles + the activity table.
    expect(screen.getByText('Today')).toBeInTheDocument();
    expect(screen.getByText('Next 4 weeks')).toBeInTheDocument();
    expect(screen.getByTestId('rep-activity-table')).toBeInTheDocument();
    // Empty entity lists -> graceful empty states.
    expect(screen.getByText('No active campaigns.')).toBeInTheDocument();
    expect(screen.getByText('No active quota for this period.')).toBeInTheDocument();
  });
});
