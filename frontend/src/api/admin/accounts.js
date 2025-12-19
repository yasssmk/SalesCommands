// frontend/src/api/admin/accounts.js

import useSWR from 'swr';
import { useMemo } from 'react';
import { useAuth } from 'hooks/useAuth';
import { api } from 'utils/axiosClient';
import { tenantKey, revalidateMultiple, handleBulkRevalidation, handleBulkTimeout } from 'api/_swr';
import { isValidUUID, sanitizeObject } from 'utils/validators';

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  accounts: '/company-accounts/',
  accountDetail: (id) => `/company-accounts/${id}/`,
  accountWorkspace: (id) => `/company-accounts/${id}/workspace/`, 
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

  // Owner scope filter (mine/team/all)
  if (filters.owner_scope) {
    queryParams.append('owner_scope', filters.owner_scope);
  }

// Advanced filters for CompanyAccounts
  if (filters.type) {
    queryParams.append('type', filters.type);
  }
  
  if (filters.classification) {
    queryParams.append('classification', filters.classification);
  }

  if (filters.account_owner) {
    queryParams.append('account_owner', filters.account_owner);
  }

  if (filters.industry) {
    queryParams.append('industry', filters.industry);
  }

  if (filters.country) {
    queryParams.append('country', filters.country);
  }

  if (filters.company_size) {
    queryParams.append('company_size', filters.company_size);
  }

  if (filters.annual_revenue) {
    queryParams.append('annual_revenue', filters.annual_revenue);
  }

  if (filters.has_buying_decision !== undefined && filters.has_buying_decision !== null) {
    queryParams.append('has_buying_decision', filters.has_buying_decision);
  }

  // Territory filter (backend applies filter_definition)
  if (filters.territory_id) {
    queryParams.append('territory_id', filters.territory_id);
  }

  // FK filters (Phase 2)
  if (filters.has_tech_stack) {
    queryParams.append('has_tech_stack', filters.has_tech_stack);
  }

  if (filters.buying_process_stage) {
    queryParams.append('buying_process_stage', filters.buying_process_stage);
  }

  if (filters.has_qualification !== undefined && filters.has_qualification !== null) {
    queryParams.append('has_qualification', filters.has_qualification);
  }

  if (filters.signals_since_days) {
    queryParams.append('signals_since_days', filters.signals_since_days);
  }

  if (filters.owner_scope) {
    queryParams.append('owner_scope', filters.owner_scope);
  }

  // Territory filter - applies territory's filter_definition on backend
  if (filters.territory_id) {
    queryParams.append('territory_id', filters.territory_id);
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
 * GET ACCOUNT WORKSPACE - Account workspace header data
 * 
 * @param {string} accountId - UUID of the account
 * @returns {Object} {workspace, workspaceLoading, workspaceError, workspaceValidating}
 */
export function useGetAccountWorkspace(accountId) {
  const { tenantId } = useAuth();

  const swrKey = useMemo(() => {
    if (!accountId || !isValidUUID(accountId)) return null;
    return tenantKey(endpoints.accountWorkspace(accountId), tenantId);
  }, [accountId, tenantId]);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      workspace: data?.data || null,
      account: data?.data?.account || null,
      stats: data?.data?.stats || null,
      workspaceLoading: isLoading,
      workspaceError: error,
      workspaceValidating: isValidating,
      mutateWorkspace: mutate
    }),
    [data, isLoading, error, isValidating, mutate]
  );

  return memoizedValue;
}

/**
 * GET ACCOUNT CHOICES - Types, Classifications, Industries
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
      choices: data?.data || {},
      types: data?.data?.types || [],
      classifications: data?.data?.classifications || [],
      industries: data?.data?.industries || [],
      countries: data?.data?.countries || [],
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
      '/opportunities/',
      '/territories/'
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
      '/opportunities/',
      '/territories/'
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
      '/opportunities/',
      '/territories/'
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
 * ✅ BULK DELETE ACCOUNTS
 * 
 * Delete multiple accounts in a single request
 * Uses 'bulk' profile (60s timeout)
 * 
 * @param {Array<string>} accountIds - Array of account IDs to delete
 * @param {string} mode - 'partial' (continue on error) or 'strict' (all or nothing)
 * @param {Function} onSyncProgress - Optional callback: (attempt, maxAttempts) => void
 * @param {Function} onSyncComplete - Optional callback: () => void (called when sync is done)
 * @returns {Promise<Object>} {success: boolean, isTimeout?: boolean, summary: Object, results: Object}
 */
