// frontend/src/api/signals/painImpacts.js
/**
 * API hooks and mutations for the PainImpact module.
 *
 * PainImpact is the "evidence" side of the Pain/Impact split:
 *   - A Pain captures the qualitative diagnosis (what × dimension).
 *   - PainImpacts capture tangible proof — metrics, departments, humans.
 *
 * Single endpoint group (no signal_type routing here — Impacts have no
 * polymorphism):
 *   /module-signals/pain-impacts/
 *
 * Unlike signals, PainImpact has NO lifecycle:
 *   - no status (PENDING / VALIDATED / REJECTED)
 *   - no validate / reject actions
 *   - plain CRUD only
 *
 * Follows the same patterns as api/accounts/signals.js for consistency.
 *
 * Cache invalidation note:
 *   Every PainImpact write revalidates BOTH the pain-impacts list caches
 *   AND the pain-signals list caches — because PainSignal list/detail
 *   serializers nest `impacts` inline. Missing that would leave the nested
 *   list stale after an impact write.
 */

import useSWR from "swr";
import { useMemo } from "react";

import { useAuth } from "hooks/useAuth";
import { api } from "utils/axiosClient";
import { tenantKey, revalidateMultiple } from "api/_swr";
import { isValidUUID } from "utils/validators";

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  list: "/module-signals/pain-impacts/",
  detail: (id) => `/module-signals/pain-impacts/${id}/`,
  // pain signal endpoints — needed for cross-cache revalidation after write
  painList: "/module-signals/pain/",
};

// ==============================|| URL BUILDER ||============================== //

/**
 * Build a list URL with query params for server-side filtering.
 *
 * Supported filters (must match PainImpactFilter on the backend):
 *   pain_signal_id     — UUID of a parent pain
 *   account_id         — UUID of the account (filters via pain_signal__account)
 *   level              — BUSINESS | DEPARTMENT | PERSONAL
 *   human_impact       — FRUSTRATION | OVERLOAD | STRESS | DEMOTIVATION | CONFLICT
 *   impacted_department_id
 *   impacted_contact_id
 *
 * @param {string} baseUrl
 * @param {Object} params - { page, pageSize, search, ordering, filters }
 * @returns {string}
 */
function buildUrlWithParams(baseUrl, params = {}) {
  const { page, pageSize, search, ordering, filters = {} } = params;

  const query = new URLSearchParams();

  if (page !== undefined && page !== null) {
    query.append("page", page);
  }
  if (pageSize !== undefined && pageSize !== null) {
    query.append("page_size", pageSize);
  }
  if (search) {
    query.append("search", search);
  }
  if (ordering) {
    query.append("ordering", ordering);
  }

  // --- impact-specific filters ---
  if (filters.pain_signal_id) {
    query.append("pain_signal", filters.pain_signal_id);
  }
  if (filters.account_id) {
    query.append("account", filters.account_id);
  }
  if (filters.level) {
    query.append("level", filters.level);
  }
  if (filters.human_impact) {
    query.append("human_impact", filters.human_impact);
  }
  if (filters.impacted_department_id) {
    query.append("impacted_department", filters.impacted_department_id);
  }
  if (filters.impacted_contact_id) {
    query.append("impacted_contact", filters.impacted_contact_id);
  }

  const qs = query.toString();
  return qs ? `${baseUrl}?${qs}` : baseUrl;
}

// ==============================|| REVALIDATION ||============================== //

/**
 * Revalidate caches that depend on PainImpact data.
 *
 * Must include:
 *   - pain-impacts lists (direct endpoint)
 *   - pain-signals lists (nested `impacts` array in list serializer)
 *
 * Both revalidations use prefix matching — any variant with query params
 * gets picked up.
 */
function revalidatePainImpactCaches() {
  revalidateMultiple([endpoints.list, endpoints.painList]);
}

// ==============================|| BASE HOOK ||============================== //

/**
 * Generic SWR hook for the PainImpact list endpoint.
 * Not exported — callers use the public convenience hooks below.
 *
 * @param {Object} options - { page, pageSize, search, ordering, filters, enabled }
 * @returns {Object} { impacts, impactsCount, impactsLoading, impactsError,
 *                     impactsValidating, impactsEmpty, mutateImpacts }
 */
function useGetPainImpacts(options = {}) {
  const { tenantId } = useAuth();
  const {
    page = 1,
    pageSize = 50,
    search = "",
    ordering = "-created_at",
    filters = {},
    enabled = true,
  } = options;

  const urlWithParams = useMemo(
    () =>
      enabled
        ? buildUrlWithParams(endpoints.list, {
            page,
            pageSize,
            search,
            ordering,
            filters,
          })
        : null,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [enabled, page, pageSize, search, ordering, JSON.stringify(filters)],
  );

  const swrKey = tenantKey(urlWithParams, tenantId);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  return useMemo(
    () => ({
      impacts: data?.data?.results ?? data?.results ?? [],
      impactsCount: data?.data?.count ?? data?.count ?? 0,
      impactsLoading: isLoading,
      impactsError: error,
      impactsValidating: isValidating,
      impactsEmpty:
        !isLoading && !(data?.data?.results?.length ?? data?.results?.length),
      mutateImpacts: mutate,
    }),
    [data, isLoading, error, isValidating, mutate],
  );
}

