// frontend/src/__tests__/views/home/blocks.smoke.test.jsx
//
// Render smoke for the Rep Home blocks: they must compile and mount with real
// KPI-shaped data, and apply the goal-gradient framing ("only X left").

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';

// MainCard pulls a next/font chain (via Highlighter/theme-config) that jsdom
// can't evaluate; stub it, rendering its title as text and forwarding onClick
// so titles stay assertable and clickable tiles work.
vi.mock('next/font/google', () => ({
  Public_Sans: () => ({ className: 'mock-public-sans', style: { fontFamily: 'mock' } }),
}));
vi.mock('components/MainCard', () => ({
  default: ({ children, title, onClick }) => (
    <div data-testid="main-card" onClick={onClick}>
      {title ? <div>{title}</div> : null}
      {children}
    </div>
  ),
}));

import TodoBlock from 'views/home/components/TodoBlock';
import ProgressBlock from 'views/home/components/ProgressBlock';
import QuotaBlock from 'views/home/components/QuotaBlock';

afterEach(() => cleanup());

describe('TodoBlock', () => {
  const windows = { overdue: 1, today: 2, next_7_days: 3, next_4_weeks: 5 };

  it('renders the 4 window tiles', () => {
    render(<TodoBlock windows={windows} activeFilter="today" onSelect={vi.fn()} loading={false} />);
    expect(screen.getByText('Overdue')).toBeInTheDocument();
    expect(screen.getByText('Today')).toBeInTheDocument();
    expect(screen.getByText('Next 7 days')).toBeInTheDocument();
    expect(screen.getByText('Next 4 weeks')).toBeInTheDocument();
  });

  it('frames zero-today as all clear', () => {
    render(<TodoBlock windows={{ overdue: 0, today: 0, next_7_days: 0, next_4_weeks: 0 }} activeFilter="today" onSelect={vi.fn()} loading={false} />);
    expect(screen.getByText('all clear for today')).toBeInTheDocument();
    expect(screen.getByText('nothing overdue')).toBeInTheDocument();
  });

  it('clicking a tile selects that window', () => {
    const onSelect = vi.fn();
    render(<TodoBlock windows={windows} activeFilter="today" onSelect={onSelect} loading={false} />);
    fireEvent.click(screen.getByText('Overdue'));
    expect(onSelect).toHaveBeenCalledWith('overdue');
  });
});

describe('ProgressBlock', () => {
  it('renders active campaigns and ranks territories, no hidden overflow', () => {
    const campaigns = [{ entity: { id: 'c1', name: 'Q3 Outbound' }, result: { value: 40 } }];
    const territories = [
      { entity: { id: 't1', name: 'North' }, result: { value: 90 } },
      { entity: { id: 't2', name: 'South' }, result: { value: 20 } },
    ];
    render(
      <ProgressBlock campaigns={campaigns} territories={territories} territoriesTotal={2} loading={false} />,
    );
    expect(screen.getByText('Active campaigns')).toBeInTheDocument();
    expect(screen.getByText('Q3 Outbound')).toBeInTheDocument();
    // Lowest-coverage territory (South, 20%) is surfaced.
    expect(screen.getByText('South')).toBeInTheDocument();
  });

  it('shows an empty state when there are no active campaigns', () => {
    render(<ProgressBlock campaigns={[]} territories={[]} territoriesTotal={0} loading={false} />);
    expect(screen.getByText('No active campaigns.')).toBeInTheDocument();
  });
});

describe('QuotaBlock', () => {
  it('renders quota attainment with the remaining framing near the finish', () => {
    const quotas = [
      { entity: { id: 1, name: 'Meetings Q3' }, result: { value: 80, meta: { current: 8, target: 10, target_type: 'meetings' } } },
    ];
    render(<QuotaBlock quotas={quotas} loading={false} />);
    expect(screen.getByText('Meetings Q3')).toBeInTheDocument();
    expect(screen.getByText('Only 2 left')).toBeInTheDocument();
    expect(screen.getByText('8 of 10')).toBeInTheDocument();
  });

  it('renders an empty state with no active quota', () => {
    render(<QuotaBlock quotas={[]} loading={false} />);
    expect(screen.getByText('No active quota for this period.')).toBeInTheDocument();
  });
});
