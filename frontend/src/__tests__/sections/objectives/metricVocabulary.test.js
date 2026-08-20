// frontend/src/__tests__/sections/objectives/metricVocabulary.test.js
//
// The metric vocabulary the objective UI offers, pinned against the backend's.
//
// LEADS was removed end to end (PO). A deletion is the one change nothing else
// catches: the picker would simply stop listing it and no existing test would
// notice, so the absence is asserted here directly — and so is the presence of
// the five that remain, because "the list is shorter" must not be able to pass
// by accident when a live metric goes missing too.
//
// METRICS is what ObjectiveForm renders as the metric <Select>'s options
// (sections/objectives/ObjectiveForm.jsx), so asserting on it is asserting on
// what the user can pick.

import { describe, it, expect } from 'vitest';

import { METRICS, metricLabel, isMonetaryMetric } from 'sections/objectives/metricLabels';

describe('objective metric vocabulary', () => {
  it('no longer offers LEADS', () => {
    expect(METRICS.map((m) => m.value)).not.toContain('LEADS');
  });

  it('offers exactly the five backend MetricKey values', () => {
    expect(METRICS.map((m) => m.value).sort()).toEqual([
      'DECISION_CYCLES',
      'MEETINGS',
      'NEW_LOGOS',
      'PIPELINE_VALUE',
      'REVENUE_WON',
    ]);
  });

  it('renders an objective stored under the retired key as its raw identifier', () => {
    // Quota.metric is a plain column, so a row written before the removal can
    // still reach the UI. It must show something, not an empty cell.
    expect(metricLabel('LEADS')).toBe('LEADS');
    expect(isMonetaryMetric('LEADS')).toBe(false);
  });

  it('still labels and types the surviving metrics', () => {
    expect(metricLabel('DECISION_CYCLES')).toBe('Decision cycles');
    expect(isMonetaryMetric('PIPELINE_VALUE')).toBe(true);
    expect(isMonetaryMetric('MEETINGS')).toBe(false);
  });
});
