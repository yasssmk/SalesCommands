// frontend/src/__tests__/views/objectives/objectivesList.test.jsx
//
// The My Objectives page: payload-driven bar/ratio, the Active/All toggle
// (Active = CURRENT only), and the "focus now" order (soonest end date first,
// then lowest attainment). Real renders; only data + third-party lib are mocked.

import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';

vi.mock('next/font/google', () => ({
  Public_Sans: () => ({ className: 'mock-public-sans', style: { fontFamily: 'mock' } }),
}));
// The page imports ObjectiveModal -> ObjectiveForm -> the third-party MUI date
// picker, whose ESM entry does not resolve under vitest. Stub the lib only.
vi.mock('@mui/x-date-pickers/DatePicker', () => ({ DatePicker: () => null }));
vi.mock('@mui/x-date-pickers/LocalizationProvider', () => ({ LocalizationProvider: ({ children }) => children }));
vi.mock('@mui/x-date-pickers/AdapterDayjs', () => ({ AdapterDayjs: {} }));

const mockUseGetObjectives = vi.fn();
vi.mock('api/objectives/objectives', () => ({
  useGetObjectives: () => mockUseGetObjectives(),
  createObjective: vi.fn(),
  updateObjective: vi.fn(),
  deleteObjective: vi.fn(),
}));

import ObjectivesListPage from 'views/objectives/list';

afterEach(cleanup);

const q = (id, metric, state, period_end, progress_ratio) => ({
  id,
  metric,
  state,
  period_end,
  period_start: '2020-01-01',
  target_value: '10',
  current_value: 3,
  progress_ratio,
});

// c2 ends before c1; p1 is PAST.
const c1 = q('1', 'REVENUE_WON', 'CURRENT', '2026-08-31', 1.3);
const c2 = q('2', 'MEETINGS', 'CURRENT', '2026-08-15', 0.3);
const p1 = q('3', 'LEADS', 'PAST', '2020-12-31', 0.5);

const precedes = (a, b) =>
  Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
const title = (name) => screen.getByText(name);

describe('ObjectivesListPage — payload, toggle, order', () => {
  it('renders the over-achieved bar/ratio from the payload', () => {
    mockUseGetObjectives.mockReturnValue({ objectives: [c1, c2], objectivesLoading: false });
    render(<ObjectivesListPage />);
    expect(screen.getByText('130%')).toBeTruthy(); // c1 ratio 1.3, non-clamped
    expect(screen.getByLabelText('over-achieved')).toBeTruthy();
    expect(screen.getByText('30%')).toBeTruthy(); // c2 ratio 0.3
  });

  it('Active (default) shows only CURRENT objectives; All shows everything', () => {
    mockUseGetObjectives.mockReturnValue({ objectives: [c1, c2, p1], objectivesLoading: false });
    render(<ObjectivesListPage />);

    // default = Active -> the PAST one is hidden
    expect(screen.getByText('Revenue won')).toBeTruthy();
    expect(screen.getByText('Meetings')).toBeTruthy();
    expect(screen.queryByText('Leads')).toBeNull();

    // switch to All -> the PAST one appears
    fireEvent.click(screen.getByRole('button', { name: 'All' }));
    expect(screen.getByText('Leads')).toBeTruthy();
  });

  it('orders by soonest end date first (then lowest attainment)', () => {
    mockUseGetObjectives.mockReturnValue({ objectives: [c1, c2], objectivesLoading: false });
    render(<ObjectivesListPage />);
    // c2 (end 2026-08-15) must come before c1 (end 2026-08-31)
    expect(precedes(title('Meetings'), title('Revenue won'))).toBe(true);
  });

  it('breaks an end-date tie by lowest attainment first', () => {
    const t1 = q('4', 'DECISION_CYCLES', 'CURRENT', '2026-09-30', 0.8);
    const t2 = q('5', 'NEW_LOGOS', 'CURRENT', '2026-09-30', 0.2);
    mockUseGetObjectives.mockReturnValue({ objectives: [t1, t2], objectivesLoading: false });
    render(<ObjectivesListPage />);
    // same end date -> lower ratio (New logos 0.2) before higher (Decision cycles 0.8)
    expect(precedes(title('New logos'), title('Decision cycles'))).toBe(true);
  });
});
