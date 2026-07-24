// frontend/src/__tests__/views/home/progressBlockNavigation.test.jsx
//
// Rep progress block navigation:
//   - a PERMANENT "See all" footer on both cards (even at 0 entity), to the
//     ACTIVE-filtered campaigns list / the territories list;
//   - each row's name links to its workspace (/campaigns/{id}, /territories/{id});
//   - GoalProgressRow renders a link ONLY when given an href.
//
// Real render: ProgressBlock, MainCard, GoalProgressRow, LinearWithLabel and the
// links all render. Only the framework font loader is stubbed.

import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';

vi.mock('next/font/google', () => ({
  Public_Sans: () => ({ className: 'mock-public-sans', style: { fontFamily: 'mock' } }),
}));

import ProgressBlock from 'sections/home/ProgressBlock';
import GoalProgressRow from 'sections/home/GoalProgressRow';

const camp = (id, name) => ({
  entity: { id, name, planned_end_date: '2026-06-30' },
  result: { value: 50, meta: { accounts_completed: 1, accounts_total: 10 } },
});
const terr = (id, name) => ({
  entity: { id, name },
  result: { value: 50, meta: { numerator: 5, denominator: 10 } },
});

afterEach(cleanup);

// ==============================|| PERMANENT "See all" ON BOTH CARDS ||============================== //

describe('ProgressBlock — permanent "See all" footer on both cards', () => {
  it('present on both cards at 0 entity, with the count dropped (never "(0)")', () => {
    const { container } = render(<ProgressBlock campaigns={[]} territories={[]} loading={false} />);
    const campLink = container.querySelector('a[href="/campaigns?status=ACTIVE"]');
    const terrLink = container.querySelector('a[href="/territories"]');
    expect(campLink).not.toBeNull();
    expect(terrLink).not.toBeNull();
    expect(campLink).toHaveTextContent('See all');
    expect(campLink).not.toHaveTextContent('(0)');
    expect(terrLink).not.toHaveTextContent('(0)');
  });

  it('present with the real total even when nothing is hidden (hiddenCount = 0)', () => {
    const { container } = render(
      <ProgressBlock
        campaigns={[camp('c1', 'A'), camp('c2', 'B')]}
        campaignsTotal={2}
        territories={[terr('t1', 'North')]}
        territoriesTotal={1}
        loading={false}
      />,
    );
    expect(container.querySelector('a[href="/campaigns?status=ACTIVE"]')).toHaveTextContent('See all (2)');
    expect(container.querySelector('a[href="/territories"]')).toHaveTextContent('See all (1)');
  });
});

// ==============================|| CLICKABLE ROW NAMES ||============================== //

describe('ProgressBlock — row names link to their workspace', () => {
  it('campaign name → /campaigns/{id}, territory name → /territories/{id} (real ids)', () => {
    const { container } = render(
      <ProgressBlock
        campaigns={[camp('c1', 'Q3 Outbound')]}
        campaignsTotal={1}
        territories={[terr('t9', 'North')]}
        territoriesTotal={1}
        loading={false}
      />,
    );
    expect(container.querySelector('a[href="/campaigns/c1"]')).toHaveTextContent('Q3 Outbound');
    expect(container.querySelector('a[href="/territories/t9"]')).toHaveTextContent('North');
  });
});

// ==============================|| GoalProgressRow href IS OPTIONAL ||============================== //

describe('GoalProgressRow — href is optional', () => {
  const gradient = { pct: 50, mode: 'remaining', headline: '8 to go' };

  it('renders the label as a link when href is given', () => {
    const { container } = render(<GoalProgressRow label="Deal" gradient={gradient} href="/campaigns/c1" />);
    expect(container.querySelector('a[href="/campaigns/c1"]')).toHaveTextContent('Deal');
  });

  it('renders NO link on the label without href (strictly unchanged)', () => {
    const { container } = render(<GoalProgressRow label="Plain" gradient={gradient} />);
    expect(container.querySelector('a')).toBeNull();
    expect(screen.getByText('Plain').closest('a')).toBeNull();
  });
});
