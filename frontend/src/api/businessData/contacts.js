// frontend/src/api/businessData/contacts.js

import useSWR from 'swr';
import { useMemo } from 'react';
import { useAuth } from 'hooks/useAuth';
import { api } from 'utils/axiosClient';
import { tenantKey, revalidateMultiple, handleBulkRevalidation, handleBulkTimeout } from 'api/_swr';
import { isValidUUID, sanitizeObject } from 'utils/validators';

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  contacts: '/contacts/',
  contactDetail: (id) => `/contacts/${id}/`,
  choices: '/contacts/choices/',
  bulkCreate: '/contacts/bulk-create/',
  bulkUpdate: '/contacts/bulk-update/',
  bulkDelete: '/contacts/bulk-delete/',
  markEmailInvalid: (id) => `/contacts/${id}/mark-email-invalid/`,
  markPhoneInvalid: (id) => `/contacts/${id}/mark-phone-invalid/`,
  markOptedOut: (id) => `/contacts/${id}/mark-opted-out/`
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

  // Account filter
  if (filters.account_id) {
    queryParams.append('account_id', filters.account_id);
  }

  // Company owner filter — a contact's owner is its company account's owner.
  // Used by CONTACT territories scoped to "Company's Owner = me".
  if (filters.account_owner_id) {
    queryParams.append('account_owner_id', filters.account_owner_id);
  }

  // Influence level filter
  if (filters.influence_level) {
    queryParams.append('influence_level', filters.influence_level);
  }

  // Department filter
  if (filters.standard_department) {
    queryParams.append('standard_department', filters.standard_department);
  }

  // Status filters
  if (filters.is_primary !== undefined && filters.is_primary !== null) {
    queryParams.append('is_primary', filters.is_primary);
  }

  if (filters.opted_out !== undefined && filters.opted_out !== null) {
    queryParams.append('opted_out', filters.opted_out);
  }

  if (filters.email_is_valid !== undefined && filters.email_is_valid !== null) {
    queryParams.append('email_is_valid', filters.email_is_valid);
  }

  if (filters.phone_is_valid !== undefined && filters.phone_is_valid !== null) {
    queryParams.append('phone_is_valid', filters.phone_is_valid);
  }

  if (filters.has_buying_authority !== undefined && filters.has_buying_authority !== null) {
    queryParams.append('has_buying_authority', filters.has_buying_authority);
  }

  // Job title filter
  if (filters.job_title) {
    queryParams.append('job_title', filters.job_title);
  }
  
  const queryString = queryParams.toString();
  return queryString ? `${baseUrl}?${queryString}` : baseUrl;
};

// ==============================|| READ HOOKS ||============================== //

/**
 * GET CONTACTS - Paginated list with filters
 * 
 * @param {Object|null} options - {page, pageSize, search, ordering, filters}. Pass null to skip fetch.
 * @returns {Object} {contacts, contactsCount, contactsLoading, contactsError, contactsValidating, contactsEmpty}
 */
export function useGetContacts(options = {}) {
  const { tenantId } = useAuth();

  // null options = skip fetch (modal closed, component not active)
  const enabled = options !== null;
  const { page = 1, pageSize = 10, search = '', ordering = '', filters = {} } = options || {};

  const urlWithParams = useMemo(() => {
    if (!enabled) return null;
    return buildUrlWithParams(endpoints.contacts, { page, pageSize, search, ordering, filters });
  }, [enabled, page, pageSize, search, ordering, filters]);

  const swrKey = urlWithParams ? tenantKey(urlWithParams, tenantId) : null;

  const { data, isLoading, error, isValidating } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      contacts: data?.data?.results || data?.results || [],
      contactsCount: data?.data?.count || data?.count || 0,
      contactsLoading: enabled ? isLoading : false,
      contactsError: error,
      contactsValidating: isValidating,
      contactsEmpty: !isLoading && !(data?.data?.results?.length || data?.results?.length)
    }),
    [data, isLoading, error, isValidating]
  );

  return memoizedValue;
}

