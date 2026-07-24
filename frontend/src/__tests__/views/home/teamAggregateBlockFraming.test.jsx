// frontend/src/__tests__/views/home/teamAggregateBlockFraming.test.jsx
//
// Manager progress blocks (cap, fixed height, "See all", no row links):
//   - capped to PROGRESS_TOP_N rows with the global "All teams" row counting
//     within it (7 teams → global + 4 teams shown, 3 hidden);
//   - the rows zone reserves the SAME fixed height as the rep across states;
//   - a permanent "See all" footer on both cards (even at 0 team), same
//     destinations as the rep;
//   - team rows are never links (a row is an aggregated team, not an object).
//
// Real render: TeamCampaignsBlock / TeamTerritoriesBlock, TeamAggregateBlock,
// MainCard, GoalProgressRow all render. Only the framework font loader is stubbed.

import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, within, cleanup } from '@testing-library/react';

vi.mock('next/font/google', () => ({
  Public_Sans: () => ({ className: 'mock-public-sans', style: { fontFamily: 'mock' } }),
}));

import TeamCampaignsBlock from 'sections/home/TeamCampaignsBlock';
import TeamTerritoriesBlock from 'sections/home/TeamTerritoriesBlock';

const RESERVED = '320px'; // PROGRESS_TOP_N (5) × ROW_HEIGHT (64) — shared with the rep

// n teams, ascending progress (so the lowest-progress teams sort first).
function teams(n) {
  const labels = {};
  const per_group = {};
  for (let i = 0; i < n; i += 1) {
    labels[`t${i}`] = `Team ${i}`;
    per_group[`t${i}`] = { total: 10, done: i, progress_pct: i * 10 };
  }
  return { meta: { dimension: 'team', labels, per_group, global: { total: 10 * n, done: n, progress_pct: 10 } } };
}
const EMPTY_RESULT = { meta: { labels: {}, per_group: {}, global: null } };

const campaignsZone = () => screen.getByTestId('team-progress-zone-campaigns');
const territoriesZone = () => screen.getByTestId('team-progress-zone-territories');

afterEach(cleanup);

// ==============================|| CAP — global counts within the 5 ||============================== //

describe('TeamAggregateBlock — capped to 5 rows including the global "All teams" row', () => {
  it('7 teams → 5 rows (All teams + 4 lowest-progress teams); the other 3 are hidden', () => {
    render(<TeamCampaignsBlock result={teams(7)} loading={false} />);
    const zone = campaignsZone();
    // 5 rows total: the global row + 4 team rows (each row carries one bar).
    expect(within(zone).getAllByRole('progressbar')).toHaveLength(5);
    expect(within(zone).getByText('All teams')).toBeInTheDocument();
    // The 4 lowest-progress teams (0..3) show; the 3 highest (4..6) are hidden.
    ['Team 0', 'Team 1', 'Team 2', 'Team 3'].forEach((n) =>
      expect(within(zone).getByText(n)).toBeInTheDocument(),
    );
    ['Team 4', 'Team 5', 'Team 6'].forEach((n) =>
      expect(within(zone).queryByText(n)).not.toBeInTheDocument(),
    );
  });
});

// ==============================|| FIXED-HEIGHT ROWS ZONE (shared with the rep) ||============================== //

describe('TeamAggregateBlock — the rows zone reserves the same height in every state', () => {
  it('5 teams → reserved height', () => {
    render(<TeamCampaignsBlock result={teams(5)} loading={false} />);
    expect(campaignsZone()).toHaveStyle({ minHeight: RESERVED });
  });
  it('2 teams → the SAME reserved height', () => {
    render(<TeamCampaignsBlock result={teams(2)} loading={false} />);
    expect(campaignsZone()).toHaveStyle({ minHeight: RESERVED });
  });
  it('0 teams (empty state) → the SAME reserved height', () => {
    render(<TeamCampaignsBlock result={EMPTY_RESULT} loading={false} />);
    expect(campaignsZone()).toHaveStyle({ minHeight: RESERVED });
    expect(screen.getByText('No active campaigns.')).toBeInTheDocument();
  });
  it('loading → the SAME reserved height', () => {
    render(<TeamCampaignsBlock result={null} loading />);
    expect(campaignsZone()).toHaveStyle({ minHeight: RESERVED });
  });
});

// ==============================|| PERMANENT "See all", NO ROW LINKS ||============================== //

describe('TeamAggregateBlock — permanent "See all", team rows never link', () => {
  it('campaigns: See all → /campaigns?status=ACTIVE, present even at 0 team, rows not links', () => {
    const { rerender } = render(<TeamCampaignsBlock result={teams(3)} loading={false} />);
    expect(screen.getByRole('link', { name: /see all/i })).toHaveAttribute('href', '/campaigns?status=ACTIVE');
    // team rows never navigate
    expect(screen.getByText('All teams').closest('a')).toBeNull();
    expect(screen.getByText('Team 0').closest('a')).toBeNull();

    // still present with zero teams
    rerender(<TeamCampaignsBlock result={EMPTY_RESULT} loading={false} />);
    expect(screen.getByRole('link', { name: /see all/i })).toHaveAttribute('href', '/campaigns?status=ACTIVE');
  });

  it('territories: See all → /territories, present even at 0 team, rows not links', () => {
    const { rerender } = render(<TeamTerritoriesBlock result={teams(3)} loading={false} />);
    expect(screen.getByRole('link', { name: /see all/i })).toHaveAttribute('href', '/territories');
    expect(screen.getByText('Team 1').closest('a')).toBeNull();

    rerender(<TeamTerritoriesBlock result={EMPTY_RESULT} loading={false} />);
    expect(screen.getByRole('link', { name: /see all/i })).toHaveAttribute('href', '/territories');
  });
});
