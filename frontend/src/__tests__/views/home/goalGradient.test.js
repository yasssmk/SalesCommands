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

describe('goalGradient — queue framing', () => {
  it('surfaces the remaining as the action throughout ("X noun to go"), even early', () => {
    const g = goalGradient(2, 20, { framing: 'queue', noun: 'accounts' });
    expect(g.mode).toBe('queue');
    expect(g.pct).toBe(10);
    expect(g.remaining).toBe(18);
    expect(g.headline).toBe('18 accounts to go'); // not "2 done", not "Only 18 left"
  });

  it('never says "only" near the end — still the plain remaining ("2 accounts to go")', () => {
    const g = goalGradient(18, 20, { framing: 'queue', noun: 'accounts' });
    expect(g.mode).toBe('queue');
    expect(g.headline).toBe('2 accounts to go');
  });

  it('reports "All done" when the queue is empty', () => {
    const g = goalGradient(20, 20, { framing: 'queue', noun: 'accounts' });
    expect(g.mode).toBe('done');
    expect(g.pct).toBe(100);
    expect(g.headline).toBe('All done');
  });

  it('omits the noun gracefully', () => {
    const g = goalGradient(3, 5, { framing: 'queue' });
    expect(g.headline).toBe('2 to go');
  });

  it('default framing is unchanged (goal) — same input reads "2 done", not "3 to go"', () => {
    expect(goalGradient(2, 20).headline).toBe('2 done'); // goal default, iso with existing behavior
  });
});
