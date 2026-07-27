// frontend/src/__tests__/views/objectives/objectivesList.test.jsx
//
// The My Objectives page renders each quota with its metric, period-state chip,
// and progress bar whose RATIO comes from the payload (progress_ratio) — an
// over-achieved quota shows the real % + star. Real renders; only the data hook
// and the campaigns hook are mocked.

import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, within, cleanup } from '@testing-library/react';

// next/font pulls a chain jsdom can't evaluate (via MainCard); stub the loader.
vi.mock('next/font/google', () => ({
  Public_Sans: () => ({ className: 'mock-public-sans', style: { fontFamily: 'mock' } }),
}));

// The page imports ObjectiveModal -> ObjectiveForm -> the third-party MUI date
// picker, whose ESM entry does not resolve under vitest. Stub the lib (not our
// own components); the form isn't rendered here (modal closed) anyway.
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
vi.mock('api/campaigns/campaigns', () => ({ useGetCampaigns: () => ({ campaigns: [] }) }));

import ObjectivesListPage from 'views/objectives/list';

afterEach(cleanup);

const overQuota = {
  id: '11111111-1111-1111-1111-111111111111',
  metric: 'REVENUE_WON',
  target_value: '100.00',
  current_value: 130,
  progress_ratio: 1.3,
  period_start: '2026-01-01',
  period_end: '2026-12-31',
  state: 'CURRENT',
};
const normalQuota = {
  id: '22222222-2222-2222-2222-222222222222',
  metric: 'MEETINGS',
  target_value: '10.00',
  current_value: 3,
  progress_ratio: 0.3,
  period_start: '2020-01-01',
  period_end: '2020-12-31',
  state: 'PAST',
};

describe('ObjectivesListPage', () => {
  it('renders each objective with metric, period-state chip and payload-driven ratio', () => {
    mockUseGetObjectives.mockReturnValue({ objectives: [overQuota, normalQuota], objectivesLoading: false });
    render(<ObjectivesListPage />);

    // metric labels (readable)
    expect(screen.getByText('Revenue won')).toBeTruthy();
    expect(screen.getByText('Meetings')).toBeTruthy();
    // period-state chips
    expect(screen.getByText('Current')).toBeTruthy();
    expect(screen.getByText('Past')).toBeTruthy();

    // over-achieved quota: real % from progress_ratio (1.3 -> 130%) + star
    expect(screen.getByText('130%')).toBeTruthy();
    expect(screen.getByLabelText('over-achieved')).toBeTruthy();
    // normal quota: its own %
    expect(screen.getByText('30%')).toBeTruthy();
  });

  it('shows an empty state when the user has no objectives', () => {
    mockUseGetObjectives.mockReturnValue({ objectives: [], objectivesLoading: false });
    render(<ObjectivesListPage />);
    expect(screen.getByText(/No objectives yet/i)).toBeTruthy();
  });
});
