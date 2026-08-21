// frontend/src/api/objectives/objectives.js
//
// SWR data layer for the personal Objectives (backend module `quotas/`, endpoint
// /quotas/quotas/). Named `objectives` because that is what the product calls
// them; the backend module is `quotas` for historical reasons. The legacy
// api/quotas/quotas.js — which read the OLD end_users sales-quotas on the
// pre-Sprint-C rules — was deleted with the Home cards it fed.
//
// Mirrors api/territories/territories.js: a tenant-keyed SWR list hook plus
// create/update/delete async helpers that revalidate the list on success.

import useSWR from 'swr';
import { useMemo } from 'react';

import { useAuth } from 'hooks/useAuth';
import { api } from 'utils/axiosClient';
import { tenantKey, revalidateMultiple } from 'api/_swr';
import { isValidUUID } from 'utils/validators';

export const endpoints = {
  objectives: '/quotas/quotas/',
  objectiveDetail: (id) => `/quotas/quotas/${id}/`,
};

/**
 * useGetObjectives — the current user's objectives (scoped by tier on the
 * backend). `filters` is serialised INSIDE the useMemo so a fresh inline object
 * never re-triggers SWR (no refetch loop).
 */
export function useGetObjectives(options = {}) {
  const { tenantId } = useAuth();
  const { ordering = '', filters = {}, enabled = true } = options;

  const filtersKey = JSON.stringify(filters);

  const url = useMemo(() => {
    const params = new URLSearchParams();
    if (ordering) params.set('ordering', ordering);
    const f = JSON.parse(filtersKey);
    Object.entries(f).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') params.set(k, v);
    });
    const qs = params.toString();
    return qs ? `${endpoints.objectives}?${qs}` : endpoints.objectives;
  }, [ordering, filtersKey]);

  const swrKey = useMemo(
    () => (enabled ? tenantKey(url, tenantId) : null),
    [enabled, url, tenantId],
  );

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
  });

  return useMemo(
    () => ({
      objectives: data?.data?.results || data?.results || [],
      objectivesCount: data?.data?.count || data?.count || 0,
      objectivesLoading: isLoading,
      objectivesError: error,
      objectivesValidating: isValidating,
      mutateObjectives: mutate,
    }),
    [data, isLoading, error, isValidating, mutate],
  );
}

function _fail(result) {
  return {
    success: false,
    error: result?.error,
    status: result?.status || 0,
    response: result?.response || null,
  };
}

export async function createObjective(payload) {
  const result = await api.post(endpoints.objectives, payload);
  if (result.success) {
    revalidateMultiple([endpoints.objectives]);
    return { success: true, data: result.data };
  }
  return _fail(result);
}

export async function updateObjective(objectiveId, payload) {
  if (!objectiveId || !isValidUUID(objectiveId)) {
    return { success: false, error: 'Invalid objective ID format', status: 400 };
  }
  const result = await api.patch(endpoints.objectiveDetail(objectiveId), payload);
  if (result.success) {
    revalidateMultiple([endpoints.objectives]);
    return { success: true, data: result.data };
  }
  return _fail(result);
}

export async function deleteObjective(objectiveId) {
  if (!objectiveId || !isValidUUID(objectiveId)) {
    return { success: false, error: 'Invalid objective ID format', status: 400 };
  }
  const result = await api.delete(endpoints.objectiveDetail(objectiveId));
  if (result.success || result.status === 204) {
    revalidateMultiple([endpoints.objectives]);
    return { success: true, status: result.status ?? 204 };
  }
  return _fail(result);
}
