// frontend/src/api/businessData/productCatalog.js
/**
 * API hooks for the ProductCatalog module.
 *
 * The ProductCatalog is a tenant-level master list of products the
 * organisation sells. Curated by admins, consumed read-only by the
 * DealProduct surface in the DC Workspace.
 *
 * Endpoint: /product-catalog/
 *
 * Mirrors the techCatalog.js pattern for reads (list hook only —
 * admin CRUD lives in a future admin view).
 */

import useSWR from "swr";
import { useMemo } from "react";

import { useAuth } from "hooks/useAuth";
import { tenantKey } from "api/_swr";

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  list: "/product-catalog/",
};

// ==============================|| LIST HOOK ||============================== //

/**
 * GET PRODUCT CATALOG ENTRIES — full list (no pagination for picker use).
 *
 * @param {Object} options - { search }
 * @returns {Object} {
 *   entries, entriesLoading, entriesError, entriesEmpty, mutateEntries
 * }
 */
export function useGetProductCatalogEntries(options = {}) {
  const { tenantId } = useAuth();
  const { search = "" } = options;

  const urlWithParams = useMemo(() => {
    const query = new URLSearchParams();
    query.append("page_size", "200");
    if (search) {
      query.append("search", search);
    }
    const qs = query.toString();
    return qs ? `${endpoints.list}?${qs}` : endpoints.list;
  }, [search]);

  const swrKey = tenantKey(urlWithParams, tenantId);

  const { data, isLoading, error, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  return useMemo(
    () => ({
      entries: data?.data?.results ?? data?.results ?? [],
      entriesLoading: isLoading,
      entriesError: error,
      entriesEmpty:
        !isLoading && !(data?.data?.results?.length ?? data?.results?.length),
      mutateEntries: mutate,
    }),
    [data, isLoading, error, mutate],
  );
}
