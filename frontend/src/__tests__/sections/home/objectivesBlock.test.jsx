// frontend/src/__tests__/sections/home/objectivesBlock.test.jsx
//
// The Home "Active objectives" block: the connected user's CURRENT objectives,
// capped to PROGRESS_TOP_N, ordered soonest-end then lowest-attainment, each row
// a real GoalProgressRow (bar + gold over-achievement). Permanent "See all" →
// the My Objectives route. Real renders — only next/font, the auth hook, and the
// data hook are mocked (no shared-component mock).

import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';

vi.mock('next/font/google', () => ({
  Public_Sans: () => ({ className: 'mock-public-sans', style: { fontFamily: 'mock' } }),
}));

const mockUseUserPermissions = vi.fn();
vi.mock('hooks/useUserPermissions', () => ({
  useUserPermissions: () => mockUseUserPermissions(),
}));

const mockUseGetObjectives = vi.fn();
vi.mock('api/objectives/objectives', () => ({
  useGetObjectives: (opts) => mockUseGetObjectives(opts),
}));

import ObjectivesBlock from 'sections/home/ObjectivesBlock';

afterEach(cleanup);

const q = (id, metric, state, period_end, progress_ratio, current_value = 3, target_value = 10) => ({
  id,
  metric,
  state,
  period_end,
  period_start: '2020-01-01',
  target_value,
  current_value,
  progress_ratio,
});

const precedes = (a, b) =>
  Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
const label = (name) => screen.getByText(name);

function mount(objectives, { currentUserId = 'u1', objectivesLoading = false } = {}) {
  mockUseUserPermissions.mockReturnValue({ currentUserId });
  mockUseGetObjectives.mockReturnValue({ objectives, objectivesLoading });
  return render(<ObjectivesBlock />);
}

describe('ObjectivesBlock — current objectives, cap, order, See all', () => {
  it('lists only CURRENT objectives, ordered soonest-end then lowest-attainment', () => {
    // Mixed states + dates: date-only order would put the PAST one first; the
    // block must both DROP non-current and order the currents by end then ratio.
    const c1 = q('1', 'REVENUE_WON', 'CURRENT', '2026-08-31', 0.6);
    const c2 = q('2', 'MEETINGS', 'CURRENT', '2026-08-15', 0.3);
    const fut = q('3', 'PIPELINE_VALUE', 'FUTURE', '2026-09-01', 0.0);
    const past = q('4', 'LEADS', 'PAST', '2020-12-31', 0.9);
    mount([c1, past, fut, c2]);

    // non-current excluded
    expect(screen.queryByText('Pipeline value')).toBeNull();
    expect(screen.queryByText('Leads')).toBeNull();
    // currents present, c2 (ends 2026-08-15) before c1 (ends 2026-08-31)
    expect(label('Meetings')).toBeTruthy();
    expect(label('Won value')).toBeTruthy();
    expect(precedes(label('Meetings'), label('Won value'))).toBe(true);
  });

  it('caps the list to PROGRESS_TOP_N (5) rows, dropping the latest-ending', () => {
    // Six currents with ascending end dates; the 6th (latest end) must be cut.
    const metrics = ['MEETINGS', 'LEADS', 'REVENUE_WON', 'NEW_LOGOS', 'DECISION_CYCLES', 'PIPELINE_VALUE'];
    const objs = metrics.map((m, i) =>
      q(String(i), m, 'CURRENT', `2026-1${i}-01`, 0.5),
    );
    const { container } = mount(objs);
    // exactly 5 bars rendered
    expect(container.querySelectorAll('.MuiLinearProgress-root').length).toBe(5);
    // the latest-ending objective (Pipeline value, 2026-15-01) is the one dropped
    expect(screen.queryByText('Pipeline value')).toBeNull();
    expect(label('Meetings')).toBeTruthy();
  });

  it('renders a permanent "See all" linking to the My Objectives route', () => {
    const { container } = mount([q('1', 'MEETINGS', 'CURRENT', '2026-08-15', 0.3)]);
    const link = container.querySelector('a[href="/objectives"]');
    expect(link).not.toBeNull();
    expect(link).toHaveTextContent('See all');
  });

  it('empty state keeps the block (fixed-height zone + message), not hidden', () => {
    const { container } = mount([q('1', 'LEADS', 'PAST', '2020-12-31', 0.5)]); // no currents
    expect(screen.getByText('No active objectives.')).toBeTruthy();
    // the fixed-height rows zone is still present (block not collapsed/hidden)
    expect(container.querySelector('[data-testid="objectives-rows-zone"]')).not.toBeNull();
    // See all still permanent
    expect(container.querySelector('a[href="/objectives"]')).not.toBeNull();
  });

  it('an over-achieved current objective renders a full gold-marked bar', () => {
    const { container } = mount([q('1', 'REVENUE_WON', 'CURRENT', '2026-08-31', 1.3, 13, 10)]);
    // star (gold over-achievement marker) present
    expect(screen.getByLabelText('over-achieved')).toBeTruthy();
    // the real, uncapped percentage is shown
    expect(screen.getByText('130%')).toBeTruthy();
    // the FULL bar keeps the success token (same as a normal 100% bar)
    const bar = container.querySelector('.MuiLinearProgress-root');
    expect(bar.className).toContain('MuiLinearProgress-colorSuccess');
  });

  it('passes the owner filter (own objectives only) to the data hook', () => {
    mount([]);
    // the hook is called with filters scoping to the connected user's id
    const call = mockUseGetObjectives.mock.calls.at(-1)[0];
    expect(call.filters.owner).toBe('u1');
    expect(call.enabled).toBe(true);
  });
});
