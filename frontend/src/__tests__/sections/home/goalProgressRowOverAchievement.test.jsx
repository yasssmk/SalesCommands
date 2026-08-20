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

// The determinate bar's FILL element. Its inline transform encodes the fill:
// MUI renders `translateX(0%)` for a full (value 100) bar and shifts it left for
// less. For value > 100 MUI shifts it RIGHT (off-screen) — the bug this fix
// closes — so a FULL, capped bar reads translateX(0%) at any percentage.
function barFill(container) {
  return container.querySelector('.MuiLinearProgress-bar1Determinate');
}

describe('GoalProgressRow — over-achievement colour', () => {
  it('ratio > 1: FULL bar uses the success token (same as normal 100%), NOT gold', () => {
    const { container } = render(
      <GoalProgressRow label="Won value" gradient={gradient} overAchievementRatio={1.3} />
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

  it('the FULL over bar keeps the SAME fill token at any percentage (130% and 300%)', () => {
    // 130%: capped bar is full (translateX 0%), success token, real label.
    const { container: c130 } = render(
      <GoalProgressRow label="A" gradient={gradient} overAchievementRatio={1.3} />
    );
    const bar130 = c130.querySelector('.MuiLinearProgress-root');
    const fill130 = barFill(c130);
    expect(bar130.className).toContain('MuiLinearProgress-colorSuccess');
    expect(fill130.style.transform).toBe('translateX(0%)'); // FULL, not off-screen
    cleanup();

    // 300%: the bar looks IDENTICAL (full, same success token) — a single fill
    // colour regardless of magnitude — while the LABEL shows the real 300%.
    const { container: c300 } = render(
      <GoalProgressRow label="A" gradient={gradient} overAchievementRatio={3.0} />
    );
    const bar300 = c300.querySelector('.MuiLinearProgress-root');
    const fill300 = barFill(c300);
    expect(bar300.className).toContain('MuiLinearProgress-colorSuccess');
    expect(bar300.className).not.toContain('MuiLinearProgress-colorPrimary');
    expect(fill300.style.transform).toBe('translateX(0%)'); // FULL at 300%, not empty
    // the fill token/transform is the SAME as at 130% — one colour, always.
    expect(bar300.className).toBe(bar130.className);
    expect(fill300.style.transform).toBe(fill130.style.transform);
    // the label is NOT capped — it shows the real, uncapped percentage.
    expect(screen.getByText('300%')).toBeTruthy();
    expect(screen.queryByText('100%')).toBeNull();
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
    const { container } = render(<GoalProgressRow label="Meetings" gradient={gradient} />);
    expect(screen.getByText('50%')).toBeTruthy();
    expect(screen.getByText('5 done')).toBeTruthy();
    expect(screen.queryByLabelText('over-achieved')).toBeNull();
    expect(container.querySelector('.MuiLinearProgress-colorPrimary')).toBeTruthy();
  });
});