export const bulkDeleteAccounts = async (accountIds, mode = 'partial', onSyncProgress = null, onSyncComplete = null) => {
  let result = null;

  try {
    console.log('[bulkDeleteAccounts] start', { count: accountIds?.length ?? 0, mode });

    if (!Array.isArray(accountIds) || accountIds.length === 0) {
      return {
        success: false,
        message: 'No account IDs provided',
        summary: { requested: 0, deleted: 0, failed: 0 },
        results: { success: [], failed: [] }
      };
    }

    const invalidIds = accountIds.filter(id => !isValidUUID(id));
    if (invalidIds.length > 0) {
      console.error('[bulkDeleteAccounts] invalid UUIDs', { count: invalidIds.length });
      return {
        success: false,
        message: `${invalidIds.length} invalid account ID(s) detected`,
        summary: { requested: accountIds.length, deleted: 0, failed: accountIds.length },
        results: {
          success: [],
          failed: invalidIds.map(id => ({ id, errors: ['Invalid UUID format'] }))
        }
      };
    }

    result = await api.delete(endpoints.bulkDelete, {
      data: { ids: accountIds, mode },
      profile: 'bulk'
    });

    console.log('[bulkDeleteAccounts] API response received:', {
      success: result.success,
      status: result.status,
      hasData: !!result.data,
      is202: result?.data?.__is202
    });

    // ✅ CAS 202 : Attendre le polling
    if (result?.data?.__is202) {
      console.log('[bulkDeleteAccounts] 🔄 202 detected, starting polling...');
      
      const finalResult = await handleBulkRevalidation(
        result,
        [endpoints.accounts, '/activities/', '/opportunities/', '/contacts/'],
        onSyncProgress,
        onSyncComplete
      );

      console.log('[bulkDeleteAccounts] 📥 Polling complete:', {
        hasFinalResult: !!finalResult,
        hasData: finalResult?.data !== undefined
      });

      if (finalResult?.data) {
        console.log('[bulkDeleteAccounts] ✅ Returning polling result');
        if (finalResult.data?.status === 'pending') {
          console.log('[bulkDeleteAccounts] ⏳ Polling reached max attempts, marking operation as pending');
          return {
            ...finalResult.data,
            success: false,
            status: finalResult.data.status || 'pending',
            isPending: true
          };
        }

        return finalResult.data;
      }

      if (finalResult && (finalResult.summary || finalResult.results)) {
        console.log('[bulkDeleteAccounts] ✅ Returning finalResult directly');
        return finalResult;
      }

      console.error('[bulkDeleteAccounts] ❌ finalResult missing data');
      return {
        success: false,
        message: 'Polling completed but no result data',
        summary: { requested: accountIds.length, deleted: 0, failed: accountIds.length },
        results: { success: [], failed: [] }
      };
    }

    // ✅ CAS SYNC
    if (result.success) {
      console.log('[bulkDeleteAccounts] ✅ Sync success', { 
        status: result.status ?? 200,
        deleted: result.data?.summary?.deleted ?? 0
      });

      revalidateMultiple([endpoints.accounts, '/activities/', '/opportunities/', '/contacts/', '/territories/']);
      return result.data;
    }

    // CAS TIMEOUT - Trigger polling (apiRequest returns, doesn't throw)
    if (result.isTimeout) {
      console.log('[bulkDeleteAccounts] ⏱️ Timeout detected in result, starting polling...');
      
      const pollResult = await handleBulkTimeout(
        { idempotencyKey: result.idempotencyKey },
        [endpoints.accounts, '/activities/', '/opportunities/', '/contacts/'],
        onSyncProgress,
        onSyncComplete
      );
      
      if (pollResult?.status === 'succeeded') {
        // Backend stores: { data: {...}, http_status: 200 }
        // We need to unwrap .data to get the actual result
        const actualResult = pollResult.result?.data || pollResult.result || {};
        return {
          success: true,
          ...actualResult
        };
      }
      
      return {
        success: false,
        isTimeout: true,
        isPending: pollResult?.status === 'still_running',
        message: pollResult?.error || 'Operation may have completed in background',
        summary: { requested: accountIds?.length ?? 0, deleted: 0, failed: 0 },
        results: { success: [], failed: [] }
      };
    }

    // ❌ Gestion erreur
    const status = result.status || 0;
    const message = result.error || 'Bulk delete failed';
    console.error('[bulkDeleteAccounts] api.delete error', { status, message });

    if (result.data && typeof result.data === 'object') {
      if (result.data.results || result.data.summary) {
        console.log('[bulkDeleteAccounts] returning structured error from backend');
        return {
          ...result.data,
          success: false,
          status: result.status,
          isTimeout: result.isTimeout || false  
        };
      }
    }

    return {
      success: false,
      isTimeout: result.isTimeout || false,
      message: message,
      error: { status, message, response: result.response || null },
      summary: { requested: accountIds.length, deleted: 0, failed: accountIds.length },
      results: {
        success: [],
        failed: accountIds.map(id => ({ id, errors: [message] }))
      }
    };

  } catch (err) {
    console.error('[bulkDeleteAccounts] thrown', err);
    
    const isTimeout = 
      err?.code === 'ECONNABORTED' || 
      err?.message?.toLowerCase()?.includes('timeout') ||
      err?.response?.status === 408 ||
      err?.response?.status === 504;
    
    if (isTimeout) {
      console.log('[bulkDeleteAccounts] ⏱️ Timeout detected, starting polling...');
    
      const pollResult = await handleBulkTimeout(
        err,
        [endpoints.accounts, '/activities/', '/opportunities/', '/contacts/'],
        onSyncProgress,
        onSyncComplete
      );
      
      if (pollResult?.status === 'succeeded') {
        const actualResult = pollResult.result?.data || pollResult.result || {};
        return {
          success: true,
          ...actualResult
        };
      }
      
      return {
        success: false,
        isTimeout: true,
        isPending: pollResult?.status === 'still_running',
        message: pollResult?.error || 'Operation may have completed in background',
        summary: { requested: accountIds?.length ?? 0, deleted: 0, failed: 0 },
        results: { success: [], failed: [] }
      };
    }
    
    return {
      success: false,
      isTimeout: false,
      message: err?.message || 'Unknown error',
      error: { message: err?.message || String(err) },
      summary: { requested: accountIds?.length ?? 0, deleted: 0, failed: accountIds?.length ?? 0 },
      results: {
        success: [],
        failed: (accountIds || []).map(id => ({ id, errors: [err?.message || 'Unknown error'] }))
      }
    };
  }
};

