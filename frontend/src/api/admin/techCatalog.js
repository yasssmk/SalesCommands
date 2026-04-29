// frontend/src/api/admin/techCatalog.js
/**
 * API hooks and mutations for the TechCatalog module.
 *
 * The TechCatalog is a tenant-level master list of products that the
 * sales organization needs to recognize on prospect accounts. It is
 * curated by tenant admins and consumed read-only by sales-side modules
 * downstream (Decision Cycle, Product, signals).
 *
 * Endpoint group (single, flat):
 *   /tech-catalog/
 *
 * Mounted in salescommands/urls.py — no `module-` prefix here, the
 * catalog stays under a short root path because it is used across
 * multiple consumer modules.
 *
 * Patterns:
 *   - SWR hooks for reads, with tenantKey() for multi-tenant isolation
 *   - Mutations call api.post/patch/delete and revalidate the list
 *     prefix on success so cached pages reflect the new state
 *   - All mutations validate the UUID format before hitting the network
 *   - Result objects always carry { success, data?, error?, status }
 *
 * Cache invalidation:
 *   Every successful write revalidates the list endpoint prefix. The
 *   detail endpoint isn't pre-emptively revalidated — SWR will refetch
 *   the detail page only when re-rendered, which is the right tradeoff
 *   for a small reference catalog.
 */

import useSWR from "swr";
import { useMemo } from "react";

import { useAuth } from "hooks/useAuth";
import { api } from "utils/axiosClient";
import { tenantKey, revalidateMultiple } from "api/_swr";
import { isValidUUID } from "utils/validators";

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  list: "/tech-catalog/",
  detail: (id) => `/tech-catalog/${id}/`,
};

// ==============================|| URL BUILDER ||============================== //

/**
 * Build a list URL with query params for server-side pagination,
 * search and ordering.
 *
 * Supported params:
 *   - page, pageSize → standard DRF pagination
 *   - search         → matches against company_name and product_name
 *                      (server-side, see TechCatalogViewSet.search_fields)
 *   - ordering       → e.g. "-updated_at", "company_name", "-product_name"
 *
 * No structured filters — the catalog has no advanced filter surface
 * yet. If filtering becomes necessary later, add a `filters` param here
 * and a corresponding TechCatalogFilter on the backend.
 *
 * @param {string} baseUrl
 * @param {Object} params
 * @returns {string}
 */
function buildUrlWithParams(baseUrl, params = {}) {
  const { page, pageSize, search, ordering } = params;

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

  const qs = query.toString();
  return qs ? `${baseUrl}?${qs}` : baseUrl;
}

// ==============================|| REVALIDATION ||============================== //

/**
 * Revalidate every cached query under the list endpoint.
 *
 * Prefix-based — covers all variants with different page/search/ordering
 * params. The detail endpoint isn't preemptively revalidated; SWR
 * naturally refetches it on the next mount.
 */
function revalidateTechCatalogCaches() {
  revalidateMultiple([endpoints.list]);
}

// ==============================|| LIST HOOK ||============================== //

/**
 * GET TECH CATALOG ENTRIES — paginated list.
 *
 * @param {Object} options - { page, pageSize, search, ordering }
 * @returns {Object} {
 *   entries, entriesCount, entriesLoading, entriesError,
 *   entriesValidating, entriesEmpty, mutateEntries
 * }
 */
export function useGetTechCatalogEntries(options = {}) {
  const { tenantId } = useAuth();
  const {
    page = 1,
    pageSize = 50,
    search = "",
    ordering = "company_name",
  } = options;

  const urlWithParams = useMemo(
    () =>
      buildUrlWithParams(endpoints.list, {
        page,
        pageSize,
        search,
        ordering,
      }),
    [page, pageSize, search, ordering],
  );

  const swrKey = tenantKey(urlWithParams, tenantId);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  return useMemo(
    () => ({
      entries: data?.data?.results ?? data?.results ?? [],
      entriesCount: data?.data?.count ?? data?.count ?? 0,
      entriesLoading: isLoading,
      entriesError: error,
      entriesValidating: isValidating,
      entriesEmpty:
        !isLoading &&
        !(data?.data?.results?.length ?? data?.results?.length),
      mutateEntries: mutate,
    }),
    [data, isLoading, error, isValidating, mutate],
  );
}

// ==============================|| DETAIL HOOK ||============================== //

/**
 * GET TECH CATALOG ENTRY — single entry by id.
 *
 * @param {string} entryId - UUID of the entry
 * @returns {Object} {
 *   entry, entryLoading, entryError, entryValidating, mutateEntry
 * }
 */
export function useGetTechCatalogEntry(entryId) {
  const { tenantId } = useAuth();

  const swrKey = useMemo(() => {
    if (!entryId || !isValidUUID(entryId)) return null;
    return tenantKey(endpoints.detail(entryId), tenantId);
  }, [entryId, tenantId]);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  return useMemo(
    () => ({
      entry: data?.data ?? null,
      entryLoading: isLoading,
      entryError: error,
      entryValidating: isValidating,
      mutateEntry: mutate,
    }),
    [data, isLoading, error, isValidating, mutate],
  );
}

// ==============================|| MUTATIONS ||============================== //

/**
 * CREATE TECH CATALOG ENTRY
 *
 * POST /tech-catalog/
 *
 * Required payload: { company_name }.
 * Optional: { product_name, vendor_url, is_competitor, is_integration_target }.
 *
 * If product_name is omitted or blank, the backend auto-fills it from
 * company_name (see model.clean()).
 *
 * @param {Object} payload
 * @returns {Promise<{ success: boolean, data?: Object, error?: string, status?: number }>}
 */
export async function createTechCatalogEntry(payload) {
  const result = await api.post(endpoints.list, payload);

  if (result.success) {
    revalidateTechCatalogCaches();
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
 * UPDATE TECH CATALOG ENTRY (PATCH)
 *
 * PATCH /tech-catalog/<id>/
 *
 * Every field is optional — only what the client sends gets written.
 * Server enforces tenant-scoped uniqueness on (company_name, product_name)
 * when either name field is changing.
 *
 * @param {string} entryId
 * @param {Object} payload
 * @returns {Promise<{ success: boolean, data?: Object, error?: string, status?: number }>}
 */
export async function updateTechCatalogEntry(entryId, payload) {
  if (!entryId || !isValidUUID(entryId)) {
    return {
      success: false,
      error: "Invalid tech catalog entry ID format",
      status: 400,
    };
  }

  const url = endpoints.detail(entryId);
  const result = await api.patch(url, payload);

  if (result.success) {
    revalidateTechCatalogCaches();
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
 * DELETE TECH CATALOG ENTRY
 *
 * DELETE /tech-catalog/<id>/
 *
 * Hard delete — no soft-delete flag on the model. The admin owns
 * deletion semantics. Any FK from downstream consumers (DC, Product,
 * signals) is governed by their own on_delete behaviour.
 *
 * @param {string} entryId
 * @returns {Promise<{ success: boolean, status?: number, error?: string }>}
 */
export async function deleteTechCatalogEntry(entryId) {
  if (!entryId || !isValidUUID(entryId)) {
    return {
      success: false,
      error: "Invalid tech catalog entry ID format",
      status: 400,
    };
  }

  const url = endpoints.detail(entryId);
  const result = await api.delete(url);

  if (result.success || result.status === 200 || result.status === 204) {
    revalidateTechCatalogCaches();
    return { success: true, status: result.status ?? 200 };
  }

  return {
    success: false,
    error: result.error,
    status: result.status ?? 0,
    response: result.response ?? null,
  };
}