/**
 * GET CONTACT - Single contact details
 * 
 * @param {string} contactId - UUID of the contact
 * @returns {Object} {contact, contactLoading, contactError, contactValidating}
 */
export function useGetContact(contactId) {
  const { tenantId } = useAuth();

  const swrKey = useMemo(() => {
    if (!contactId || !isValidUUID(contactId)) return null;
    return tenantKey(endpoints.contactDetail(contactId), tenantId);
  }, [contactId, tenantId]);

  const { data, isLoading, error, isValidating } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      contact: data?.data || data || null,
      contactLoading: isLoading,
      contactError: error,
      contactValidating: isValidating
    }),
    [data, isLoading, error, isValidating]
  );

  return memoizedValue;
}

/**
 * GET CONTACT CHOICES - Influence levels, Standard departments
 * 
 * @returns {Object} {choices, influenceLevels, standardDepartments, choicesLoading, choicesError}
 */
export function useGetContactChoices() {
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
      influenceLevels: data?.data?.influence_levels || data?.influence_levels || [],
      standardDepartments: data?.data?.standard_departments || data?.standard_departments || [],
      choicesLoading: isLoading,
      choicesError: error
    }),
    [data, isLoading, error]
  );

  return memoizedValue;
}

// ==============================|| MUTATION FUNCTIONS ||============================== //

/**
 * CREATE CONTACT - Insert new contact
 * 
 * @param {Object} payload - Contact data
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function createContact(payload) {
  const sanitized = sanitizeObject(payload, ['first_name', 'last_name', 'email', 'job_title', 'notes']);
  
  const result = await api.post(endpoints.contacts, sanitized);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.contacts,
      '/company-accounts/'
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
 * UPDATE CONTACT - Modify existing contact
 * 
 * @param {string} contactId - UUID of the contact
 * @param {Object} payload - Contact data to update
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function updateContact(contactId, payload) {
  if (!contactId || !isValidUUID(contactId)) {
    return { success: false, error: 'Invalid contact ID' };
  }
  
  const sanitized = sanitizeObject(payload, ['first_name', 'last_name', 'email', 'job_title', 'notes']);
  
  const result = await api.patch(endpoints.contactDetail(contactId), sanitized);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.contacts,
      endpoints.contactDetail(contactId),
      '/company-accounts/'
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
 * DELETE CONTACT - Remove contact
 * 
 * @param {string} contactId - UUID of the contact
 * @returns {Promise<Object>} {success: boolean, error?: string}
 */
export async function deleteContact(contactId) {
  if (!contactId || !isValidUUID(contactId)) {
    return { success: false, error: 'Invalid contact ID' };
  }
  
  const result = await api.delete(endpoints.contactDetail(contactId));
  
  if (result.success) {
    revalidateMultiple([
      endpoints.contacts,
      '/company-accounts/'
    ]);
    return { success: true };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0
  };
}

// ==============================|| CONTACT ACTIONS ||============================== //

