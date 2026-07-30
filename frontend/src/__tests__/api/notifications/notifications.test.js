// frontend/src/__tests__/api/notifications/notifications.test.js

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, cleanup } from '@testing-library/react';

// ==============================|| MOCKS ||============================== //

// Capture the SWR options each hook passes so we can assert polling config.
const swrMock = vi.fn(() => ({ data: undefined, isLoading: false, error: null, mutate: vi.fn() }));
vi.mock('swr', () => ({ default: (key, options) => swrMock(key, options) }));

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
  respondToNotification,
  deriveUnreadCount,
  notificationHref,
  endpoints,
} from 'api/notifications/notifications';

// ==============================|| TESTS ||============================== //

beforeEach(() => {
  vi.clearAllMocks();
  swrMock.mockImplementation(() => ({ data: undefined, isLoading: false, error: null, mutate: vi.fn() }));
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

describe('notificationHref', () => {
  it('resolves a decision_cycle to the DC workspace URL', () => {
    const href = notificationHref({
      related_object_type: 'decision_cycle',
      payload: { account_id: 'acc-1', cycle_id: 'cyc-1' },
    });
    expect(href).toBe('/accounts/acc-1/dc/cyc-1');
  });

  it('resolves an activity to the activity URL', () => {
    const href = notificationHref({
      related_object_type: 'activity',
      payload: { activity_id: 'act-9' },
    });
    expect(href).toBe('/activities/act-9');
  });

  it('returns null for tech_stack_signal (not click-through)', () => {
    expect(
      notificationHref({ related_object_type: 'tech_stack_signal', payload: { tech_name: 'FooDB' } }),
    ).toBeNull();
  });

  it('returns null for an unknown type', () => {
    expect(notificationHref({ related_object_type: 'something_else', payload: {} })).toBeNull();
  });

  it('returns null when routing ids are missing', () => {
    expect(notificationHref({ related_object_type: 'decision_cycle', payload: { account_id: 'acc-1' } })).toBeNull();
    expect(notificationHref({ related_object_type: 'activity', payload: {} })).toBeNull();
    expect(notificationHref(null)).toBeNull();
  });
});

describe('useUnreadCount', () => {
  it('polls every 60s and targets the unread-count endpoint', () => {
    renderHook(() => useUnreadCount());

    const [key, options] = swrMock.mock.calls[0];
    expect(key).toEqual([endpoints.unreadCount, 'tenant-123']);
    expect(options.refreshInterval).toBe(60000);
  });

  it('derives unreadCount from the SWR data', () => {
    swrMock.mockReturnValue({ data: { data: { count: 7 } }, isLoading: false, error: null, mutate: vi.fn() });

    const { result } = renderHook(() => useUnreadCount());
    expect(result.current.unreadCount).toBe(7);
  });
});

describe('useGetNotifications', () => {
  it('does NOT poll (no refreshInterval on the list)', () => {
    renderHook(() => useGetNotifications({ enabled: true }));

    const [, options] = swrMock.mock.calls[0];
    expect(options.refreshInterval).toBeUndefined();
  });

  it('passes a null key when disabled so SWR skips the request', () => {
    renderHook(() => useGetNotifications({ enabled: false }));

    const [key] = swrMock.mock.calls[0];
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

describe('respondToNotification', () => {
  it('returns 400 without calling the API for a missing id', async () => {
    const result = await respondToNotification('', 'ACCEPTED');
    expect(result.success).toBe(false);
    expect(result.status).toBe(400);
    expect(api.post).not.toHaveBeenCalled();
  });

  it('POSTs the response_status body and revalidates on success', async () => {
    api.post.mockResolvedValue({ success: true, data: { id: 'n1', response_status: 'ACCEPTED' } });

    const result = await respondToNotification('n1', 'ACCEPTED');

    expect(api.post).toHaveBeenCalledWith(endpoints.respond('n1'), { response_status: 'ACCEPTED' });
    expect(result.success).toBe(true);
    expect(revalidateByPrefix).toHaveBeenCalledWith('/notifications/');
    // Accepting/declining changes the BI todo — the Home must refresh too.
    expect(revalidateByPrefix).toHaveBeenCalledWith('/bi/');
  });

  it('surfaces the error shape on failure without revalidating', async () => {
    api.post.mockResolvedValue({ success: false, error: 'Not actionable', status: 400 });

    const result = await respondToNotification('n1', 'DECLINED');

    expect(result.success).toBe(false);
    expect(result.status).toBe(400);
    expect(revalidateByPrefix).not.toHaveBeenCalled();
  });
});
