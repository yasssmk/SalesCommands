// frontend/src/api/admin/accounts.js

import useSWR from 'swr';
import { useMemo } from 'react';
import { useAuth } from 'hooks/useAuth';
import { api } from 'utils/axiosClient';
import { tenantKey, revalidateMultiple, handleBulkRevalidation } from 'api/_swr';
import { isValidUUID, sanitizeObject } from 'utils/validators';

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  accounts: '/company-accounts/',
  accountDetail: (id) => `/company-accounts/${id}/`,
  choices: '/company-accounts/choices/',
  bulkCreate: '/company-accounts/bulk-create/',
  bulkUpdate: '/company-accounts/bulk-update/',
  bulkDelete: '/company-accounts/bulk-delete/'
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

  // Advanced filters for CompanyAccounts
  if (filters.type) {
    queryParams.append('type', filters.type);
  }
  
  if (filters.classification) {
    queryParams.append('classification', filters.classification);
  }
  
  if (filters.tier) {
    queryParams.append('tier', filters.tier);
  }

  if (filters.account_owner) {
    queryParams.append('account_owner', filters.account_owner);
  }
  
  const queryString = queryParams.toString();
  return queryString ? `${baseUrl}?${queryString}` : baseUrl;
};

// ==============================|| READ HOOKS ||============================== //

/**
 * GET ACCOUNTS - Paginated list with filters
 * 
 * @param {Object} options - {page, pageSize, search, ordering, filters}
 * @returns {Object} {accounts, accountsCount, accountsLoading, accountsError, accountsValidating, accountsEmpty}
 */
export function useGetAccounts(options = {}) {
  const { tenantId } = useAuth();
  const { page = 1, pageSize = 10, search = '', ordering = '', filters = {} } = options;

  const urlWithParams = useMemo(() => {
    return buildUrlWithParams(endpoints.accounts, { page, pageSize, search, ordering, filters });
  }, [page, pageSize, search, ordering, filters]);

  const swrKey = tenantKey(urlWithParams, tenantId);

  const { data, isLoading, error, isValidating } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      accounts: data?.data?.results || data?.results || [],
      accountsCount: data?.data?.count || data?.count || 0,
      accountsLoading: isLoading,
      accountsError: error,
      accountsValidating: isValidating,
      accountsEmpty: !isLoading && !(data?.data?.results?.length || data?.results?.length)
    }),
    [data, isLoading, error, isValidating]
  );

  return memoizedValue;
}

/**
 * GET ACCOUNT - Single account details
 * 
 * @param {string} accountId - UUID of the account
 * @returns {Object} {account, accountLoading, accountError, accountValidating}
 */
export function useGetAccount(accountId) {
  const { tenantId } = useAuth();

  const swrKey = useMemo(() => {
    if (!accountId || !isValidUUID(accountId)) return null;
    return tenantKey(endpoints.accountDetail(accountId), tenantId);
  }, [accountId, tenantId]);

  const { data, isLoading, error, isValidating } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      account: data?.data || data || null,
      accountLoading: isLoading,
      accountError: error,
      accountValidating: isValidating
    }),
    [data, isLoading, error, isValidating]
  );

  return memoizedValue;
}

/**
 * GET ACCOUNT CHOICES - For dropdowns (type, classification, tier)
 * 
 * @returns {Object} {choices, choicesLoading, choicesError}
 */
export function useGetAccountChoices() {
  const { tenantId } = useAuth();

  const swrKey = tenantKey(endpoints.choices, tenantId);

  const { data, isLoading, error } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      choices: data?.data || data || {},
      choicesLoading: isLoading,
      choicesError: error
    }),
    [data, isLoading, error]
  );

  return memoizedValue;
}

// ==============================|| MUTATION FUNCTIONS ||============================== //

/**
 * CREATE ACCOUNT - Insert new company account
 * 
 * @param {Object} payload - Account data
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function createAccount(payload) {
  // Sanitize string fields
  const sanitized = sanitizeObject(payload, ['company_name', 'description', 'website', 'industry']);
  
  const result = await api.post(endpoints.accounts, sanitized);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.accounts,
      '/activities/',
      '/opportunities/'
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
 * UPDATE ACCOUNT - Modify existing account
 * 
 * @param {string} accountId - UUID of the account
 * @param {Object} payload - Account data to update
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function updateAccount(accountId, payload) {
  // Validate accountId
  if (!accountId || !isValidUUID(accountId)) {
    return {
      success: false,
      error: 'Invalid account ID format',
      status: 400
    };
  }
  
  // Sanitize string fields
  const sanitized = sanitizeObject(payload, ['company_name', 'description', 'website', 'industry']);
  
  const result = await api.patch(endpoints.accountDetail(accountId), sanitized);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.accounts,
      endpoints.accountDetail(accountId),
      '/activities/',
      '/opportunities/'
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
 * DELETE ACCOUNT - Remove account
 * 
 * @param {string} accountId - UUID of the account
 * @returns {Promise<Object>} {success: boolean, status?: number, error?: string}
 */
