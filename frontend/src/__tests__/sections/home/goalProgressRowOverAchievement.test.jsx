// frontend/src/__tests__/sections/home/goalProgressRowOverAchievement.test.jsx
//
// GoalProgressRow: the OPTIONAL over-achievement rendering, and proof that
// WITHOUT the prop the row is unchanged (the Home consumers pass nothing).
// Real render — no shared-component mock.

import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';

import GoalProgressRow from 'sections/home/GoalProgressRow';

afterEach(cleanup);

const gradient = { pct: 50, mode: 'accumulated', headline: '5 done' };

describe('GoalProgressRow — over-achievement (opt-in)', () => {
  it('ratio > 1 shows the REAL percentage (not clamped), a star, and the over bar', () => {
    const { container } = render(
      <GoalProgressRow label="Revenue won" gradient={gradient} overAchievementRatio={1.3} />
    );
    // real, uncapped percentage — discriminant vs "100%"
    expect(screen.getByText('130%')).toBeTruthy();
    expect(screen.queryByText('100%')).toBeNull();
    // star marker present
    expect(screen.getByLabelText('over-achieved')).toBeTruthy();
    // the over branch (which paints warning.dark) is taken
    expect(container.querySelector('[data-over-achieved="true"]')).toBeTruthy();
  });

  it('ratio <= 1 renders the normal style (no star, no over bar, gradient pct)', () => {
    const { container } = render(
      <GoalProgressRow label="Meetings" gradient={gradient} overAchievementRatio={0.5} />
    );
    expect(screen.getByText('50%')).toBeTruthy();
    expect(screen.queryByLabelText('over-achieved')).toBeNull();
    expect(container.querySelector('[data-over-achieved="true"]')).toBeNull();
  });

  it('WITHOUT the prop the row is unchanged (non-regression for the Home)', () => {
    const { container } = render(<GoalProgressRow label="Leads" gradient={gradient} />);
    expect(screen.getByText('50%')).toBeTruthy();
    expect(screen.getByText('5 done')).toBeTruthy();
    expect(screen.queryByLabelText('over-achieved')).toBeNull();
    expect(container.querySelector('[data-over-achieved="true"]')).toBeNull();
  });
});
