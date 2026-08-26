// frontend/src/api/signals/signalClusters.js
/**
 * API hooks and mutations for Signal Clusters.
 *
 * A cluster is NOT an ORM entity on the backend — it is a projection over
 * signals sharing the same canonical_key on a given account. The
 * backend exposes four endpoints at /module-signals/clusters/:
 *
 *   GET   /module-signals/clusters/                        → list
 *   GET   /module-signals/clusters/{canonical_key}/        → detail + members
 *   POST  /module-signals/clusters/archive/                → archive
 *   POST  /module-signals/clusters/unarchive/              → unarchive
 *
 * signalType is parameterized end-to-end so any supported cluster signal
 * type (pain / objective / impact) works without refactor.
 *
 * Follows the URL-building, revalidation, and mutation-return-shape
 * pattern shared by the other api/signals modules.
 *
 * Cache invalidation strategy
 * ---------------------------
 * Writes on a cluster's archival state do NOT change the underlying
 * signals — they only change which archival rows are "active".
 * However, writes on signals DO change the cluster payload
 * (confirmation_count, freshness, etc.), so the per-type signal modules
 * already revalidate their cache tag. We complete the picture here by also
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
};

// ==============================|| URL BUILDER ||============================== //

/**
 * Normalise a signal_type input (string | string[]) to the CSV form
 * expected by the backend (`pain` or `pain,objective`).
 *
 * Returns null/empty input as-is so the caller can decide whether to
 * append the param at all.
 *
 *   normaliseSignalType('pain')                   → 'pain'
 *   normaliseSignalType(['pain'])                 → 'pain'
 *   normaliseSignalType(['pain', 'objective'])    → 'pain,objective'
 *   normaliseSignalType([])                       → null
 *   normaliseSignalType(null | undefined | '')    → null
 *
 * Empty tokens (e.g. ['pain', ''] or 'pain,,') are dropped silently —
 * the backend treats them the same and a missing token carries no intent.
 *
 * @param {string|string[]|null|undefined} input
 * @returns {string|null}
 */
function normaliseSignalType(input) {
  if (input == null || input === "") return null;

  if (Array.isArray(input)) {
    const cleaned = input
      .map((t) => (t == null ? "" : String(t).trim()))
      .filter(Boolean);
    if (cleaned.length === 0) return null;
    return cleaned.join(",");
  }

  const trimmed = String(input).trim();
  return trimmed || null;
}

/**
 * Build the cluster list URL with query params.
 *
 * Supported params (aligned with backend SignalClusterListView):
 *   - account           (UUID, required)
 *   - signal_type       (string CSV — default 'pain' applied by callers)
 *   - decision_cycle    (UUID, optional)
 *   - include_archived  (bool, default false)
 *
 * `signalType` may be a single value ('pain') or an array
 * (['pain', 'objective']). Arrays are serialised as a comma-separated
 * list — the backend's _parse_signal_type accepts that form for the
 * list endpoint.
 *
 * @param {string} baseUrl
 * @param {Object} params
 * @returns {string}
 */
