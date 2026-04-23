// frontend/src/api/signals/signalClusters.js
/**
 * API hooks and mutations for Signal Clusters.
 *
 * A cluster is NOT an ORM entity on the backend — it is a projection over
 * signals sharing the same canonical_key on a given account. Sprint 2
 * backend exposes four endpoints at /module-signals/clusters/:
 *
 *   GET   /module-signals/clusters/                        → list
 *   GET   /module-signals/clusters/{canonical_key}/        → detail + members
 *   POST  /module-signals/clusters/archive/                → archive
 *   POST  /module-signals/clusters/unarchive/              → unarchive
 *
 * Sprint 3 covers Pain clusters only. Other signal types may ship in
 * later sprints — signalType is parameterized end-to-end to keep that
 * path open without refactor.
 *
 * Follows the pattern established by api/signals/painImpacts.js (the
 * most recent module) for URL building, revalidation, and mutation
 * return shape.
 *
 * Cache invalidation strategy
 * ---------------------------
 * Writes on a cluster's archival state do NOT change the underlying
 * signals or impacts — they only change which archival rows are "active".
 * However, writes on signals or impacts DO change the cluster payload
 * (confirmation_count, freshness, etc.), so painImpacts.js already
 * revalidates the pain cache tag. We complete the picture here by also
 * revalidating the clusters cache whenever an archive/unarchive happens.
 */

import useSWR from "swr";
import { useMemo } from "react";

import { useAuth } from "hooks/useAuth";
import { api } from "utils/axiosClient";
import { tenantKey, revalidateMultiple } from "api/_swr";
import { isValidUUID } from "utils/validators";

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  list: "/module-signals/clusters/",
  // Path-param endpoint — canonical_key may contain ':' (e.g. 'pain:OPS:TIME').
  // Backend route uses Django's <path:> converter which accepts unencoded
  // colons; we encode nonetheless for URL safety on the client side and for
  // any intermediate proxy that might be strict.
  detail: (canonicalKey) =>
    `/module-signals/clusters/${encodeURIComponent(canonicalKey)}/`,
  archive: "/module-signals/clusters/archive/",
  unarchive: "/module-signals/clusters/unarchive/",

  // Sibling caches — kept here so revalidateClusterCaches() stays
  // self-documenting. Any write that changes cluster data must revalidate
  // these prefixes as well.
  painList: "/module-signals/pain/",
  painImpactList: "/module-signals/pain-impacts/",
};

// ==============================|| URL BUILDER ||============================== //

/**
 * Build the cluster list URL with query params.
 *
 * Supported params (aligned with backend SignalClusterListView):
 *   - account           (UUID, required)
 *   - signal_type       (default 'pain')
 *   - decision_cycle    (UUID, optional)
 *   - include_archived  (bool, default false)
 *
 * @param {string} baseUrl
 * @param {Object} params
 * @returns {string}
 */
function buildListUrl(baseUrl, params = {}) {
  const { accountId, signalType, decisionCycleId, includeArchived } = params;

  const query = new URLSearchParams();

  if (accountId) {
    query.append("account", accountId);
  }
  if (signalType) {
    query.append("signal_type", signalType);
  }
  if (decisionCycleId) {
    query.append("decision_cycle", decisionCycleId);
  }
  if (includeArchived) {
    query.append("include_archived", "true");
  }

  const qs = query.toString();
  return qs ? `${baseUrl}?${qs}` : baseUrl;
}

/**
 * Build the cluster detail URL with required `account` query param.
 *
 * @param {string} canonicalKey
 * @param {string} accountId
 * @param {string} [signalType='pain']
 * @returns {string}
 */
function buildDetailUrl(canonicalKey, accountId, signalType = "pain") {
  const query = new URLSearchParams({
    account: accountId,
    signal_type: signalType,
  });
  return `${endpoints.detail(canonicalKey)}?${query.toString()}`;
}

// ==============================|| REVALIDATION ||============================== //

/**
 * Revalidate all caches that depend on cluster data.
 *
 * The cluster payload is derived from Pain signals + PainImpacts + the
 * archival table. Writes on any of those should bust the cluster cache,
 * and writes on the cluster archival table should bust the Pain/Impact
 * caches to keep their detail views consistent (same cache tag on the
 * backend — 'signals').
 */
function revalidateClusterCaches() {
  revalidateMultiple([
    endpoints.list,
    endpoints.painList,
    endpoints.painImpactList,
  ]);
}

// ==============================|| LIST HOOK ||============================== //

/**
 * GET CLUSTERS BY ACCOUNT
 *
 * Fetches the cluster list for an account, optionally filtered by
 * signal_type, decision_cycle, and archival state.
 *
 * The hook returns `null` SWR key (no fetch) when accountId is invalid,
 * which lets callers render loading/empty states without spurious
 * network calls.
 *
 * @param {string} accountId - Account UUID (required for fetch to run)
 * @param {Object} [options]
 * @param {string} [options.signalType='pain']
 * @param {string} [options.decisionCycleId]
 * @param {boolean} [options.includeArchived=false]
 * @returns {Object} { clusters, clustersCount, clustersLoading,
 *                     clustersError, clustersValidating, clustersEmpty,
 *                     mutateClusters }
 */