/**
 * ✅ BULK UPDATE ACCOUNTS
 * 
 * Update multiple accounts in a single request
 * Uses 'bulk' profile (60s timeout)
 * 
 * @param {Array<string>} accountIds - Array of account IDs to update
 * @param {Object} patchData - Data to apply to all selected accounts
 * @param {string} mode - 'partial' (continue on error) or 'strict' (all or nothing)
 * @param {Function} onSyncProgress - Optional callback: (attempt, maxAttempts) => void
 * @param {Function} onSyncComplete - Optional callback: () => void (called when sync is done)
 * @returns {Promise<Object>} {success: boolean, isTimeout?: boolean, summary: Object, results: Object}
 */
export const bulkUpdateAccounts = async (accountIds, patchData, mode = 'partial', onSyncProgress = null, onSyncComplete = null) => {
  let result = null;

  try {
    console.log('[bulkUpdateAccounts] start', { 
      count: accountIds?.length ?? 0, 
      mode,
      fields: Object.keys(patchData || {})
    });

    if (!Array.isArray(accountIds) || accountIds.length === 0) {
      return {
        success: false,
        message: 'No account IDs provided',
        summary: { requested: 0, updated: 0, failed: 0 },
        results: { success: [], failed: [] }
      };
    }

    const invalidIds = accountIds.filter(id => !isValidUUID(id));
    if (invalidIds.length > 0) {
      console.error('[bulkUpdateAccounts] invalid UUIDs', { count: invalidIds.length });
      return {
        success: false,
        message: `${invalidIds.length} invalid account ID(s) detected`,
        summary: { requested: accountIds.length, updated: 0, failed: accountIds.length },
        results: {
          success: [],
          failed: invalidIds.map(id => ({ id, errors: ['Invalid UUID format'] }))
        }
      };
    }

    if (!patchData || typeof patchData !== 'object' || Object.keys(patchData).length === 0) {
      return {
        success: false,
        message: 'No fields to update provided',
        summary: { requested: accountIds.length, updated: 0, failed: 0 },
        results: { success: [], failed: [] }
      };
    }

    result = await api.patch(endpoints.bulkUpdate, {
      ids: accountIds,
      patch: patchData,
      mode
    }, {
      profile: 'bulk'
    });

    console.log('[bulkUpdateAccounts] API response received:', {
      success: result.success,
      status: result.status,
      hasData: !!result.data,
      is202: result?.data?.__is202
    });

    // ✅ CAS 202 : Attendre le polling
    if (result?.data?.__is202) {
      console.log('[bulkUpdateAccounts] 🔄 202 detected, starting polling...');
      
      const finalResult = await handleBulkRevalidation(
        result,
        [endpoints.accounts, '/activities/', '/opportunities/', '/contacts/'],
        onSyncProgress,
        onSyncComplete
      );

      console.log('[bulkUpdateAccounts] 📥 Polling complete:', {
        hasFinalResult: !!finalResult,
        hasData: finalResult?.data !== undefined
      });

      if (finalResult?.data) {
        console.log('[bulkUpdateAccounts] ✅ Returning polling result');
        if (finalResult.data?.status === 'pending') {
          console.log('[bulkUpdateAccounts] ⏳ Polling reached max attempts, marking operation as pending');
          return {
            ...finalResult.data,
            success: false,
            status: finalResult.data.status || 'pending',
            isPending: true
          };
        }
        return finalResult.data;
      }

      if (finalResult && (finalResult.summary || finalResult.results)) {
        console.log('[bulkUpdateAccounts] ✅ Returning finalResult directly');
        return finalResult;
      }

      console.error('[bulkUpdateAccounts] ❌ finalResult missing data');
      return {
        success: false,
        message: 'Polling completed but no result data',
        summary: { requested: accountIds.length, updated: 0, failed: accountIds.length },
        results: { success: [], failed: [] }
      };
    }

    // ✅ CAS SYNC
    if (result.success) {
      console.log('[bulkUpdateAccounts] ✅ Sync success', { 
        status: result.status ?? 200,
        updated: result.data?.summary?.updated ?? 0
      });

      revalidateMultiple([endpoints.accounts, '/activities/', '/opportunities/', '/contacts/', '/territories/']);
      return result.data;
    }

    // CAS TIMEOUT - Trigger polling (apiRequest returns, doesn't throw)
    if (result.isTimeout) {
      console.log('[bulkUpdateAccounts] ⏱️ Timeout detected in result, starting polling...');
      
      const pollResult = await handleBulkTimeout(
        { idempotencyKey: result.idempotencyKey },
        [endpoints.accounts, '/activities/', '/opportunities/', '/contacts/'],
        onSyncProgress,
        onSyncComplete
      );
      
      if (pollResult?.status === 'succeeded') {
        // Backend stores: { data: {...}, http_status: 200 }
        // We need to unwrap .data to get the actual result
        const actualResult = pollResult.result?.data || pollResult.result || {};
        return {
          success: true,
          ...actualResult
        };
      }
      
      return {
        success: false,
        isTimeout: true,
        isPending: pollResult?.status === 'still_running',
        message: pollResult?.error || 'Operation may have completed in background',
        summary: { requested: accountIds?.length ?? 0, updated: 0, failed: 0 },
        results: { success: [], failed: [] }
      };
    }

    // ❌ Gestion erreur
    const status = result.status || 0;
    const message = result.error || 'Bulk update failed';
    console.error('[bulkUpdateAccounts] api.patch error', { status, message });

    if (result.data && typeof result.data === 'object') {
      if (result.data.results || result.data.summary) {
        console.log('[bulkUpdateAccounts] returning structured error from backend');
        return {
          ...result.data,
          success: false,
          status: result.status,
          isTimeout: result.isTimeout || false
        };
      }
    }

    return {
      success: false,
      isTimeout: result.isTimeout || false,
      message: message,
      error: { status, message, response: result.response || null },
      summary: { requested: accountIds.length, updated: 0, failed: accountIds.length },
      results: {
        success: [],
        failed: accountIds.map(id => ({ id, errors: [message] }))
      }
    };

  } catch (err) {
    console.error('[bulkUpdateAccounts] thrown', err);
    
    const isTimeout = 
      err?.code === 'ECONNABORTED' || 
      err?.message?.toLowerCase()?.includes('timeout') ||
      err?.response?.status === 408 ||
      err?.response?.status === 504;
    
    if (isTimeout) {
      console.log('[bulkUpdateAccounts] ⏱️ Timeout detected, starting polling...');
      
      const pollResult = await handleBulkTimeout(
        err,
        [endpoints.accounts, '/activities/', '/opportunities/', '/contacts/'],
        onSyncProgress,
        onSyncComplete
      );
      
      if (pollResult?.status === 'succeeded') {
        const actualResult = pollResult.result?.data || pollResult.result || {};
        return {
          success: true,
          ...actualResult
        };
      }
      
      return {
        success: false,
        isTimeout: true,
        isPending: pollResult?.status === 'still_running',
        message: pollResult?.error || 'Operation may have completed in background',
        summary: { requested: accountIds?.length ?? 0, updated: 0, failed: 0 },
        results: { success: [], failed: [] }
      };
    }
    
    return {
      success: false,
      isTimeout: false,
      message: err?.message || 'Unknown error',
      error: { message: err?.message || String(err) },
      summary: { requested: accountIds?.length ?? 0, updated: 0, failed: accountIds?.length ?? 0 },
      results: {
        success: [],
        failed: (accountIds || []).map(id => ({ id, errors: [err?.message || 'Unknown error'] }))
      }
    };
  }
};