function buildListUrl(baseUrl, params = {}) {
  const {
    accountId,
    signalType,
    decisionCycleId,
    includeArchived,
    department,
    contact,
    scope,
    statuses,
    perimeter,
    whats,
    dimensions,
    contacts,
  } = params;

  const query = new URLSearchParams();

  if (accountId) {
    query.append("account", accountId);
  }

  // signalType arrives already normalised by the caller (the hook calls
  // normaliseSignalType before passing). Defensive normalisation here is
  // cheap and keeps the builder robust against direct callers.
  const normalisedType = normaliseSignalType(signalType);
  if (normalisedType) {
    query.append("signal_type", normalisedType);
  }

  if (decisionCycleId) {
    query.append("decision_cycle", decisionCycleId);
  }
  if (includeArchived) {
    query.append("include_archived", "true");
  }

  // Member filters (mirror the aggregated endpoint's semantics on the backend
  // cluster endpoint). `department` is a repeatable param — accept a single id
  // (the flat drawer's single-select) or an array; `status` is repeatable too.
  const departmentList = Array.isArray(department)
    ? department
    : department
      ? [department]
      : [];
  departmentList.forEach((d) => {
    if (d != null && d !== "") query.append("department", d);
  });
  if (contact) {
    query.append("contact", contact);
  }
  if (scope) {
    query.append("scope", scope);
  }
  (statuses || []).forEach((s) => {
    if (s) query.append("status", s);
  });

  // Grouped (unified) filters — perimeter (OR: 'BUSINESS' sentinel + dept ids),
  // domain (`what`), dimension, and multi-contact. Each is a repeatable param.
  (perimeter || []).forEach((p) => {
    if (p != null && p !== "") query.append("perimeter", p);
  });
  (whats || []).forEach((w) => {
    if (w) query.append("what", w);
  });
  (dimensions || []).forEach((d) => {
    if (d) query.append("dimension", d);
  });
  (contacts || []).forEach((c) => {
    if (c) query.append("contact", c);
  });

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
 * The cluster payload is derived from Pain signals + Impact signals + the
 * archival table. Writes on any of those should bust the cluster cache,
 * and writes on the cluster archival table should bust the Pain cache to
 * keep its detail views consistent (same cache tag on the backend —
 * 'signals').
 */
function revalidateClusterCaches() {
  revalidateMultiple([
    endpoints.list,
    endpoints.painList,
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
 * signalType polymorphism
 * -----------------------
 * `options.signalType` accepts either:
 *   - a single string ('pain')                         → most callers
 *   - an array of strings (['pain', 'objective'])      → Qualification tab
 *
 * Arrays are serialised as CSV in the URL (`signal_type=pain,objective`)
 * — the backend's _parse_signal_type accepts that form for list calls.
 *
 * Cache key stability
 * -------------------
 * The hook normalises signalType to a stable CSV string before computing
 * the SWR key. Identical inputs (whether passed as a string or an array)
 * therefore produce the same cache entry — no spurious refetches when a
 * caller passes a fresh array instance on each render.
 *
 * @param {string} accountId - Account UUID (required for fetch to run)
 * @param {Object} [options]
 * @param {string|string[]} [options.signalType='pain']
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
    department = null,
    contact = null,
    scope = null,
    statuses = null,
    perimeter = null,
    whats = null,
    dimensions = null,
    contacts = null,
  } = options;

  const enabled = Boolean(accountId && isValidUUID(accountId));

  // Stable CSV keys for the array/scalar member filters so a fresh array
  // instance per render does not thrash the SWR cache key.
  const departmentKey = Array.isArray(department)
    ? department.join(",")
    : department || "";
  const statusesKey = (statuses || []).join(",");
  const perimeterKey = (perimeter || []).join(",");
  const whatsKey = (whats || []).join(",");
  const dimensionsKey = (dimensions || []).join(",");
  const contactsKey = (contacts || []).join(",");

  // Normalise signalType to a stable CSV string.
  //
  // This serves two purposes:
  //   1. Single source of truth for the URL builder AND for the memo
  //      dependency list — guarantees identical inputs (string 'pain' vs
  //      array ['pain']) hit the same SWR cache entry.
  //   2. Avoids referential instability when the caller passes a fresh
  //      array on each render (e.g. `signalType={[type]}`).
  //
  // Falls back to 'pain' (the documented default) when the input
  // normalises to null — preserves the previous default behaviour.
  const normalisedSignalType = useMemo(
    () => normaliseSignalType(signalType) ?? "pain",
    [signalType],
  );

  const urlWithParams = useMemo(
    () =>
      enabled
        ? buildListUrl(endpoints.list, {
            accountId,
            signalType: normalisedSignalType,
            decisionCycleId,
            includeArchived,
            department,
            contact,
            scope,
            statuses,
            perimeter,
            whats,
            dimensions,
            contacts,
          })
        : null,
    // The array filters use their stable CSV keys as deps (the array
    // instances themselves are referentially unstable across renders).
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      enabled,
      accountId,
      normalisedSignalType,
      decisionCycleId,
      includeArchived,
      departmentKey,
      contact,
      scope,
      statusesKey,
      perimeterKey,
      whatsKey,
      dimensionsKey,
      contactsKey,
    ],
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