export async function deleteAccount(accountId) {
  // Validate accountId
  if (!accountId || !isValidUUID(accountId)) {
    return {
      success: false,
      error: 'Invalid account ID format',
      status: 400
    };
  }
  
  const result = await api.delete(endpoints.accountDetail(accountId));
  
  if (result.success || result.status === 204) {
    revalidateMultiple([
      endpoints.accounts,
      '/activities/',
      '/opportunities/'
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

// ==============================|| BULK OPERATIONS ||============================== //

/**
 * BULK DELETE ACCOUNTS - Delete multiple accounts
 * 
 * @param {string[]} ids - Array of account UUIDs
 * @param {string} mode - 'strict' (all-or-nothing) or 'partial' (best-effort)
 * @param {Function} onSyncProgress - Optional callback for sync progress
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function bulkDeleteAccounts(ids, mode = 'partial', onSyncProgress = null) {
  // Validate IDs
  if (!Array.isArray(ids) || ids.length === 0) {
    return {
      success: false,
      error: 'No account IDs provided',
      status: 400
    };
  }
  
  // Validate all UUIDs
  const invalidIds = ids.filter(id => !isValidUUID(id));
  if (invalidIds.length > 0) {
    return {
      success: false,
      error: `Invalid account ID format: ${invalidIds.join(', ')}`,
      status: 400
    };
  }
  
  let result = null;
  
  try {
    result = await api.delete(endpoints.bulkDelete, {
      data: { ids, mode }
    });
    
    if (result.success) {
      return { success: true, data: result.data };
    }
    
    return {
      success: false,
      error: result.error,
      status: result.status || 0,
      response: result.response || null
    };
  } finally {
    // Handle revalidation (immediate or progressive based on result)
    await handleBulkRevalidation(
      result,
      [endpoints.accounts, '/activities/', '/opportunities/'],
      onSyncProgress
    );
  }
}

/**
 * BULK UPDATE ACCOUNTS - Update multiple accounts
 * 
 * @param {string[]} ids - Array of account UUIDs
 * @param {Object} patch - Fields to update
 * @param {string} mode - 'strict' (all-or-nothing) or 'partial' (best-effort)
 * @param {Function} onSyncProgress - Optional callback for sync progress
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function bulkUpdateAccounts(ids, patch, mode = 'partial', onSyncProgress = null) {
  // Validate IDs
  if (!Array.isArray(ids) || ids.length === 0) {
    return {
      success: false,
      error: 'No account IDs provided',
      status: 400
    };
  }
  
  // Validate all UUIDs
  const invalidIds = ids.filter(id => !isValidUUID(id));
  if (invalidIds.length > 0) {
    return {
      success: false,
      error: `Invalid account ID format: ${invalidIds.join(', ')}`,
      status: 400
    };
  }
  
  // Validate patch object
  if (!patch || typeof patch !== 'object' || Object.keys(patch).length === 0) {
    return {
      success: false,
      error: 'No fields to update provided',
      status: 400
    };
  }
  
  let result = null;
  
  try {
    result = await api.patch(endpoints.bulkUpdate, {
      ids,
      patch,
      mode
    });
    
    if (result.success) {
      return { success: true, data: result.data };
    }
    
    return {
      success: false,
      error: result.error,
      status: result.status || 0,
      response: result.response || null
    };
  } finally {
    // Handle revalidation (immediate or progressive based on result)
    await handleBulkRevalidation(
      result,
      [endpoints.accounts, '/activities/', '/opportunities/'],
      onSyncProgress
    );
  }
}

/**
 * BULK CREATE ACCOUNTS - Create multiple accounts
 * 
 * @param {Object[]} accounts - Array of account data objects
 * @param {string} mode - 'strict' (all-or-nothing) or 'partial' (best-effort)
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function bulkCreateAccounts(accounts, mode = 'partial') {
  // Validate input
  if (!Array.isArray(accounts) || accounts.length === 0) {
    return {
      success: false,
      error: 'No accounts provided',
      status: 400
    };
  }
  
  // Sanitize each account
  const sanitizedAccounts = accounts.map(account => 
    sanitizeObject(account, ['company_name', 'description', 'website', 'industry'])
  );
  
  const result = await api.post(endpoints.bulkCreate, {
    accounts: sanitizedAccounts,
    mode
  });
  
  if (result.success) {
    revalidateMultiple([
      endpoints.accounts,
      '/activities/',
      '/opportunities/'
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