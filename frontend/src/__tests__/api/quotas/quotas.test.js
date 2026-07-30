// frontend/src/__tests__/api/quotas/quotas.test.js

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, cleanup } from '@testing-library/react';

// ==============================|| MOCKS ||============================== //

const swrMock = vi.fn(() => ({ data: undefined, isLoading: false, error: null, mutate: vi.fn() }));
vi.mock('swr', () => ({ default: (key, options) => swrMock(key, options) }));

vi.mock('hooks/useAuth', () => ({
  useAuth: () => ({ tenantId: 'tenant-123' }),
}));

vi.mock('api/_swr', () => ({
  tenantKey: (url, tenantId) => (url && tenantId ? [url, tenantId] : null),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import { useGetMyActiveQuotas, useGetTeamQuotas, endpoints } from 'api/quotas/quotas';

beforeEach(() => {
  vi.clearAllMocks();
  swrMock.mockImplementation(() => ({ data: undefined, isLoading: false, error: null, mutate: vi.fn() }));
});

afterEach(() => {
  cleanup();
});

describe('useGetMyActiveQuotas', () => {
  it('targets the current-period my-quotas endpoint, keyed by tenant', () => {
    renderHook(() => useGetMyActiveQuotas());
    const [key] = swrMock.mock.calls[0];
    expect(key).toEqual([endpoints.myActiveQuotas, 'tenant-123']);
    expect(endpoints.myActiveQuotas).toContain('current_period=true');
  });

  it('passes a null key when disabled', () => {
    renderHook(() => useGetMyActiveQuotas({ enabled: false }));
    const [key] = swrMock.mock.calls[0];
    expect(key).toBeNull();
  });

  it('unwraps the paginated results and count', () => {
    swrMock.mockReturnValue({
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

describe('useGetTeamQuotas', () => {
  it('narrows to a team, current period + active, keyed by tenant', () => {
    renderHook(() => useGetTeamQuotas('team-9'));
    const [key] = swrMock.mock.calls[0];
    expect(key).toEqual([endpoints.teamQuotas('team-9'), 'tenant-123']);
    expect(endpoints.teamQuotas('team-9')).toContain('user__team=team-9');
    expect(endpoints.teamQuotas('team-9')).toContain('current_period=true');
    expect(endpoints.teamQuotas('team-9')).toContain('status=active');
  });

  it('passes a null key until the teamId is known', () => {
    renderHook(() => useGetTeamQuotas(null));
    const [key] = swrMock.mock.calls[0];
    expect(key).toBeNull();
  });

  it('unwraps the team quota rows', () => {
    swrMock.mockReturnValue({
      data: { data: { results: [{ id: 5, user_id: 'u1', user_name: 'Alice' }], count: 1 } },
      isLoading: false,
      error: null,
      mutate: vi.fn(),
    });
    const { result } = renderHook(() => useGetTeamQuotas('team-9'));
    expect(result.current.quotas[0].user_id).toBe('u1');
  });
});