export function useGetClustersByAccount(accountId, options = {}) {
  const { tenantId } = useAuth();

  const {
    signalType = "pain",
    decisionCycleId = null,
    includeArchived = false,
  } = options;

  const enabled = Boolean(accountId && isValidUUID(accountId));

  const urlWithParams = useMemo(
    () =>
      enabled
        ? buildListUrl(endpoints.list, {
            accountId,
            signalType,
            decisionCycleId,
            includeArchived,
          })
        : null,
    [enabled, accountId, signalType, decisionCycleId, includeArchived],
  );

  const swrKey = tenantKey(urlWithParams, tenantId);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  return useMemo(() => {
    // Backend returns { success: true, data: [...] } — no pagination wrapper.
    // Some older callsites wrap everything under data.data; we handle both.
    const clusters = data?.data ?? data?.results ?? [];

    return {
      clusters: Array.isArray(clusters) ? clusters : [],
      clustersCount: Array.isArray(clusters) ? clusters.length : 0,
      clustersLoading: enabled ? isLoading : false,
      clustersError: error,
      clustersValidating: isValidating,
      clustersEmpty:
        !isLoading && !(Array.isArray(clusters) && clusters.length),
      mutateClusters: mutate,
    };
  }, [data, isLoading, error, isValidating, mutate, enabled]);
}

// ==============================|| DETAIL HOOK ||============================== //

/**
 * GET CLUSTER DETAIL
 *
 * Fetches a single cluster with its member signals (PainSignals with
 * nested impacts, per PainSignalDetailSerializer on the backend).
 *
 * Both `accountId` and `canonicalKey` must be present for the fetch to
 * run. The hook returns null SWR key otherwise.
 *
 * @param {string} accountId - Account UUID
 * @param {string} canonicalKey - Cluster identifier (e.g. 'pain:OPS:TIME')
 * @param {Object} [options]
 * @param {string} [options.signalType='pain']
 * @returns {Object} { cluster, clusterLoading, clusterError,
 *                     clusterValidating, mutateCluster }
 */
export function useGetClusterDetail(accountId, canonicalKey, options = {}) {
  const { tenantId } = useAuth();
  const { signalType = "pain" } = options;

  const enabled = Boolean(
    accountId && isValidUUID(accountId) && canonicalKey && canonicalKey.trim(),
  );

  const urlWithParams = useMemo(
    () =>
      enabled ? buildDetailUrl(canonicalKey, accountId, signalType) : null,
    [enabled, canonicalKey, accountId, signalType],
  );

  const swrKey = tenantKey(urlWithParams, tenantId);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  return useMemo(
    () => ({
      // Backend returns { success: true, data: { ...cluster, members: [...] } }
      cluster: data?.data ?? data ?? null,
      clusterLoading: enabled ? isLoading : false,
      clusterError: error,
      clusterValidating: isValidating,
      mutateCluster: mutate,
    }),
    [data, isLoading, error, isValidating, mutate, enabled],
  );
}

// ==============================|| MUTATIONS ||============================== //

/**
 * ARCHIVE CLUSTER
 *
 * POST /module-signals/clusters/archive/
 * Body: { account, canonical_key, signal_type }
 *
 * @param {Object} params
 * @param {string} params.account        - Account UUID
 * @param {string} params.canonicalKey   - Cluster identifier
 * @param {string} [params.signalType='pain']
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function archiveCluster({
  account,
  canonicalKey,
  signalType = "pain",
}) {
  if (!account || !isValidUUID(account)) {
    return { success: false, error: "Invalid account ID format", status: 400 };
  }
  if (!canonicalKey || !String(canonicalKey).trim()) {
    return { success: false, error: "Invalid canonical key", status: 400 };
  }

  const result = await api.post(endpoints.archive, {
    account,
    canonical_key: canonicalKey,
    signal_type: signalType,
  });

  if (result.success) {
    revalidateClusterCaches();
    const data = result.data?.data ?? result.data;
    return { success: true, data };
  }

  return {
    success: false,
    error: result.error,
    status: result.status ?? 0,
    response: result.response ?? null,
  };
}

/**
 * UNARCHIVE CLUSTER
 *
 * POST /module-signals/clusters/unarchive/
 * Body: { account, canonical_key, signal_type }
 *
 * @param {Object} params
 * @param {string} params.account
 * @param {string} params.canonicalKey
 * @param {string} [params.signalType='pain']
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function unarchiveCluster({
  account,
  canonicalKey,
  signalType = "pain",
}) {
  if (!account || !isValidUUID(account)) {
    return { success: false, error: "Invalid account ID format", status: 400 };
  }
  if (!canonicalKey || !String(canonicalKey).trim()) {
    return { success: false, error: "Invalid canonical key", status: 400 };
  }

  const result = await api.post(endpoints.unarchive, {
    account,
    canonical_key: canonicalKey,
    signal_type: signalType,
  });

  if (result.success) {
    revalidateClusterCaches();
    const data = result.data?.data ?? result.data;
    return { success: true, data };
  }

  return {
    success: false,
    error: result.error,
    status: result.status ?? 0,
    response: result.response ?? null,
  };
}