// ==============================|| PUBLIC HOOKS ||============================== //

/**
 * GET IMPACTS BY PAIN
 *
 * Fetches all impacts attached to a specific pain signal.
 *
 * Mostly redundant with PainSignal's nested `impacts` field, but useful
 * when the UI needs richer pagination / filtering than the nested payload
 * provides (e.g. "show only PERSONAL impacts of this pain").
 *
 * @param {string} painId  - PainSignal UUID
 * @param {Object} options - { page, pageSize, search, ordering, filters }
 * @returns {Object} same shape as useGetPainImpacts
 */
export function useGetPainImpactsByPain(painId, options = {}) {
  const enabled = Boolean(painId && isValidUUID(painId));

  const mergedOptions = useMemo(
    () => ({
      ...options,
      enabled,
      filters: {
        ...options.filters,
        pain_signal_id: enabled ? painId : undefined,
      },
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [painId, enabled, JSON.stringify(options)],
  );

  return useGetPainImpacts(mergedOptions);
}

/**
 * GET IMPACTS BY ACCOUNT
 *
 * Fetches all PainImpacts across all pains of an account.
 *
 * Filters via `pain_signal__account` on the backend (double-hop join) —
 * useful for aggregated views that don't care about the specific pain,
 * e.g. "all PERSONAL impacts on Acme Corp this quarter".
 *
 * @param {string} accountId - Account UUID
 * @param {Object} options   - { page, pageSize, search, ordering, filters }
 * @returns {Object} same shape as useGetPainImpacts
 */
export function useGetPainImpactsByAccount(accountId, options = {}) {
  const enabled = Boolean(accountId && isValidUUID(accountId));

  const mergedOptions = useMemo(
    () => ({
      ...options,
      enabled,
      filters: {
        ...options.filters,
        account_id: enabled ? accountId : undefined,
      },
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [accountId, enabled, JSON.stringify(options)],
  );

  return useGetPainImpacts(mergedOptions);
}

// ==============================|| MUTATIONS ||============================== //

/**
 * CREATE PAIN IMPACT
 *
 * POST /module-signals/pain-impacts/
 *
 * Required payload:
 *   - pain_signal : UUID of the parent pain
 *   - level       : 'BUSINESS' | 'DEPARTMENT' | 'PERSONAL'
 *
 * Level-conditional required fields:
 *   - DEPARTMENT → impacted_department
 *   - PERSONAL   → impacted_contact (must belong to the same account as pain)
 *
 * Optional fields:
 *   - human_impact (PERSONAL only)
 *   - metric       (free text)
 *   - notes        (free text)
 *
 * @param {Object} payload
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function createPainImpact(payload) {
  const result = await api.post(endpoints.list, payload);

  if (result.success) {
    revalidatePainImpactCaches();
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
 * UPDATE PAIN IMPACT (PATCH)
 *
 * PATCH /module-signals/pain-impacts/{id}/
 *
 * Merged-state validation on the backend: when changing `level`, the
 * caller MUST also send the level-appropriate field values. Example:
 *   { level: "PERSONAL" }               → rejected if instance has
 *                                           impacted_department set
 *   { level: "PERSONAL",
 *     impacted_department: null,
 *     impacted_contact: <uuid> }        → accepted
 *
 * @param {string} impactId
 * @param {Object} payload
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function updatePainImpact(impactId, payload) {
  if (!impactId || !isValidUUID(impactId)) {
    return { success: false, error: "Invalid impact ID format", status: 400 };
  }

  const url = endpoints.detail(impactId);
  const result = await api.patch(url, payload);

  if (result.success) {
    revalidatePainImpactCaches();
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
 * DELETE PAIN IMPACT
 *
 * DELETE /module-signals/pain-impacts/{id}/
 *
 * Hard delete — an impact has no lifecycle and no audit trail of its own.
 * If granular restore is ever needed, we'd introduce a soft-delete pattern;
 * until then, a deleted impact is gone for good.
 *
 * @param {string} impactId
 * @returns {Promise<{success: boolean, status?: number, error?: string}>}
 */
export async function deletePainImpact(impactId) {
  if (!impactId || !isValidUUID(impactId)) {
    return { success: false, error: "Invalid impact ID format", status: 400 };
  }

  const url = endpoints.detail(impactId);
  const result = await api.delete(url);

  if (result.success || result.status === 204) {
    revalidatePainImpactCaches();
    return { success: true, status: result.status ?? 204 };
  }

  return {
    success: false,
    error: result.error,
    status: result.status ?? 0,
    response: result.response ?? null,
  };
}
