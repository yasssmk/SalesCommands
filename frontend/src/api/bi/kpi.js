// frontend/src/api/bi/kpi.js

import { useMemo } from 'react';
import useSWR from 'swr';

import { useAuth } from 'hooks/useAuth';
import { api } from 'utils/axiosClient';
import { tenantKey } from 'api/_swr';

// ==============================|| BI KPI API ||============================== //

export const endpoints = {
  kpi: (key) => `/bi/kpi/${key}/`,
  batch: '/bi/kpi/batch/',
};

// The backend caps a single batch at this many requests. We chunk client-side
// so a rep with many entities never breaks their Home — the batch is a
// transport optimisation, not a semantic unit.
export const BATCH_CAP = 20;

/**
 * Build the detail URL for one KPI. Any key in `params` that is not a reserved
 * endpoint control (scope / period) is forwarded as a KPI compute_fn param
 * (cycle_id, campaign_id, territory_id, quota_id, ...).
 */
export function buildKpiUrl(key, { scope, period, params } = {}) {
  const qs = new URLSearchParams();
  if (scope) qs.append('scope', scope);
  if (period) qs.append('period', period);
  if (params && typeof params === 'object') {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') qs.append(k, v);
    });
  }
  const q = qs.toString();
  return q ? `${endpoints.kpi(key)}?${q}` : endpoints.kpi(key);
}

export function chunk(arr, size) {
  const out = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}

/**
 * useKpi — one KPI via GET /bi/kpi/<key>/.
 *
 * @param {string} key - registered KPI key
 * @param {Object} options - { scope, period, params, enabled }
 */
export function useKpi(key, options = {}) {
  const { tenantId } = useAuth();
  const { scope, period, params, enabled = true } = options;
  const paramsSig = JSON.stringify(params || null);

  const url = useMemo(
    () => (key ? buildKpiUrl(key, { scope, period, params }) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [key, scope, period, paramsSig],
  );

  const swrKey = useMemo(
    () => (enabled && key ? tenantKey(url, tenantId) : null),
    [enabled, key, url, tenantId],
  );

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    dedupingInterval: 5000,
  });

  return useMemo(
    () => ({
      kpi: data?.data || null,
      kpiLoading: isLoading,
      kpiError: error,
      kpiValidating: isValidating,
      mutateKpi: mutate,
    }),
    [data, isLoading, error, isValidating, mutate],
  );
}

/**
 * Batch fetcher — chunks at BATCH_CAP, fires one POST per chunk, and
 * concatenates results IN ORDER so a caller can zip results to requests by
 * index (results[i] <-> requests[i]).
 */
export async function batchFetcher(requests) {
  const chunks = chunk(requests, BATCH_CAP);
  const responses = await Promise.all(
    chunks.map((c) => api.post(endpoints.batch, { requests: c })),
  );

  const results = [];
  responses.forEach((res) => {
    if (!res || res.success === false) {
      throw new Error(res?.error || 'BI batch request failed');
    }
    const body = res.data;
    const chunkResults = body?.data?.results || body?.results || [];
    results.push(...chunkResults);
  });
  return results;
}

/**
 * useKpiBatch — N KPIs in one round-trip (chunked at BATCH_CAP under the hood).
 *
 * @param {Array} requests - [{ key, scope?, period?, params? }, ...]
 * @param {Object} options - { enabled }
 * @returns results in request order (results[i] corresponds to requests[i]).
 */
export function useKpiBatch(requests, options = {}) {
  const { tenantId } = useAuth();
  const { enabled = true } = options;
  const list = Array.isArray(requests) ? requests : [];
  const sig = JSON.stringify(list);

  const swrKey = useMemo(
    () => (enabled && tenantId && list.length ? [endpoints.batch, tenantId, sig] : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [enabled, tenantId, sig],
  );

  const { data, isLoading, error, isValidating, mutate } = useSWR(
    swrKey,
    () => batchFetcher(list),
    { revalidateOnFocus: false, revalidateOnReconnect: false, dedupingInterval: 5000 },
  );

  return useMemo(
    () => ({
      results: data || [],
      resultsLoading: isLoading,
      resultsError: error,
      resultsValidating: isValidating,
      mutateResults: mutate,
    }),
    [data, isLoading, error, isValidating, mutate],
  );
}
