// frontend/src/api/territories.js
/**
 * API hooks and mutations for Territories module.
 * 
 * Follows the same patterns as accounts.js for consistency.
 */

import useSWR from 'swr';
import { useMemo } from 'react';
import { useAuth } from 'hooks/useAuth';
import { api } from 'utils/axiosClient';
import { tenantKey, revalidateMultiple } from 'api/_swr';
import { isValidUUID, sanitizeObject } from 'utils/validators';

// ==============================|| CONSTANTS ||============================== //

/**
 * Territory types (matching backend TerritoryType choices)
 */
export const TERRITORY_TYPES = {
  ACCOUNT: 'ACCOUNT',
  CONTACT: 'CONTACT'
};

/**
 * Default territory ID for "All Accounts"
 * Note: This is a frontend constant for hardcoded territories
 * Once backend is connected, system territories will have real UUIDs
 */
export const DEFAULT_TERRITORY_ID = 'all-accounts';

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  territories: '/territories/',
  territoryDetail: (id) => `/territories/${id}/`,
  choices: '/territories/choices/',
  accountsCount: (id) => `/territories/${id}/accounts-count/`
};

// ==============================|| HELPER - BUILD URL WITH PARAMS ||============================== //

/**
 * Build URL with query params for server-side pagination/filtering
 * @param {string} baseUrl - Base URL
 * @param {Object} params - Optional params {page, pageSize, search, ordering, filters}
 * @returns {string} URL with query string
 */
const buildUrlWithParams = (baseUrl, params = {}) => {
  const { page, pageSize, search, ordering, filters = {} } = params;
  const queryParams = new URLSearchParams();
  
  // Pagination
  if (page !== undefined && page !== null) {
    queryParams.append('page', page);
  }
  
  if (pageSize !== undefined && pageSize !== null) {
    queryParams.append('page_size', pageSize);
  }
  
  // Search
  if (search !== undefined && search !== null && search !== '') {
    queryParams.append('search', search);
  }

  // Ordering
  if (ordering !== undefined && ordering !== null && ordering !== '') {
    queryParams.append('ordering', ordering);
  }

  // Owner scope filter (mine/team/all)
  if (filters.owner_scope) {
    queryParams.append('owner_scope', filters.owner_scope);
  }

  // Filters
  if (filters.type) {
    queryParams.append('type', filters.type);
  }
  
  if (filters.is_system !== undefined) {
    queryParams.append('is_system', filters.is_system);
  }

  if (filters.owner) {
    queryParams.append('owner', filters.owner);
  }
  
  const queryString = queryParams.toString();
  return queryString ? `${baseUrl}?${queryString}` : baseUrl;
};

// ==============================|| READ HOOKS ||============================== //

/**
 * GET TERRITORIES - Paginated list with filters
 * 
 * @param {Object} options - {page, pageSize, search, ordering, filters}
 * @returns {Object} {territories, territoriesCount, territoriesLoading, territoriesError, territoriesValidating, territoriesEmpty}
 */
export function useGetTerritories(options = {}) {
  const { tenantId } = useAuth();
  const { page = 1, pageSize = 50, search = '', ordering = '', filters = {} } = options;

  const urlWithParams = useMemo(() => {
    return buildUrlWithParams(endpoints.territories, { page, pageSize, search, ordering, filters });
  }, [page, pageSize, search, ordering, filters]);

  const swrKey = tenantKey(urlWithParams, tenantId);

  const { data, isLoading, error, isValidating } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      territories: data?.data?.results || data?.results || [],
      territoriesCount: data?.data?.count || data?.count || 0,
      territoriesLoading: isLoading,
      territoriesError: error,
      territoriesValidating: isValidating,
      territoriesEmpty: !isLoading && !(data?.data?.results?.length || data?.results?.length)
    }),
    [data, isLoading, error, isValidating]
  );

  return memoizedValue;
}

/**
 * GET TERRITORY - Single territory details
 * 
 * @param {string} territoryId - UUID of the territory
 * @returns {Object} {territory, territoryLoading, territoryError, territoryValidating}
 */
export function useGetTerritory(territoryId) {
  const { tenantId } = useAuth();

  const swrKey = useMemo(() => {
    if (!territoryId || !isValidUUID(territoryId)) return null;
    return tenantKey(endpoints.territoryDetail(territoryId), tenantId);
  }, [territoryId, tenantId]);

  const { data, isLoading, error, isValidating } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      territory: data?.data || data || null,
      territoryLoading: isLoading,
      territoryError: error,
      territoryValidating: isValidating
    }),
    [data, isLoading, error, isValidating]
  );

  return memoizedValue;
}

/**
 * GET TERRITORY CHOICES - Types for dropdowns
 * 
 * @returns {Object} {choices, types, choicesLoading, choicesError}
 */
export function useGetTerritoryChoices() {
  const { tenantId } = useAuth();

  const swrKey = tenantKey(endpoints.choices, tenantId);

  const { data, isLoading, error } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      choices: data?.data || {},
      types: data?.data?.type || [],
      choicesLoading: isLoading,
      choicesError: error
    }),
    [data, isLoading, error]
  );

  return memoizedValue;
}

// ==============================|| MUTATION FUNCTIONS ||============================== //

/**
 * CREATE TERRITORY - Insert new territory
 * 
 * @param {Object} payload - Territory data {name, description, type, filter_definition, is_default}
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function createTerritory(payload) {
  // Sanitize string fields
  const sanitized = sanitizeObject(payload, ['name', 'description']);
  
  const result = await api.post(endpoints.territories, sanitized);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.territories,
      '/company-accounts/'  // Territories affect account filtering
    ]);
    return { success: true, data: result.data };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

/**
 * UPDATE TERRITORY - Modify existing territory
 * 
 * @param {string} territoryId - UUID of the territory
 * @param {Object} payload - Territory data to update
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function updateTerritory(territoryId, payload) {
  // Validate territoryId
  if (!territoryId || !isValidUUID(territoryId)) {
    return {
      success: false,
      error: 'Invalid territory ID format',
      status: 400
    };
  }
  
  // Sanitize string fields
  const sanitized = sanitizeObject(payload, ['name', 'description']);
  
  const result = await api.patch(endpoints.territoryDetail(territoryId), sanitized);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.territories,
      endpoints.territoryDetail(territoryId),
      '/company-accounts/'  // Territories affect account filtering
    ]);
    return { success: true, data: result.data };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

/**
 * DELETE TERRITORY - Remove territory
 * 
 * @param {string} territoryId - UUID of the territory
 * @returns {Promise<Object>} {success: boolean, status?: number, error?: string}
 */
export async function deleteTerritory(territoryId) {
  // Validate territoryId
  if (!territoryId || !isValidUUID(territoryId)) {
    return {
      success: false,
      error: 'Invalid territory ID format',
      status: 400
    };
  }
  
  const result = await api.delete(endpoints.territoryDetail(territoryId));
  
  if (result.success || result.status === 204) {
    revalidateMultiple([
      endpoints.territories,
      '/company-accounts/'  // Territories affect account filtering
    ]);
    return { success: true, status: result.status ?? 204 };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

// ==============================|| HELPER FUNCTIONS ||============================== //

/**
 * Get accounts count for a territory
 * 
 * @param {string} territoryId - UUID of the territory
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function getTerritoryAccountsCount(territoryId) {
  if (!territoryId || !isValidUUID(territoryId)) {
    return {
      success: false,
      error: 'Invalid territory ID format',
      status: 400
    };
  }
  
  const result = await api.get(endpoints.accountsCount(territoryId));
  
  if (result.success) {
    return { success: true, data: result.data };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0
  };
}