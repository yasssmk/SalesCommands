// frontend/src/__tests__/api/metricSurfaceRevalidation.test.js
//
// A write that changes a metric INPUT must revalidate the surfaces that DISPLAY
// the derived number — not only the endpoint it wrote to.
//
// THE GAP. Each write helper revalidated its own keys: a deal-product save
// refreshed the DC list's Amount column and nothing else. The campaign card, the
// objectives block and every KPI read live behind other keys (/campaigns/,
// /quotas/quotas/, /bi/kpi/), so they only refreshed on window focus or when SWR
// judged them stale — which is why a card looked frozen right after the action
// that changed it.
//
// This is the CLIENT half of the freshness fix. The SERVER half (the campaign
// read caches ignoring decision_cycles/activities/accounts tag bumps) is pinned
// in backend/tests/campaigns/test_campaign_cache_freshness.py. Both were real:
// fixing only the client leaves Redis handing back the same stale body.
//
// The assertions are on the PREFIXES passed to SWR's mutate, because
// revalidateByPrefix matches keys by prefix (api/_swr.js matchKey) — '/campaigns/'
// covers the list, every detail and every dashboard.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const mutate = vi.fn(() => Promise.resolve());
vi.mock('swr', () => ({ mutate: (...a) => mutate(...a) }));

// utils/axiosClient wraps axios and returns { success, data, ... } — the helpers
// branch on `success`, not on an HTTP status.
const ok = { success: true, status: 200, data: { data: { id: 'x' } } };
const post = vi.fn(() => Promise.resolve(ok));
const patch = vi.fn(() => Promise.resolve(ok));
const del = vi.fn(() => Promise.resolve({ success: true, status: 204, data: {} }));
vi.mock('utils/axiosClient', () => ({
  api: {
    post: (...a) => post(...a),
    patch: (...a) => patch(...a),
    delete: (...a) => del(...a),
    get: vi.fn(() => Promise.resolve({ status: 200, data: { data: [] } })),
  },
}));
vi.mock('utils/displayError', () => ({
  displayErrorSnackbar: vi.fn(),
  displaySuccessSnackbar: vi.fn(),
}));

import { METRIC_SURFACE_PREFIXES } from 'api/_swr';
import { createDCProduct, updateDCProduct, deleteDCProduct } from 'api/accounts/decisionCycles';

// Real UUIDs: the helpers validate their ids (utils/validators.isValidUUID) and
// short-circuit before any request otherwise.
const CYCLE = '11111111-1111-4111-8111-111111111111';
const LINE = '22222222-2222-4222-8222-222222222222';
const PRODUCT = '33333333-3333-4333-8333-333333333333';

beforeEach(() => {
  mutate.mockClear();
  post.mockClear();
  patch.mockClear();
  del.mockClear();
});
afterEach(() => vi.clearAllMocks());

/** Every prefix handed to SWR's mutate during the last call. */
function revalidatedPrefixes() {
  return mutate.mock.calls
    .map(([matcher]) => matcher)
    .filter((m) => typeof m === 'function')
    .map((m) => {
      // matchKey returns a closure; probe it with candidate keys instead of
      // reaching into its internals.
      const probes = [
        '/campaigns/', '/quotas/quotas/', '/bi/kpi/',
        '/decision_cycles/', '/module-activities/', '/company-accounts/',
      ];
      return probes.filter((p) => m([p, 'tenant-1']));
    })
    .flat();
}

describe('metric-surface revalidation', () => {
  it('declares the three surfaces that show derived numbers', () => {
    expect(METRIC_SURFACE_PREFIXES).toEqual([
      '/campaigns/',
      '/quotas/quotas/',
      '/bi/kpi/',
    ]);
  });

  it.each([
    ['create', () => createDCProduct(CYCLE, { product_catalog_entry: PRODUCT, quantity: 1 })],
    ['update', () => updateDCProduct(CYCLE, LINE, { unit_price: 999 })],
    ['delete', () => deleteDCProduct(CYCLE, LINE)],
  ])('a product %s revalidates the campaign, objective and KPI surfaces', async (_label, run) => {
    await run();

    const prefixes = revalidatedPrefixes();
    expect(prefixes).toContain('/campaigns/');
    expect(prefixes).toContain('/quotas/quotas/');
    expect(prefixes).toContain('/bi/kpi/');
  });

  it('still revalidates the writer own keys', async () => {
    // Anti-over-correction: widening the set must not replace what already
    // worked — the DC list's Amount column still refreshes.
    await updateDCProduct(CYCLE, LINE, { unit_price: 999 });

    expect(revalidatedPrefixes()).toContain('/decision_cycles/');
  });
});