/**
 * ✅ BULK CREATE ACCOUNTS (CSV Import)
 * 
 * Create multiple accounts in a single request
 * Uses 'bulk' profile (60s timeout)
 * 
 * @param {Array} accounts - Array of account objects
 * @param {string} mode - 'partial' (continue on error) or 'strict' (all or nothing)
 * @param {Function} onSyncProgress - Optional callback: (attempt, maxAttempts) => void
 * @param {Function} onSyncComplete - Optional callback: () => void (called when sync is done)
 * @returns {Promise<Object>} {success: boolean, summary: Object, results: Object}
 */
export const bulkCreateAccounts = async (accounts, mode = 'partial', onSyncProgress = null, onSyncComplete = null) => {
  let result = null;

  try {
    console.log('[bulkCreateAccounts] start', { count: accounts?.length ?? 0, mode });

    if (!Array.isArray(accounts) || accounts.length === 0) {
      return {
        success: false,
        message: 'No accounts provided',
        summary: { total: 0, success: 0, failed: 0, skipped: 0 },
        results: { success: [], failed: [], skipped: [] }
      };
    }

    // Sanitize each account
    const sanitizedAccounts = accounts.map(account => 
      sanitizeObject(account, ['company_name', 'description', 'website', 'industry'])
    );

    result = await api.post(endpoints.bulkCreate, 
      { accounts: sanitizedAccounts, mode }, 
      { profile: 'bulk' }
    );

    console.log('[bulkCreateAccounts] API response received:', {
      success: result.success,
      status: result.status,
      hasData: !!result.data,
      is202: result?.data?.__is202
    });

    // ✅ CAS 202 : Attendre le polling AVANT de retourner
    if (result?.data?.__is202) {
      console.log('[bulkCreateAccounts] 🔄 202 detected, starting polling...');
      
      const finalResult = await handleBulkRevalidation(
        result,
        [endpoints.accounts, '/activities/', '/opportunities/', '/contacts/'],
        onSyncProgress,
        onSyncComplete
      );

      console.log('[bulkCreateAccounts] 📥 Polling complete:', {
        hasFinalResult: !!finalResult,
        hasData: finalResult?.data !== undefined
      });

      if (finalResult?.data) {
        console.log('[bulkCreateAccounts] ✅ Returning polling result');
        if (finalResult.data?.status === 'pending') {
          console.log('[bulkCreateAccounts] ⏳ Polling reached max attempts, marking operation as pending');
          return {
            ...finalResult.data,
            success: false,
            status: finalResult.data.status || 'pending',
            isPending: true
          };
        }

        return finalResult.data;
      }

      if (finalResult && (finalResult.summary || finalResult.results)) {
        console.log('[bulkCreateAccounts] ✅ Returning finalResult directly (no nesting)');
        return finalResult;
      }

      console.error('[bulkCreateAccounts] ❌ finalResult missing data structure');
      return {
        success: false,
        message: 'Polling completed but no result data',
        summary: { total: accounts?.length ?? 0, success: 0, failed: accounts?.length ?? 0, skipped: 0 },
        results: { success: [], failed: [], skipped: [] }
      };
    }

    // ✅ CAS SYNC : Retourner immédiatement
    if (result.success) {
      console.log('[bulkCreateAccounts] ✅ Sync success', { 
        status: result.status ?? 200,
        created: result.data?.summary?.success ?? result.data?.summary?.created ?? 0
      });

      revalidateMultiple([endpoints.accounts, '/activities/', '/opportunities/', '/contacts/', '/territories/']);
      
      return result.data;
    }

    // CAS TIMEOUT - Trigger polling (apiRequest returns, doesn't throw)
    if (result.isTimeout) {
      console.log('[bulkCreateAccounts] ⏱️ Timeout detected in result, starting polling...');
      
      const pollResult = await handleBulkTimeout(
        { idempotencyKey: result.idempotencyKey },
        [endpoints.accounts, '/activities/', '/opportunities/', '/contacts/'],
        onSyncProgress,
        onSyncComplete
      );
      
      if (pollResult?.status === 'succeeded') {
        // Backend stores: { data: {...}, http_status: 200 }
        // We need to unwrap .data to get the actual result
        const actualResult = pollResult.result?.data || pollResult.result || {};
        return {
          success: true,
          ...actualResult
        };
      }
      
      return {
        success: false,
        isTimeout: true,
        isPending: pollResult?.status === 'still_running',
        message: pollResult?.error || 'Operation may have completed in background',
        summary: { total: accounts?.length ?? 0, success: 0, failed: 0, skipped: 0 },
        results: { success: [], failed: [], skipped: [] }
      };
    }

    // ❌ Gestion d'erreur
    const status = result.status || 0;
    const message = result.error || 'Bulk create failed';
    console.error('[bulkCreateAccounts] api.post error', { status, message });

    if (result.data && typeof result.data === 'object') {
      if (result.data.results || result.data.summary) {
        console.log('[bulkCreateAccounts] returning structured error from backend');
        return {
          ...result.data,
          success: false,
          isTimeout: result.isTimeout || false
        };
      }
    }

    return {
      success: false,
      isTimeout: result.isTimeout || false, 
      message: message,
      error: { status, message, response: result.response || null },
      summary: { total: accounts?.length ?? 0, success: 0, failed: accounts?.length ?? 0, skipped: 0 },
      results: {
        success: [],
        failed: (accounts || []).map((a, i) => ({
          row: i + 1,
          company_name: a?.company_name || '(unknown)',
          errors: [message]
        })),
        skipped: []
      }
    };

  } catch (err) {
    console.error('[bulkCreateAccounts] thrown', err);
    
    const isTimeout = 
      err?.code === 'ECONNABORTED' || 
      err?.message?.toLowerCase()?.includes('timeout') ||
      err?.response?.status === 408 ||
      err?.response?.status === 504;
    
    if (isTimeout) {
      console.log('[bulkCreateAccounts] ⏱️ Timeout detected, starting polling...');
      
      const pollResult = await handleBulkTimeout(
        err,
        [endpoints.accounts, '/activities/', '/opportunities/', '/contacts/'],
        onSyncProgress,
        onSyncComplete
      );
      
      if (pollResult?.status === 'succeeded') {
        const actualResult = pollResult.result?.data || pollResult.result || {};
        return {
          success: true,
          ...actualResult
        };
      }
      
      return {
        success: false,
        isTimeout: true,
        isPending: pollResult?.status === 'still_running',
        message: pollResult?.error || 'Operation may have completed in background',
        summary: { total: accounts?.length ?? 0, success: 0, failed: 0, skipped: 0 },
        results: { success: [], failed: [], skipped: [] }
      };
    }
    
    return {
      success: false,
      isTimeout: false,
      message: err?.message || 'Unknown error',
      error: { message: err?.message || String(err) },
      summary: { total: accounts?.length ?? 0, success: 0, failed: accounts?.length ?? 0, skipped: 0 },
      results: {
        success: [],
        failed: (accounts || []).map((a, i) => ({
          row: i + 1,
          company_name: a?.company_name || '(unknown)',
          errors: [err?.message || 'Unknown error']
        })),
        skipped: []
      }
    };
  }
};