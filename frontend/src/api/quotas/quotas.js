// frontend/src/api/quotas/quotas.js

import { useMemo } from 'react';
import useSWR from 'swr';

import { useAuth } from 'hooks/useAuth';
import { tenantKey } from 'api/_swr';

// ==============================|| SALES QUOTA API ||============================== //

export const endpoints = {
  // The backend list already defaults active_only=true; current_period=true
  // restricts to the quota window in effect now.
  myActiveQuotas: '/client/sales-quotas/my-quotas/?current_period=true',
};

/**
 * useGetMyActiveQuotas — the current rep's active, in-period quota(s).
 *
 * A rep may legitimately have more than one (by target_type), so this returns a
 * list. Used by the Rep Home "Where I am" block to resolve quota_ids for the
 * quota_attainment KPI.
 */
export function useGetMyActiveQuotas(options = {}) {
  const { tenantId } = useAuth();
  const { enabled = true } = options;

  const swrKey = useMemo(
    () => (enabled ? tenantKey(endpoints.myActiveQuotas, tenantId) : null),
    [enabled, tenantId],
  );

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    dedupingInterval: 5000,
  });

  return useMemo(
    () => ({
      quotas: data?.data?.results || data?.results || [],
      quotasCount: data?.data?.count || data?.count || 0,
      quotasLoading: isLoading,
      quotasError: error,
      quotasValidating: isValidating,
      mutateQuotas: mutate,
    }),
    [data, isLoading, error, isValidating, mutate],
  );
}
