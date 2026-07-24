// frontend/src/__tests__/views/home/progressBlockLoadingAndRowHeight.test.jsx
//
// Two socle defects of the Home progress block:
//   1. The progress cards must show their skeleton for the WHOLE load (entity
//      lists AND the KPI batch), never flash the empty state before the entities
//      arrive.
//   2. A GoalProgressRow keeps a CONSTANT height across modes: the bar's space
//      stays reserved in the 'empty' state (bar hidden, not removed).
//
// Real shared components render (MainCard, ProgressBlock, GoalProgressRow,
// LinearWithLabel). Only DATA hooks and the framework font loader are mocked.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';

// next/font/google pulls a font chain jsdom can't evaluate (via MainCard's
// Highlighter/theme-config). Stub the loader — a framework module, NOT a shared
// component — so the real MainCard renders.
vi.mock('next/font/google', () => ({
  Public_Sans: () => ({ className: 'mock-public-sans', style: { fontFamily: 'mock' } }),
}));

// ==============================|| DATA-HOOK MOCKS (mutable per phase) ||============================== //

let campaignsReturn = { campaigns: [], campaignsLoading: false };
let territoriesReturn = { territories: [], territoriesCount: 0, territoriesLoading: false };
let kpiBatchReturn = { results: [], resultsLoading: false, resultsError: null };

vi.mock('api/campaigns/campaigns', () => ({ useGetMyCampaigns: () => campaignsReturn }));
vi.mock('api/territories/territories', () => ({ useGetTerritories: () => territoriesReturn }));
vi.mock('api/quotas/quotas', () => ({ useGetMyActiveQuotas: () => ({ quotas: [] }) }));
vi.mock('api/accounts/decisionCycles', () => ({
  useGetDecisionCycles: () => ({ cycles: [] }),
  CYCLE_DERIVED_STATUS_LABELS: {},
  CYCLE_STATUS_COLORS: {},
}));
vi.mock('api/bi/kpi', () => ({ useKpiBatch: () => kpiBatchReturn }));
vi.mock('api/bi/todo', () => ({
  useGetTodoWindows: () => ({
    windows: { overdue: 0, today: 0, next_7_days: 0, next_4_weeks: 0 },
    windowsLoading: false,
    windowsError: null,
  }),
  TODO_WINDOWS: { OVERDUE: 'overdue', TODAY: 'today', NEXT_7_DAYS: 'next_7_days', NEXT_4_WEEKS: 'next_4_weeks' },
}));
// RepActivityTable pulls ReusableTable/TanStack — a heavy home-local block, not
// under test. Stub it so the test isolates the progress block.
vi.mock('sections/home/RepActivityTable', () => ({ default: () => <div data-testid="rep-activity-table" /> }));
vi.mock('utils/displayError', () => ({ displayErrorSnackbar: vi.fn() }));

// ==============================|| IMPORTS (after mocks) ||============================== //

import RepHome from 'views/home/RepHome';
import GoalProgressRow from 'sections/home/GoalProgressRow';

const skeletonCount = (container) => container.querySelectorAll('.MuiSkeleton-root').length;

beforeEach(() => {
  campaignsReturn = { campaigns: [], campaignsLoading: false };
  territoriesReturn = { territories: [], territoriesCount: 0, territoriesLoading: false };
  kpiBatchReturn = { results: [], resultsLoading: false, resultsError: null };
});
afterEach(() => cleanup());

// ==============================|| DEFECT 1 — no empty-state flash on load ||============================== //

describe('RepHome progress cards — skeleton covers the whole load, no empty-state flash', () => {
  it('shows the skeleton (NOT the empty state) while the ENTITY lists are still loading', () => {
    // Entities loading; the KPI batch key is null at this point, so resultsLoading
    // is false — the exact window where the empty state used to flash.
    campaignsReturn = { campaigns: [], campaignsLoading: true };
    territoriesReturn = { territories: [], territoriesCount: 0, territoriesLoading: true };
    kpiBatchReturn = { results: [], resultsLoading: false, resultsError: null };

    const { container } = render(<RepHome />);

    expect(skeletonCount(container)).toBeGreaterThan(0);
    expect(screen.queryByText('No active campaigns.')).not.toBeInTheDocument();
    expect(screen.queryByText('No territories yet.')).not.toBeInTheDocument();
  });

  it('keeps the skeleton while entities are present but the KPI batch is still loading', () => {
    campaignsReturn = { campaigns: [{ id: 'c1', name: 'Q3 Outbound' }], campaignsLoading: false };
    territoriesReturn = { territories: [{ id: 't1', name: 'North' }], territoriesCount: 1, territoriesLoading: false };
    kpiBatchReturn = { results: [], resultsLoading: true, resultsError: null };

    const { container } = render(<RepHome />);

    expect(skeletonCount(container)).toBeGreaterThan(0);
    expect(screen.queryByText('No active campaigns.')).not.toBeInTheDocument();
    expect(screen.queryByText('No territories yet.')).not.toBeInTheDocument();
  });

  it('shows the empty state only once loading has settled AND there is genuinely nothing', () => {
    campaignsReturn = { campaigns: [], campaignsLoading: false };
    territoriesReturn = { territories: [], territoriesCount: 0, territoriesLoading: false };
    kpiBatchReturn = { results: [], resultsLoading: false, resultsError: null };

    const { container } = render(<RepHome />);

    expect(skeletonCount(container)).toBe(0);
    expect(screen.getByText('No active campaigns.')).toBeInTheDocument();
    expect(screen.getByText('No territories yet.')).toBeInTheDocument();
  });
});

// ==============================|| DEFECT 2 — constant row height across modes ||============================== //

describe('GoalProgressRow — constant row height (bar space reserved in the empty state)', () => {
  const normalGradient = { pct: 60, mode: 'remaining', headline: '8 accounts to go' };
  const emptyGradient = { pct: 0, mode: 'empty', headline: 'No accounts assigned' };

  it('RESERVES the bar container in the empty state (present in the DOM, but hidden)', () => {
    const { container } = render(<GoalProgressRow label="Empty" gradient={emptyGradient} />);
    // The reserved bar container is present even in 'empty' mode — THIS is the
    // change under test: the empty row used to render no bar at all and was
    // therefore shorter than a normal row.
    const bar = container.querySelector('.MuiLinearProgress-root');
    expect(bar).not.toBeNull();
    // ...but kept invisible (out of the a11y tree too), so the visual — no
    // "0% of nothing" — is unchanged.
    expect(bar.closest('[style*="visibility"]')).toHaveStyle({ visibility: 'hidden' });
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument(); // hidden → not announced
  });

  it('keeps the bar VISIBLE and accessible for a normal (non-empty) row', () => {
    const { container } = render(<GoalProgressRow label="North" gradient={normalGradient} />);
    const bar = container.querySelector('.MuiLinearProgress-root');
    expect(bar).not.toBeNull();
    expect(bar.closest('[style*="visibility"]')).toHaveStyle({ visibility: 'visible' });
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('the bar container is present in BOTH modes (row height no longer depends on mode)', () => {
    const { container: c1, unmount } = render(<GoalProgressRow label="North" gradient={normalGradient} />);
    const normalHasBar = !!c1.querySelector('.MuiLinearProgress-root');
    unmount();
    const { container: c2 } = render(<GoalProgressRow label="Empty" gradient={emptyGradient} />);
    const emptyHasBar = !!c2.querySelector('.MuiLinearProgress-root');
    expect(normalHasBar).toBe(true);
    expect(emptyHasBar).toBe(true); // was false before the fix (empty rendered no bar)
  });
});
