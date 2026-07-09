// frontend/src/api/notifications/notifications.js
/**
 * API hooks and mutations for the Notifications module.
 *
 * Connected to backend: app_modules/notifications/
 * All endpoints verified against app_modules/notifications/urls.py
 *
 * Freshness model:
 *   - useUnreadCount() polls (refreshInterval 60s) so the bell badge
 *     stays fresh without opening the menu.
 *   - useGetNotifications() does NOT poll — the paginated list is
 *     revalidated on demand (dropdown open / after mark-read).
 */

import useSWR from "swr";
import { useMemo } from "react";
import { useAuth } from "hooks/useAuth";
import { api } from "utils/axiosClient";
import { tenantKey, revalidateByPrefix } from "api/_swr";

// ==============================|| ENDPOINTS ||============================== //

export const endpoints = {
  list: "/notifications/",
  unreadCount: "/notifications/unread-count/",
  markRead: (id) => `/notifications/${id}/read/`,
};

// Prefix used to revalidate every notifications SWR key after a mutation.
const NOTIFICATIONS_PREFIX = "/notifications/";

// ==============================|| HELPERS ||============================== //

/**
 * Derive the unread count from a notifications-count response.
 * Tolerates both the wrapped `{ data: { count } }` shape and a bare
 * `{ count }` payload; defaults to 0 when absent.
 *
 * @param {Object} data - SWR data for the unread-count endpoint
 * @returns {number}
 */
export function deriveUnreadCount(data) {
  const count = data?.data?.count ?? data?.count;
  return typeof count === "number" && count > 0 ? count : 0;
}

// ==============================|| READ HOOKS ||============================== //

/**
 * GET NOTIFICATIONS - paginated list of the caller's notifications.
 * No polling: revalidated on demand when the dropdown opens.
 *
 * @param {Object} options - {enabled}
 */
export function useGetNotifications(options = {}) {
  const { tenantId } = useAuth();
  const { enabled = true } = options;

  const swrKey = useMemo(() => {
    if (!enabled) return null;
    return tenantKey(endpoints.list, tenantId);
  }, [enabled, tenantId]);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    dedupingInterval: 5000,
  });

  return useMemo(
    () => ({
      notifications: data?.data?.results || data?.results || [],
      totalCount: data?.data?.count || data?.count || 0,
      notificationsLoading: isLoading,
      notificationsError: error,
      notificationsValidating: isValidating,
      mutateNotifications: mutate,
    }),
    [data, isLoading, error, isValidating, mutate],
  );
}

/**
 * GET UNREAD COUNT - lightweight badge poll target (60s).
 * Mirrors the SWR options of useGetPlaylist (campaigns.js).
 */
export function useUnreadCount() {
  const { tenantId } = useAuth();

  const swrKey = useMemo(
    () => tenantKey(endpoints.unreadCount, tenantId),
    [tenantId],
  );

  const { data, isLoading, error, mutate } = useSWR(swrKey, {
    revalidateOnFocus: true,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
    dedupingInterval: 5000,
    refreshInterval: 60000,
  });

  return useMemo(
    () => ({
      unreadCount: deriveUnreadCount(data),
      unreadLoading: isLoading,
      unreadError: error,
      mutateUnreadCount: mutate,
    }),
    [data, isLoading, error, mutate],
  );
}

// ==============================|| MUTATION - MARK READ ||============================== //

/**
 * MARK NOTIFICATION READ
 * POST /notifications/{id}/read/
 *
 * @param {string} notificationId
 * @returns {{success: boolean, data?: Object, error?: string, status?: number}}
 */
export async function markNotificationRead(notificationId) {
  if (!notificationId) {
    return { success: false, error: "Invalid notification ID", status: 400 };
  }

  const result = await api.post(endpoints.markRead(notificationId));

  if (result.success || result.status === 200) {
    revalidateByPrefix(NOTIFICATIONS_PREFIX);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}
