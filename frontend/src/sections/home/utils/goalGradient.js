// frontend/src/sections/home/utils/goalGradient.js

/**
 * Goal-gradient framing for a "done out of total" value.
 *
 * Two framings, for two psychologies:
 *
 * - `framing='goal'` (default): reaching a target. Early it surfaces accumulated
 *   progress ("32 done"); past a threshold it surfaces what remains ("only 8
 *   left"). Used by the quota block.
 * - `framing='queue'`: a work queue. The REMAINING is the actionable info the
 *   whole way through ("18 accounts to go"), so it never shows accumulated and
 *   never says "only" early. Used by the campaigns / territories block.
 *
 * It always returns a percentage for the accompanying visual — never a cold
 * ratio alone.
 *
 * @param {number} done
 * @param {number} total
 * @param {Object} [opts]
 * @param {string} [opts.unit='']       - appended to the number ('%', '$', ...) — goal framing.
 * @param {number} [opts.flipAt=66]     - pct at which to switch to "remaining" — goal framing.
 * @param {string} [opts.framing='goal']- 'goal' | 'queue'.
 * @param {string} [opts.noun='']       - counted noun for the queue headline ("accounts").
 * @returns {{ mode: string, pct: number, done: number, total: number, remaining: number, headline: string }}
 */
export function goalGradient(done, total, opts = {}) {
  const { unit = '', flipAt = 66, framing = 'goal', noun = '' } = opts;
  const d = Math.max(0, Number(done) || 0);
  const t = Math.max(0, Number(total) || 0);

  if (!t) {
    return { mode: 'none', pct: 0, done: d, total: 0, remaining: 0, headline: fmt(d, unit) };
  }

  const remaining = Math.max(0, t - d);
  const pct = Math.min(100, Math.round((d / t) * 100));

  // Work-queue framing: remaining-as-action throughout, neutral (no "only").
  if (framing === 'queue') {
    const suffix = noun ? ` ${noun}` : '';
    const headline = remaining === 0 ? 'All done' : `${remaining}${suffix} to go`;
    return { mode: remaining === 0 ? 'done' : 'queue', pct, done: d, total: t, remaining, headline };
  }

  if (remaining === 0) {
    return { mode: 'done', pct: 100, done: d, total: t, remaining: 0, headline: 'Done' };
  }

  const mode = pct >= flipAt ? 'remaining' : 'accumulated';
  const headline = mode === 'remaining'
    ? `Only ${fmt(remaining, unit)} left`
    : `${fmt(d, unit)} done`;

  return { mode, pct, done: d, total: t, remaining, headline };
}

function fmt(n, unit) {
  const rounded = Math.round(n * 100) / 100;
  if (unit === '$') return `$${rounded.toLocaleString()}`;
  return `${rounded}${unit}`;
}
