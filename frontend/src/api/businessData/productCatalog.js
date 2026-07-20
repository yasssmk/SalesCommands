// frontend/src/api/businessData/productCatalog.js
/**
 * API hooks and mutations for the ProductCatalog module.
 *
 * The ProductCatalog is a tenant-level master list of products the
 * organisation sells. Curated by admins, consumed read-only by the
 * DealProduct surface in the DC Workspace and, from this sprint, edited
 * through the Business Data > Products admin table.
 *
 * Endpoint group (single, flat):
 *   /product-catalog/
 *
 * Patterns (mirrors techCatalog.js):
 *   - SWR list hook for reads, with tenantKey() for multi-tenant isolation
 *   - Mutations call api.post/patch/delete and revalidate the list
 *     prefix on success so cached pages reflect the new state
 *   - Write mutations validate the UUID format before hitting the network
 *   - Result objects always carry { success, data?, error?, status }
 *
 * Backward compatibility:
 *   The list hook defaults to a large page size so existing picker
 *   consumers (DC Workspace ProductsTab) keep receiving the full catalog
 *   when they call it with no options. The admin table passes explicit
 *   page / pageSize / ordering for server-side pagination.
 */

import useSWR from "swr";
import { useMemo } from "react";

import { useAuth } from "hooks/useAuth";
import { api } from "utils/axiosClient";
import { tenantKey, revalidateMultiple } from "api/_swr";
import { isValidUUID } from "utils/validators";

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  list: "/product-catalog/",
  detail: (id) => `/product-catalog/${id}/`,
};

// ==============================|| URL BUILDER ||============================== //

/**
 * Build a list URL with query params for server-side pagination,
 * search and ordering.
 *
 * Supported params:
 *   - page, pageSize → standard DRF pagination
 *   - search         → matches against name (server-side, see
 *                      ProductCatalogViewSet.search_fields)
 *   - ordering       → e.g. "name", "-default_unit_price", "-updated_at"
 *
 * No structured filters — the catalog has no advanced filter surface.
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
function revalidateProductCatalogCaches() {
  revalidateMultiple([endpoints.list]);
}

// ==============================|| LIST HOOK ||============================== //

/**
 * GET PRODUCT CATALOG ENTRIES — paginated list.
 *
 * Defaults to a large page size (picker mode) so callers that pass no
 * options — such as the DC Workspace ProductsTab picker — keep receiving
 * the full catalog. The admin table passes explicit pagination params.
 *
 * @param {Object} options - { page, pageSize, search, ordering }
 * @returns {Object} {
 *   entries, entriesCount, entriesLoading, entriesError,
 *   entriesValidating, entriesEmpty, mutateEntries
 * }
 */
export function useGetProductCatalogEntries(options = {}) {
  const { tenantId } = useAuth();
  const {
    page = 1,
    pageSize = 200,
    search = "",
    ordering = "name",
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
        !isLoading && !(data?.data?.results?.length ?? data?.results?.length),
      mutateEntries: mutate,
    }),
    [data, isLoading, error, isValidating, mutate],
  );
}

// ==============================|| MUTATIONS ||============================== //

/**
 * CREATE PRODUCT CATALOG ENTRY
 *
 * POST /product-catalog/
 *
 * Required payload: { name }.
 * Optional: { description, value_proposition, default_unit_price }.
 *
 * Admin-only — enforced server-side by ScopedPermission.
 *
 * @param {Object} payload
 * @returns {Promise<{ success: boolean, data?: Object, error?: string, status?: number }>}
 */
export async function createProductCatalogEntry(payload) {
  const result = await api.post(endpoints.list, payload);

  if (result.success) {
    revalidateProductCatalogCaches();
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
 * UPDATE PRODUCT CATALOG ENTRY (PATCH)
 *
 * PATCH /product-catalog/<id>/
 *
 * Every field is optional — only what the client sends gets written.
 * Server enforces tenant-scoped uniqueness on name when it is changing.
 *
 * Admin-only — enforced server-side by ScopedPermission.
 *
 * @param {string} entryId
 * @param {Object} payload
 * @returns {Promise<{ success: boolean, data?: Object, error?: string, status?: number }>}
 */
export async function updateProductCatalogEntry(entryId, payload) {
  if (!entryId || !isValidUUID(entryId)) {
    return {
      success: false,
      error: "Invalid product catalog entry ID format",
      status: 400,
    };
  }

  const url = endpoints.detail(entryId);
  const result = await api.patch(url, payload);

  if (result.success) {
    revalidateProductCatalogCaches();
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
 * DELETE PRODUCT CATALOG ENTRY
 *
 * DELETE /product-catalog/<id>/
 *
 * Hard delete. Any FK from downstream consumers (DealProduct) is governed
 * by their own on_delete behaviour.
 *
 * Admin-only — enforced server-side by ScopedPermission.
 *
 * @param {string} entryId
 * @returns {Promise<{ success: boolean, status?: number, error?: string }>}
 */
export async function deleteProductCatalogEntry(entryId) {
  if (!entryId || !isValidUUID(entryId)) {
    return {
      success: false,
      error: "Invalid product catalog entry ID format",
      status: 400,
    };
  }

  const url = endpoints.detail(entryId);
  const result = await api.delete(url);

  if (result.success || result.status === 200 || result.status === 204) {
    revalidateProductCatalogCaches();
    return { success: true, status: result.status ?? 200 };
  }

  return {
    success: false,
    error: result.error,
    status: result.status ?? 0,
    response: result.response ?? null,
  };
}
