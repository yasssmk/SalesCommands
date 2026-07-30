// frontend/src/__tests__/api/bi/kpi.test.js

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, cleanup } from '@testing-library/react';

// ==============================|| MOCKS ||============================== //

// Capture (key, fetcher|options, options) so both useKpi (options 2nd) and
// useKpiBatch (fetcher 2nd, options 3rd) can be asserted.
const swrMock = vi.fn(() => ({ data: undefined, isLoading: false, error: null, mutate: vi.fn() }));
vi.mock('swr', () => ({ default: (key, a, b) => swrMock(key, a, b) }));

vi.mock('hooks/useAuth', () => ({
  useAuth: () => ({ tenantId: 'tenant-123' }),
}));

vi.mock('utils/axiosClient', () => ({
  api: { post: vi.fn() },
}));

vi.mock('api/_swr', () => ({
  tenantKey: (url, tenantId) => (url && tenantId ? [url, tenantId] : null),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import { api } from 'utils/axiosClient';
import {
  useKpi,
  useKpiBatch,
  buildKpiUrl,
  chunk,
  batchFetcher,
  endpoints,
  BATCH_CAP,
} from 'api/bi/kpi';

beforeEach(() => {
  vi.clearAllMocks();
  swrMock.mockImplementation(() => ({ data: undefined, isLoading: false, error: null, mutate: vi.fn() }));
});

afterEach(() => {
  cleanup();
});

describe('buildKpiUrl', () => {
  it('builds a bare url with no options', () => {
    expect(buildKpiUrl('todo_my_activities')).toBe('/bi/kpi/todo_my_activities/');
  });

  it('appends scope, period and forwards extra params', () => {
    const url = buildKpiUrl('quota_attainment', { scope: 'mine', period: 'all', params: { quota_id: 42 } });
    expect(url).toBe('/bi/kpi/quota_attainment/?scope=mine&period=all&quota_id=42');
  });

  it('skips null/undefined/empty params', () => {
    const url = buildKpiUrl('k', { scope: 'team', params: { a: undefined, b: null, c: '', d: 'x' } });
    expect(url).toBe('/bi/kpi/k/?scope=team&d=x');
  });
});

describe('chunk', () => {
  it('splits into fixed-size groups', () => {
    expect(chunk([1, 2, 3, 4, 5], 2)).toEqual([[1, 2], [3, 4], [5]]);
    expect(chunk([], 3)).toEqual([]);
  });
});

describe('useKpi', () => {
  it('keys on the built url + tenant', () => {
    renderHook(() => useKpi('todo_my_activities', { scope: 'mine' }));
    const [key] = swrMock.mock.calls[0];
    expect(key).toEqual(['/bi/kpi/todo_my_activities/?scope=mine', 'tenant-123']);
  });

  it('passes a null key when disabled so SWR skips', () => {
    renderHook(() => useKpi('todo_my_activities', { enabled: false }));
    const [key] = swrMock.mock.calls[0];
    expect(key).toBeNull();
  });

  it('unwraps the KPI dict from the wrapped { data } body', () => {
    swrMock.mockReturnValue({
      data: { data: { key: 'x', value: 5, shape: 'scalar' } },
      isLoading: false,
      error: null,
      mutate: vi.fn(),
    });
    const { result } = renderHook(() => useKpi('x', { scope: 'mine' }));
    expect(result.current.kpi).toEqual({ key: 'x', value: 5, shape: 'scalar' });
  });
});

describe('useKpiBatch', () => {
  it('keys on the batch endpoint + tenant + serialized requests', () => {
    const reqs = [{ key: 'a', scope: 'mine' }];
    renderHook(() => useKpiBatch(reqs));
    const [key] = swrMock.mock.calls[0];
    expect(key).toEqual([endpoints.batch, 'tenant-123', JSON.stringify(reqs)]);
  });

  it('passes a null key for an empty request list', () => {
    renderHook(() => useKpiBatch([]));
    const [key] = swrMock.mock.calls[0];
    expect(key).toBeNull();
  });

  it('returns results in order from SWR data', () => {
    swrMock.mockReturnValue({
      data: [{ key: 'a', value: 1 }, { key: 'b', error: 'x', status: 404 }],
      isLoading: false,
      error: null,
      mutate: vi.fn(),
    });
    const { result } = renderHook(() => useKpiBatch([{ key: 'a' }, { key: 'b' }]));
    expect(result.current.results).toHaveLength(2);
    expect(result.current.results[1].status).toBe(404);
  });
});

describe('batchFetcher', () => {
  it('chunks past the cap and concatenates results in order', async () => {
    // 25 requests -> chunks of 20 + 5 -> two POSTs.
    const requests = Array.from({ length: BATCH_CAP + 5 }, (_, i) => ({ key: `k${i}` }));
    api.post
      .mockResolvedValueOnce({ success: true, data: { success: true, data: { results: [{ key: 'first' }] } } })
      .mockResolvedValueOnce({ success: true, data: { success: true, data: { results: [{ key: 'second' }] } } });

    const results = await batchFetcher(requests);

    expect(api.post).toHaveBeenCalledTimes(2);
    expect(api.post.mock.calls[0][1].requests).toHaveLength(BATCH_CAP);
    expect(api.post.mock.calls[1][1].requests).toHaveLength(5);
    expect(results).toEqual([{ key: 'first' }, { key: 'second' }]);
  });

  it('throws on a transport-level failure so SWR surfaces the error', async () => {
    api.post.mockResolvedValueOnce({ success: false, error: 'boom', status: 500 });
    await expect(batchFetcher([{ key: 'a' }])).rejects.toThrow('boom');
  });
});
