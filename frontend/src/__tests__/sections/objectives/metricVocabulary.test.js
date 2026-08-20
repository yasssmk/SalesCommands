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

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';

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

// ---------------------------------------------------------------------------
// The source guard — the string itself, not just the exported list
// ---------------------------------------------------------------------------
//
// The vocabulary assertions above pin what METRICS holds. They do NOT catch a
// hard-coded 'Leads' pasted into a card, a chart legend or a filter chip on some
// other objective screen, which is how a retired metric usually comes back. This
// scans the SOURCE of every objective/metric surface for the string.
//
// SCOPED ON PURPOSE, not whole-tree. 'leads' is also a live PERMISSIONS module
// (sections/admin/roles/permissionsRegistry.js) backing apps.leads, which is
// installed and routed and has nothing to do with the metric; and the word
// occurs in ordinary English in comments ("See all leads to..."). A blanket
// repo-wide ban would fail on code that must stay and would be deleted by the
// next person who hits it. These are the directories that render metrics.

const SURFACE_DIRS = [
  'src/sections/objectives',
  'src/views/objectives',
];
const SURFACE_FILES = [
  'src/sections/home/ObjectivesBlock.jsx',
];

function sourceFiles() {
  // vitest runs from the frontend package root, so the paths below read the
  // same as they do in an editor.
  const root = process.cwd();
  const found = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      if (statSync(full).isDirectory()) walk(full);
      else if (/\.(js|jsx|ts|tsx)$/.test(entry)) found.push(full);
    }
  };
  SURFACE_DIRS.forEach((d) => walk(resolve(root, d)));
  SURFACE_FILES.forEach((f) => found.push(resolve(root, f)));
  return found;
}

// Strip line and block comments: metricLabels.js explains the removal in prose,
// and that explanation must not be what keeps this test honest or trips it.
function code(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
}

describe('no metric surface offers or renders "Leads"', () => {
  it('finds the surfaces it claims to scan', () => {
    // Guards the guard: a renamed directory would silently scan nothing and
    // pass forever.
    const files = sourceFiles();
    expect(files.length).toBeGreaterThanOrEqual(6);
    expect(files.some((f) => f.endsWith('metricLabels.js'))).toBe(true);
    expect(files.some((f) => f.endsWith('ObjectivesBlock.jsx'))).toBe(true);
  });

  it('contains neither the LEADS key nor the "Leads" label', () => {
    const offenders = sourceFiles().filter((file) => {
      const body = code(readFileSync(file, 'utf8'));
      return /\bLEADS\b/.test(body) || /['"`]Leads['"`]/.test(body);
    });

    expect(offenders).toEqual([]);
  });
});
