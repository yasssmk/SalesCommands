// frontend/src/__tests__/views/home/progressBlockFraming.test.jsx
//
// Rep progress block framing (commit 3): both cards rank + cap to PROGRESS_TOP_N
// and reserve the same fixed-height rows zone.
//   - Campaigns: soonest planned_end_date first, then lowest progress on a tie.
//   - Cap of 5 shared by both cards; hidden count kept per card.
//   - The rows zone reserves a constant height across populated / empty / loading.
//
// Real render: ProgressBlock, MainCard and GoalProgressRow all render. Only the
// framework font loader is stubbed (no shared-component mock).

import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, within, cleanup } from '@testing-library/react';

// next/font pulls a chain jsdom can't evaluate (via MainCard); stub the loader.
vi.mock('next/font/google', () => ({
  Public_Sans: () => ({ className: 'mock-public-sans', style: { fontFamily: 'mock' } }),
}));

import ProgressBlock, { rank } from 'sections/home/ProgressBlock';

const RESERVED = '320px'; // PROGRESS_TOP_N (5) × ROW_HEIGHT (64)

const camp = (id, name, planned_end_date, value) => ({
  entity: { id, name, planned_end_date },
  result: { value, meta: { accounts_completed: 1, accounts_total: 10 } },
});
const terr = (id, name, value) => ({
  entity: { id, name },
  result: { value, meta: { numerator: value / 10, denominator: 10 } },
});

const precedes = (a, b) =>
  Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);

afterEach(cleanup);

// ==============================|| CAMPAIGN ORDERING (discriminant on DOM order) ||============================== //

describe('ProgressBlock — campaigns ordered by soonest deadline, then lowest progress', () => {
  it('orders by planned_end_date ascending (soonest first)', () => {
    render(
      <ProgressBlock
        campaigns={[camp('a', 'Later', '2026-12-31', 50), camp('b', 'Sooner', '2026-06-30', 50)]}
        territories={[]}
        loading={false}
      />,
    );
    expect(precedes(screen.getByText('Sooner'), screen.getByText('Later'))).toBe(true);
  });

  it('breaks a date tie by LOWER progress first (same KPI source as the gradient)', () => {
    render(
      <ProgressBlock
        campaigns={[camp('c', 'HighProg', '2026-06-30', 80), camp('d', 'LowProg', '2026-06-30', 20)]}
        territories={[]}
        loading={false}
      />,
    );
    expect(precedes(screen.getByText('LowProg'), screen.getByText('HighProg'))).toBe(true);
  });
});

// ==============================|| CAP OF 5 ON BOTH CARDS ||============================== //

describe('ProgressBlock — cap of 5 shared by both cards, hidden count kept', () => {
  it('the rank helper caps to 5 and reports the hidden remainder', () => {
    const seven = Array.from({ length: 7 }, (_, i) => ({ entity: { id: String(i) } }));
    const { top, hiddenCount } = rank(seven, 7);
    expect(top).toHaveLength(5);
    expect(hiddenCount).toBe(2);
  });

  it('renders at most 5 campaign rows for 7 campaigns', () => {
    const seven = Array.from({ length: 7 }, (_, i) => camp(`c${i}`, `Camp ${i}`, '2026-06-30', i * 10));
    render(<ProgressBlock campaigns={seven} campaignsTotal={7} territories={[]} loading={false} />);
    const zone = screen.getByTestId('progress-rows-zone-campaigns');
    expect(within(zone).getAllByRole('progressbar')).toHaveLength(5);
  });

  it('renders at most 5 territory rows for 7 territories and a "See all (7)" affordance', () => {
    const seven = Array.from({ length: 7 }, (_, i) => terr(`t${i}`, `Terr ${i}`, i * 10));
    render(<ProgressBlock campaigns={[]} territories={seven} territoriesTotal={7} loading={false} />);
    const zone = screen.getByTestId('progress-rows-zone-territories');
    expect(within(zone).getAllByRole('progressbar')).toHaveLength(5);
    expect(screen.getByText('See all (7)')).toBeInTheDocument();
  });
});

// ==============================|| FIXED-HEIGHT ROWS ZONE ||============================== //

describe('ProgressBlock — the rows zone reserves the same height in every state', () => {
  const zones = () => [
    screen.getByTestId('progress-rows-zone-campaigns'),
    screen.getByTestId('progress-rows-zone-territories'),
  ];

  it('5 rows → reserved height on both zones', () => {
    const five = Array.from({ length: 5 }, (_, i) => camp(`c${i}`, `C${i}`, '2026-06-30', i * 10));
    render(<ProgressBlock campaigns={five} campaignsTotal={5} territories={[]} loading={false} />);
    zones().forEach((z) => expect(z).toHaveStyle({ minHeight: RESERVED }));
  });

  it('3 rows → the SAME reserved height (no jump vs 5 rows)', () => {
    const three = Array.from({ length: 3 }, (_, i) => camp(`c${i}`, `C${i}`, '2026-06-30', i * 10));
    render(<ProgressBlock campaigns={three} campaignsTotal={3} territories={[]} loading={false} />);
    zones().forEach((z) => expect(z).toHaveStyle({ minHeight: RESERVED }));
  });

  it('0 rows (empty state) → the SAME reserved height', () => {
    render(<ProgressBlock campaigns={[]} territories={[]} loading={false} />);
    zones().forEach((z) => expect(z).toHaveStyle({ minHeight: RESERVED }));
    expect(screen.getByText('No active campaigns.')).toBeInTheDocument();
  });

  it('loading (skeleton) → the SAME reserved height', () => {
    render(<ProgressBlock campaigns={[]} territories={[]} loading />);
    zones().forEach((z) => expect(z).toHaveStyle({ minHeight: RESERVED }));
  });
});
