// frontend/src/__tests__/api/notifications/notifications.test.js

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, cleanup } from '@testing-library/react';

// ==============================|| MOCKS ||============================== //

// Capture the SWR options each hook passes so we can assert polling config.
const useSWRMock = vi.fn(() => ({ data: undefined, isLoading: false, error: null, mutate: vi.fn() }));
vi.mock('swr', () => ({ default: (key, options) => useSWRMock(key, options) }));

vi.mock('hooks/useAuth', () => ({
  useAuth: () => ({ tenantId: 'tenant-123' }),
}));

vi.mock('utils/axiosClient', () => ({
  api: { post: vi.fn() },
}));

vi.mock('api/_swr', () => ({
  // Pass-through key builder mirroring the real tenantKey contract.
  tenantKey: (url, tenantId) => (url && tenantId ? [url, tenantId] : null),
  revalidateByPrefix: vi.fn(),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import { api } from 'utils/axiosClient';
import { revalidateByPrefix } from 'api/_swr';
import {
  useGetNotifications,
  useUnreadCount,
  markNotificationRead,
  deriveUnreadCount,
  endpoints,
} from 'api/notifications/notifications';

// ==============================|| TESTS ||============================== //

beforeEach(() => {
  vi.clearAllMocks();
  useSWRMock.mockImplementation(() => ({ data: undefined, isLoading: false, error: null, mutate: vi.fn() }));
});

afterEach(() => {
  cleanup();
});

describe('deriveUnreadCount', () => {
  it('reads the wrapped { data: { count } } shape', () => {
    expect(deriveUnreadCount({ data: { count: 5 } })).toBe(5);
  });

  it('reads a bare { count } shape', () => {
    expect(deriveUnreadCount({ count: 3 })).toBe(3);
  });

  it('defaults to 0 when count is missing, null or negative', () => {
    expect(deriveUnreadCount(undefined)).toBe(0);
    expect(deriveUnreadCount({})).toBe(0);
    expect(deriveUnreadCount({ data: {} })).toBe(0);
    expect(deriveUnreadCount({ count: -1 })).toBe(0);
  });
});

describe('useUnreadCount', () => {
  it('polls every 60s and targets the unread-count endpoint', () => {
    renderHook(() => useUnreadCount());

    const [key, options] = useSWRMock.mock.calls[0];
    expect(key).toEqual([endpoints.unreadCount, 'tenant-123']);
    expect(options.refreshInterval).toBe(60000);
  });

  it('derives unreadCount from the SWR data', () => {
    useSWRMock.mockReturnValue({ data: { data: { count: 7 } }, isLoading: false, error: null, mutate: vi.fn() });

    const { result } = renderHook(() => useUnreadCount());
    expect(result.current.unreadCount).toBe(7);
  });
});

describe('useGetNotifications', () => {
  it('does NOT poll (no refreshInterval on the list)', () => {
    renderHook(() => useGetNotifications({ enabled: true }));

    const [, options] = useSWRMock.mock.calls[0];
    expect(options.refreshInterval).toBeUndefined();
  });

  it('passes a null key when disabled so SWR skips the request', () => {
    renderHook(() => useGetNotifications({ enabled: false }));

    const [key] = useSWRMock.mock.calls[0];
    expect(key).toBeNull();
  });
});

describe('markNotificationRead', () => {
  it('returns 400 without calling the API for a missing id', async () => {
    const result = await markNotificationRead('');
    expect(result.success).toBe(false);
    expect(result.status).toBe(400);
    expect(api.post).not.toHaveBeenCalled();
  });

  it('POSTs to the read endpoint and revalidates on success', async () => {
    api.post.mockResolvedValue({ success: true, data: { id: 'n1', read_at: '2026-01-01T00:00:00Z' } });

    const result = await markNotificationRead('n1');

    expect(api.post).toHaveBeenCalledWith(endpoints.markRead('n1'));
    expect(result.success).toBe(true);
    expect(revalidateByPrefix).toHaveBeenCalledWith('/notifications/');
  });

  it('surfaces the error shape on failure without revalidating', async () => {
    api.post.mockResolvedValue({ success: false, error: 'Not found', status: 404 });

    const result = await markNotificationRead('n1');

    expect(result.success).toBe(false);
    expect(result.status).toBe(404);
    expect(revalidateByPrefix).not.toHaveBeenCalled();
  });
});
