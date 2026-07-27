// frontend/src/__tests__/sections/home/goalProgressRowOverAchievement.test.jsx
//
// GoalProgressRow over-achievement: the FULL bar keeps the normal 100% token
// (color="success", NOT a gold / "empty" colour); only the star and the % label
// carry the theme gold (warning.dark). WITHOUT the prop the row is unchanged.
// Real render — no shared-component mock; assertions on the real MUI classes.

import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';

import GoalProgressRow from 'sections/home/GoalProgressRow';

afterEach(cleanup);

const gradient = { pct: 50, mode: 'accumulated', headline: '5 done' };

function pctLabelClass(container) {
  const el = [...container.querySelectorAll('.MuiTypography-root')].find(
    (e) => e.children.length === 0 && /%$/.test(e.textContent),
  );
  return el ? el.className : '';
}

describe('GoalProgressRow — over-achievement colour', () => {
  it('ratio > 1: FULL bar uses the success token (same as normal 100%), NOT gold', () => {
    const { container } = render(
      <GoalProgressRow label="Revenue won" gradient={gradient} overAchievementRatio={1.3} />
    );
    const bar = container.querySelector('.MuiLinearProgress-root');
    // bar carries the success colour token (the normal full-bar token) ...
    expect(bar.className).toContain('MuiLinearProgress-colorSuccess');
    // ... and NOT a warning/gold or the light primary "empty" token.
    expect(bar.className).not.toContain('MuiLinearProgress-colorWarning');
    expect(bar.className).not.toContain('MuiLinearProgress-colorPrimary');
    // real, uncapped percentage
    expect(screen.getByText('130%')).toBeTruthy();
    // star present (gold marker)
    expect(screen.getByLabelText('over-achieved')).toBeTruthy();
  });

  it('the over % label uses a DIFFERENT (gold) colour token than a normal label', () => {
    const { container: over } = render(
      <GoalProgressRow label="A" gradient={gradient} overAchievementRatio={1.3} />
    );
    const overClass = pctLabelClass(over);
    cleanup();
    const { container: normal } = render(<GoalProgressRow label="A" gradient={gradient} />);
    const normalClass = pctLabelClass(normal);
    // the label colour is driven by labelColor='warning.dark' only in the over
    // case, so the resolved class must differ from the default text.secondary.
    expect(overClass).not.toBe('');
    expect(overClass).not.toBe(normalClass);
  });

  it('ratio <= 1: normal style (no star, primary/success by pct), unchanged', () => {
    const { container } = render(
      <GoalProgressRow label="Meetings" gradient={gradient} overAchievementRatio={0.5} />
    );
    expect(screen.getByText('50%')).toBeTruthy();
    expect(screen.queryByLabelText('over-achieved')).toBeNull();
    expect(container.querySelector('[data-over-achieved="true"]')).toBeNull();
    expect(container.querySelector('.MuiLinearProgress-colorPrimary')).toBeTruthy();
  });

  it('WITHOUT the prop the row is unchanged (non-regression for the Home)', () => {
    const { container } = render(<GoalProgressRow label="Leads" gradient={gradient} />);
    expect(screen.getByText('50%')).toBeTruthy();
    expect(screen.getByText('5 done')).toBeTruthy();
    expect(screen.queryByLabelText('over-achieved')).toBeNull();
    expect(container.querySelector('.MuiLinearProgress-colorPrimary')).toBeTruthy();
  });
});