/**
 * MARK EMAIL INVALID - Mark contact email as invalid
 * 
 * @param {string} contactId - UUID of the contact
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function markEmailInvalid(contactId) {
  if (!contactId || !isValidUUID(contactId)) {
    return { success: false, error: 'Invalid contact ID' };
  }
  
  const result = await api.post(endpoints.markEmailInvalid(contactId));
  
  if (result.success) {
    revalidateMultiple([
      endpoints.contacts,
      endpoints.contactDetail(contactId)
    ]);
    return { success: true, data: result.data };
  }
  
  return { success: false, error: result.error };
}

/**
 * MARK PHONE INVALID - Mark contact phone as invalid
 * 
 * @param {string} contactId - UUID of the contact
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function markPhoneInvalid(contactId) {
  if (!contactId || !isValidUUID(contactId)) {
    return { success: false, error: 'Invalid contact ID' };
  }
  
  const result = await api.post(endpoints.markPhoneInvalid(contactId));
  
  if (result.success) {
    revalidateMultiple([
      endpoints.contacts,
      endpoints.contactDetail(contactId)
    ]);
    return { success: true, data: result.data };
  }
  
  return { success: false, error: result.error };
}

/**
 * MARK OPTED OUT - Mark contact as opted out
 * 
 * @param {string} contactId - UUID of the contact
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function markOptedOut(contactId) {
  if (!contactId || !isValidUUID(contactId)) {
    return { success: false, error: 'Invalid contact ID' };
  }
  
  const result = await api.post(endpoints.markOptedOut(contactId));
  
  if (result.success) {
    revalidateMultiple([
      endpoints.contacts,
      endpoints.contactDetail(contactId)
    ]);
    return { success: true, data: result.data };
  }
  
  return { success: false, error: result.error };
}

// ==============================|| BULK OPERATIONS ||============================== //

/**
 * BULK CREATE CONTACTS
 * 
 * @param {Array} contacts - Array of contact objects
 * @param {string} onConflict - 'skip' | 'update' | 'fail'
 * @param {Function} onSyncProgress - Progress callback
 * @param {Function} onSyncComplete - Complete callback
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function bulkCreateContacts(contacts, onConflict = 'skip', onSyncProgress = null, onSyncComplete = null) {
  const payload = {
    contacts,
    on_conflict: onConflict
  };
  
  try {
    const result = await api.post(endpoints.bulkCreate, payload);
    
    if (result.success) {
      handleBulkRevalidation([endpoints.contacts, '/company-accounts/']);
      return { success: true, data: result.data };
    }
    
    return { 
      success: false, 
      error: result.error,
      status: result.status || 0,
      response: result.response || null
    };
  } catch (err) {
    // Handle timeout with polling
    if (err?.code === 'ECONNABORTED' || err?.message?.includes('timeout')) {
      return handleBulkTimeout(err, [endpoints.contacts], onSyncProgress, onSyncComplete);
    }
    throw err;
  }
}

/**
 * BULK UPDATE CONTACTS
 * 
 * @param {Array} updates - Array of {id, ...fields}
 * @param {string} onMissing - 'skip' | 'fail'
 * @param {Function} onSyncProgress - Progress callback
 * @param {Function} onSyncComplete - Complete callback
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function bulkUpdateContacts(updates, onMissing = 'skip', onSyncProgress = null, onSyncComplete = null) {
  const payload = {
    contacts: updates,
    on_missing: onMissing
  };
  
  try {
    const result = await api.patch(endpoints.bulkUpdate, payload);
    
    if (result.success) {
      handleBulkRevalidation([endpoints.contacts, '/company-accounts/']);
      return { success: true, data: result.data };
    }
    
    return { 
      success: false, 
      error: result.error,
      status: result.status || 0,
      response: result.response || null
    };
  } catch (err) {
    if (err?.code === 'ECONNABORTED' || err?.message?.includes('timeout')) {
      return handleBulkTimeout(err, [endpoints.contacts], onSyncProgress, onSyncComplete);
    }
    throw err;
  }
}

/**
 * BULK DELETE CONTACTS
 * 
 * @param {Array} contactIds - Array of contact UUIDs
 * @param {string} onMissing - 'skip' | 'partial' | 'fail'
 * @param {Function} onSyncProgress - Progress callback
 * @param {Function} onSyncComplete - Complete callback
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function bulkDeleteContacts(contactIds, onMissing = 'partial', onSyncProgress = null, onSyncComplete = null) {
  const payload = {
    ids: contactIds,
    on_missing: onMissing
  };
  
  try {
    const result = await api.delete(endpoints.bulkDelete, { data: payload });
    
    if (result.success) {
      handleBulkRevalidation([endpoints.contacts, '/company-accounts/']);
      return { success: true, data: result.data };
    }
    
    return { 
      success: false, 
      error: result.error,
      status: result.status || 0,
      response: result.response || null
    };
  } catch (err) {
    if (err?.code === 'ECONNABORTED' || err?.message?.includes('timeout')) {
      return handleBulkTimeout(err, [endpoints.contacts], onSyncProgress, onSyncComplete);
    }
    throw err;
  }
}