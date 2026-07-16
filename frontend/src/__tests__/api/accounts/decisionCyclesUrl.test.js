// frontend/src/__tests__/api/accounts/decisionCyclesUrl.test.js
//
// buildUrlWithParams for the decision-cycles API. The whole point of item 4d's
// front-API change is that owner_scope + outcome__isnull are ADDITIVE: present
// -> forwarded, absent -> the URL is byte-for-byte what it was before. These
// tests pin both halves so no future edit can silently start scoping every
// existing caller of useGetDecisionCycles / useGetDecisionSteps.

import { describe, it, expect, vi } from 'vitest';

// The module pulls SWR/auth/axios at import time; none are exercised by the
// pure URL builder, so stub them to keep the unit test isolated and fast.
vi.mock('swr', () => ({ default: () => ({}), mutate: vi.fn() }));
vi.mock('hooks/useAuth', () => ({ useAuth: () => ({ tenantId: 't' }) }));
vi.mock('utils/axiosClient', () => ({ api: {} }));
vi.mock('api/_swr', () => ({ tenantKey: (u) => u, revalidateMultiple: vi.fn() }));

import { buildUrlWithParams } from 'api/accounts/decisionCycles';

const BASE = '/decision_cycles/';

describe('buildUrlWithParams — additive owner_scope / outcome__isnull', () => {
  it('forwards owner_scope only when present', () => {
    expect(buildUrlWithParams(BASE, { filters: { owner_scope: 'mine' } })).toBe(
      `${BASE}?owner_scope=mine`,
    );
  });

  it('forwards outcome__isnull as the backend true/false string', () => {
    expect(buildUrlWithParams(BASE, { filters: { outcome__isnull: true } })).toBe(
      `${BASE}?outcome__isnull=true`,
    );
    expect(buildUrlWithParams(BASE, { filters: { outcome__isnull: false } })).toBe(
      `${BASE}?outcome__isnull=false`,
    );
  });

  it('builds the "my open cycles" URL the rep Home block relies on', () => {
    const url = buildUrlWithParams(BASE, {
      page: 1,
      pageSize: 50,
      filters: { owner_scope: 'mine', outcome__isnull: true },
    });
    expect(url).toBe(`${BASE}?page=1&page_size=50&owner_scope=mine&outcome__isnull=true`);
  });

  // ---- ADDITIVE PROOF: absent -> not in the URL at all ------------------- //

  it('omits owner_scope and outcome__isnull entirely when not passed', () => {
    const url = buildUrlWithParams(BASE, {
      page: 2,
      pageSize: 25,
      search: 'acme',
      filters: { account: 'a-1', status: 'IN_PROGRESS' },
    });
    expect(url).not.toContain('owner_scope');
    expect(url).not.toContain('outcome__isnull');
    // and the pre-existing params are untouched (byte-for-byte legacy behavior)
    expect(url).toBe(`${BASE}?page=2&page_size=25&search=acme&account=a-1&status=IN_PROGRESS`);
  });

  it('a bare call (no params) is unchanged — just the base URL', () => {
    expect(buildUrlWithParams(BASE)).toBe(BASE);
  });

  it('does not forward an empty-string owner_scope', () => {
    // Guard against `owner_scope: ''` leaking a dangling param.
    expect(buildUrlWithParams(BASE, { filters: { owner_scope: '' } })).toBe(BASE);
  });
});
