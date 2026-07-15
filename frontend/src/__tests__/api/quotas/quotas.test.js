// frontend/src/__tests__/api/quotas/quotas.test.js

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, cleanup } from '@testing-library/react';

// ==============================|| MOCKS ||============================== //

const useSWRMock = vi.fn(() => ({ data: undefined, isLoading: false, error: null, mutate: vi.fn() }));
vi.mock('swr', () => ({ default: (key, options) => useSWRMock(key, options) }));

vi.mock('hooks/useAuth', () => ({
  useAuth: () => ({ tenantId: 'tenant-123' }),
}));

vi.mock('api/_swr', () => ({
  tenantKey: (url, tenantId) => (url && tenantId ? [url, tenantId] : null),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import { useGetMyActiveQuotas, endpoints } from 'api/quotas/quotas';

beforeEach(() => {
  vi.clearAllMocks();
  useSWRMock.mockImplementation(() => ({ data: undefined, isLoading: false, error: null, mutate: vi.fn() }));
});

afterEach(() => {
  cleanup();
});

describe('useGetMyActiveQuotas', () => {
  it('targets the current-period my-quotas endpoint, keyed by tenant', () => {
    renderHook(() => useGetMyActiveQuotas());
    const [key] = useSWRMock.mock.calls[0];
    expect(key).toEqual([endpoints.myActiveQuotas, 'tenant-123']);
    expect(endpoints.myActiveQuotas).toContain('current_period=true');
  });

  it('passes a null key when disabled', () => {
    renderHook(() => useGetMyActiveQuotas({ enabled: false }));
    const [key] = useSWRMock.mock.calls[0];
    expect(key).toBeNull();
  });

  it('unwraps the paginated results and count', () => {
    useSWRMock.mockReturnValue({
      data: { data: { results: [{ id: 1, target_type: 'closed_won' }], count: 1 } },
      isLoading: false,
      error: null,
      mutate: vi.fn(),
    });
    const { result } = renderHook(() => useGetMyActiveQuotas());
    expect(result.current.quotas).toHaveLength(1);
    expect(result.current.quotas[0].id).toBe(1);
    expect(result.current.quotasCount).toBe(1);
  });
});
