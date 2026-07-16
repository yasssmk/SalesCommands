// frontend/src/__tests__/views/home/goalGradient.test.js

import { describe, it, expect } from 'vitest';

import { goalGradient } from 'sections/home/utils/goalGradient';

describe('goalGradient', () => {
  it('frames accumulated progress early ("X done")', () => {
    const g = goalGradient(30, 100);
    expect(g.mode).toBe('accumulated');
    expect(g.pct).toBe(30);
    expect(g.headline).toBe('30 done');
  });

  it('flips to remaining framing near the end ("only X left")', () => {
    const g = goalGradient(92, 100);
    expect(g.mode).toBe('remaining');
    expect(g.remaining).toBe(8);
    expect(g.headline).toBe('Only 8 left');
  });

  it('reports done when nothing remains', () => {
    const g = goalGradient(100, 100);
    expect(g.mode).toBe('done');
    expect(g.pct).toBe(100);
    expect(g.headline).toBe('Done');
  });

  it('caps pct at 100 when overachieving', () => {
    const g = goalGradient(120, 100);
    expect(g.pct).toBe(100);
    expect(g.mode).toBe('done');
  });

  it('supports a currency unit in the headline', () => {
    const g = goalGradient(9000, 10000, { unit: '$' });
    expect(g.headline).toBe('Only $1,000 left');
  });

  it('supports a percent unit', () => {
    const g = goalGradient(85, 100, { unit: '%' });
    expect(g.headline).toBe('Only 15% left');
  });

  it('returns a safe none-mode when total is missing', () => {
    const g = goalGradient(5, 0);
    expect(g.mode).toBe('none');
    expect(g.pct).toBe(0);
    expect(g.remaining).toBe(0);
  });
});
