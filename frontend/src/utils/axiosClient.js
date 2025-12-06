// frontend/src/utils/axiosClient.js

import axios from 'axios';
import { authConfig, debugLog } from '../config/auth';
import { handleApiError } from '../utils/errorHandler';
import { safeConsole } from './logSanitizer';

// ==============================|| SINGLE-FLIGHT REFRESH PATTERN ||============================== //

/**
 * Single-flight pattern for token refresh
 * Ensures only ONE refresh happens at a time
 * Multiple concurrent 401s wait for same refresh and retry
 */
let refreshPromise = null;
const subscriberQueue = [];

/**
 * Called when refresh succeeds - retries all queued requests
 */
function onRefreshed() {
  subscriberQueue.splice(0).forEach(({ resolve }) => resolve());
}

/**
 * Called when refresh fails - rejects all queued requests
 */
function onRefreshFailed(error) {
  subscriberQueue.splice(0).forEach(({ reject }) => reject(error));
}

// ==============================|| CORRELATION ID GENERATOR ||============================== //

/**
 * Generate unique correlation ID for request tracing
 */
const generateCorrelationId = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

// ==============================|| RETRY-AFTER PARSER ||============================== //

/**
 * Parse Retry-After header (seconds or HTTP date)
 */
const parseRetryAfter = (retryAfter) => {
  if (!retryAfter) return 0;

  // Case 1: Integer (seconds)
  const seconds = parseInt(retryAfter, 10);
  if (!isNaN(seconds) && seconds > 0) {
    return seconds * 1000;
  }

  // Case 2: HTTP date string
  try {
    const retryDate = new Date(retryAfter);
    if (!isNaN(retryDate.getTime())) {
      const now = Date.now();
      const delay = retryDate.getTime() - now;
      return Math.max(0, delay);
    }
  } catch (e) {
    // Invalid date format
  }

  return 0;
};

// ==============================|| AXIOS CLIENT FACTORY ||============================== //

/**
 * axios client with specific timeout and profile
 * 
 * Factory pattern allows multiple clients with different timeout configurations
 * while sharing the same interceptor logic.
 * 
 * @param {number} timeout - Timeout in milliseconds
 * @param {string} profile - Profile name for logging (critical/widget/mutation/bulk/auth)
 * @returns {AxiosInstance} Configured axios instance
 */
function createAxiosClient(timeout, profile = 'default') {
  const client = axios.create({
    baseURL: authConfig.API_BASE_URL,
    timeout,
    headers: {
      'Content-Type': 'application/json',
    },
    withCredentials: true,

    // ✅ Security: DoS protection via data size limits (CVE-2024-39338)
    maxContentLength: 50 * 1024 * 1024,  // 50MB response limit
    maxBodyLength: 10 * 1024 * 1024,      // 10MB request limit
  });

  // Attach interceptors to this client
  addInterceptorsToClient(client, profile);

  return client;
}

/**
 * request and response interceptors to an axios client
 * 
 * Factorized interceptor logic to avoid duplication across multiple clients.
 * Handles:
 * - Correlation ID generation
 * - Performance tracking
 * - 401 auto-refresh
 * - Timeout detection and enrichment
 * - 429 Retry-After parsing
 * 
 * @param {AxiosInstance} client - Axios client to enhance
 * @param {string} profile - Profile name for logging
 */
function addInterceptorsToClient(client, profile) {
  // ==============================|| REQUEST INTERCEPTOR ||============================== //
  
  client.interceptors.request.use(
    (config) => {
      // Generate and attach correlation ID
      const correlationId = generateCorrelationId();
      config.headers['X-Correlation-ID'] = correlationId;

      // POST/PATCH/DELETE requests get automatic idempotency protection
      const method = config.method?.toUpperCase();
        if (['POST', 'PATCH', 'DELETE'].includes(method)) {
          // Only inject if not already provided (allow manual override)
          if (!config.headers['Idempotency-Key']) {
            const idempotencyKey = generateCorrelationId(); // Use same UUID generator
            config.headers['Idempotency-Key'] = idempotencyKey;
            
            if (process.env.NODE_ENV === 'development') {
              debugLog(
                `🔑 [${correlationId.slice(0, 8)}] Auto-injected Idempotency-Key: ${idempotencyKey.slice(0, 8)}...`
              );
            }
          }
      }
      
      config.metadata = {
        correlationId,
        startTime: performance.now(),
        profile,
        idempotencyKey: config.headers['Idempotency-Key']
      };
      
      if (process.env.NODE_ENV === 'development') {
        debugLog(
          `🚀 [${correlationId.slice(0, 8)}] [${profile.toUpperCase()}] API Request: ${config.method?.toUpperCase()} ${config.url}`
        );
      }
      
      return config;
    },
    (error) => {
      safeConsole.error('❌ Request interceptor error:', error);
      return Promise.reject(error);
    }
  );

  // ==============================|| RESPONSE INTERCEPTOR ||============================== //
  
  client.interceptors.response.use(
    (response) => {
      const correlationId = response.config.metadata?.correlationId || 'unknown';
      const startTime = response.config.metadata?.startTime;
      const requestProfile = response.config.metadata?.profile || 'unknown';
      
      let duration = 0;
      if (startTime) {
        duration = performance.now() - startTime;
      }

      // ==============================
      // ✅ STEP 6: HANDLE 202 ACCEPTED - ASYNC OPERATION
      // ==============================
      
      if (response.status === 202) {
        const pollUrl = response.data?.poll_url;
        const retryAfterHeader = response.headers?.['retry-after'];
        const idempotencyKey = response.config.metadata?.idempotencyKey;
        
        if (process.env.NODE_ENV === 'development') {
          debugLog(
            `📨 [${correlationId.slice(0, 8)}] [${requestProfile.toUpperCase()}] 202 ACCEPTED: ${response.config.url}`
          );
          debugLog(
            `   poll_url: ${pollUrl || 'N/A'}, Retry-After: ${retryAfterHeader || 'N/A'}`
          );
        }
        
        // Enrich response.data with polling metadata
        // This allows handleBulkRevalidation() to detect 202 and trigger polling
        response.data.__is202 = true;
        response.data.__poll_url = pollUrl;
        response.data.__idempotency_key = idempotencyKey;
        
        // Parse and attach Retry-After hint
        if (retryAfterHeader) {
          const retryAfterMs = parseRetryAfter(retryAfterHeader);
          response.data.__retry_after_ms = retryAfterMs;
          
          if (process.env.NODE_ENV === 'development') {
            debugLog(
              `   Retry-After parsed: ${retryAfterMs}ms (${(retryAfterMs / 1000).toFixed(1)}s)`
            );
          }
        }
        
        if (process.env.NODE_ENV === 'development') {
          debugLog(
            `   Enriched with: __is202=true, __idempotency_key=${idempotencyKey?.slice(0, 8)}...`
          );
        }
      }
      
      if (process.env.NODE_ENV === 'development') {
        debugLog(
          `✅ [${correlationId.slice(0, 8)}] [${requestProfile.toUpperCase()}] API Response: ${response.status} ${response.config.url} (${duration.toFixed(0)}ms)`
        );
      }
      
      return response;
    },
    async (error) => {
      const correlationId = error?.config?.metadata?.correlationId || 'unknown';
      const startTime = error?.config?.metadata?.startTime;
      const requestProfile = error?.config?.metadata?.profile || 'unknown';
      const status = error?.response?.status;
      const url = error?.config?.url;
      const originalRequest = error.config;
      
      let duration = 0;
      if (startTime) {
        duration = performance.now() - startTime;
      }

      // ==============================
      // HANDLE 401 UNAUTHORIZED - AUTO REFRESH TOKEN
      // ==============================
      
      // Check if this is a refresh endpoint call (prevent infinite loop)
      const isRefreshCall = url?.includes('/client/refresh-token/');
      
      // Only attempt refresh if:
      // 1. Status is 401
      // 2. Not already retried
      // 3. Not the refresh endpoint itself
      if (status === 401 && !originalRequest._retry && !isRefreshCall) {
        originalRequest._retry = true;
        
        // If a refresh is already in progress, queue this request
        if (refreshPromise) {
          if (process.env.NODE_ENV === 'development') {
            debugLog(
              `⏸️ [${correlationId.slice(0, 8)}] 401 - Queuing request (refresh in progress)`
            );
          }
          
          return new Promise((resolve, reject) => {
            subscriberQueue.push({
              resolve: () => {
                if (process.env.NODE_ENV === 'development') {
                  debugLog(
                    `🔁 [${correlationId.slice(0, 8)}] Retrying after refresh: ${originalRequest.method?.toUpperCase()} ${originalRequest.url}`
                  );
                }
                resolve(client(originalRequest));
              },
              reject,
            });
          });
        }
        
        // Start a new refresh
        try {
          if (process.env.NODE_ENV === 'development') {
            debugLog(
              `🔄 [${correlationId.slice(0, 8)}] 401 - Starting token refresh`
            );
          }
          
          // Import refreshTokens dynamically to avoid circular dependency
          const { refreshTokens } = await import('../api/auth');
          
          refreshPromise = refreshTokens();
          const refreshResult = await refreshPromise;
          
          if (!refreshResult.success) {
            // Store shouldLogout flag before throwing
            const shouldTriggerLogout = refreshResult.shouldLogout === true;
            const errorMessage = refreshResult.error || 'Token refresh failed';
            
            const error = new Error(errorMessage);
            error.shouldLogout = shouldTriggerLogout;
            throw error;
          }
          
          // Refresh succeeded - notify all queued requests
          onRefreshed();
          
          if (process.env.NODE_ENV === 'development') {
            debugLog(
              `✅ [${correlationId.slice(0, 8)}] Token refresh successful, retrying original request`
            );
          }
          
          return client(originalRequest);
          
        } catch (refreshError) {
          // Refresh failed - notify all queued requests
          onRefreshFailed(refreshError);
          
          if (process.env.NODE_ENV === 'development') {
            debugLog(
              `❌ [${correlationId.slice(0, 8)}] Token refresh failed: ${refreshError.message}`
            );
          }
          
          // Check if we should trigger hard logout or just stay in degraded mode
          const shouldTriggerLogout = refreshError.shouldLogout === true;
          
          if (shouldTriggerLogout) {
            if (process.env.NODE_ENV === 'development') {
              debugLog(
                `🚪 [${correlationId.slice(0, 8)}] Real session expiration - triggering logout`
              );
            }
            
            // Signal to the app that session has expired
            try {
              if (typeof window !== 'undefined') {
                window.dispatchEvent(new CustomEvent('auth:session-expired', {
                  detail: { error: 'Session expired. Please sign in again.' }
                }));
              }
            } catch (e) {
              safeConsole.error('Failed to dispatch session-expired event:', e);
            }
          } else {
            if (process.env.NODE_ENV === 'development') {
              debugLog(
                `⚠️ [${correlationId.slice(0, 8)}] Network error during refresh - no logout, degraded mode`
              );
            }
          }
          
          return Promise.reject(error);
          
        } finally {
          refreshPromise = null;
        }
      }

      // ==============================
      // HANDLE TIMEOUT
      // ==============================

      const isTimeout = 
        error.code === 'ECONNABORTED' || 
        error.code === 'ETIMEDOUT' ||
        (error.message && error.message.toLowerCase().includes('timeout'));
      
      if (isTimeout) {
        error.isTimeout = true;

        const idempotencyKey = error?.config?.headers?.['Idempotency-Key'];
        if (idempotencyKey) {
          error.idempotencyKey = idempotencyKey;
        }

        if (!error.response) {
          error.response = {
            status: 408,
            data: { 
              error: 'Request timeout. The operation took too long to complete.',
              detail: 'Request timeout. The operation took too long to complete.'
            },
            statusText: 'Request Timeout'
          };
        }
        
        if (process.env.NODE_ENV === 'development') {
          debugLog(
            `⏱️ [${correlationId.slice(0, 8)}] [${requestProfile.toUpperCase()}] TIMEOUT: ${url ?? '—'} (${duration.toFixed(0)}ms)`
          );
        }
      }
      
      // ==============================
      // HANDLE 429 RATE LIMIT
      // ==============================
      
      if (status === 429) {
        // ✅ STEP 3.1: Add explicit rate limit flag for consistency with isTimeout
        error.isRateLimited = true;
        
        const retryAfter = error?.response?.headers?.['retry-after'];
        
        if (retryAfter) {
          const retryAfterMs = parseRetryAfter(retryAfter);
          
          if (retryAfterMs > 0) {
            error.retryAfterMs = retryAfterMs;
            
            if (process.env.NODE_ENV === 'development') {
              debugLog(
                `⏱️ [${correlationId.slice(0, 8)}] Rate limited: retry after ${(retryAfterMs / 1000).toFixed(1)}s`
              );
            }
          } else if (process.env.NODE_ENV === 'development') {
            debugLog(
              `⚠️ [${correlationId.slice(0, 8)}] Invalid Retry-After value: "${retryAfter}"`
            );
            error.retryAfterMs = 5000;
          }
        } else {
          if (process.env.NODE_ENV === 'development') {
            debugLog(
              `⚠️ [${correlationId.slice(0, 8)}] 429 response missing Retry-After header, using 5s default`
            );
          }
          error.retryAfterMs = 5000;
        }
      }
      
      if (process.env.NODE_ENV === 'development') {
        debugLog(
          `❌ [${correlationId.slice(0, 8)}] [${requestProfile.toUpperCase()}] API Error: ${status ?? '—'} ${url ?? '—'} (${duration.toFixed(0)}ms)`
        );
      }
      
      return Promise.reject(error);
    }
  );
}

// ==============================|| AXIOS CLIENTS WITH TIMEOUT PROFILES ||============================== //

/**
 * ✅ NEW: Multiple axios clients with differentiated timeout profiles
 * 
 * Each client has its own timeout configuration optimized for specific use cases:
 * - critical: Main data fetching (users, accounts, contacts) - 8s
 * - widget: Dashboard widgets, quick stats - 4s
 * - mutation: Form submissions, CRUD operations - 10s
 * - bulk: Import/export, bulk operations - 60s
 * - auth: Login, token refresh - 5s (faster fail for auth issues)
 * 
 * All clients share the same interceptor logic (401 refresh, 429 handling, etc.)
 */
export const axiosClients = {
  critical: createAxiosClient(authConfig.TIMEOUT_PROFILES.CRITICAL, 'critical'),
  widget: createAxiosClient(authConfig.TIMEOUT_PROFILES.WIDGET, 'widget'),
  mutation: createAxiosClient(authConfig.TIMEOUT_PROFILES.MUTATION, 'mutation'),
  bulk: createAxiosClient(authConfig.TIMEOUT_PROFILES.BULK, 'bulk'),
  auth: createAxiosClient(authConfig.TIMEOUT_PROFILES.AUTH, 'auth')
};

// ==============================|| DEFAULT AXIOS CLIENT (BACKWARD COMPATIBILITY) ||============================== //

/**
 * @deprecated Use axiosClients.mutation or specific profile instead
 * 
 * Legacy default client kept for backward compatibility with existing code.
 * Uses mutation profile (10s timeout) as it was the original REQUEST_TIMEOUT value.
 */
const axiosClient = createAxiosClient(authConfig.REQUEST_TIMEOUT, 'default');

// ==============================|| HELPER FUNCTIONS ||============================== //

/**
 * Wrapper for requests with automatic error handling
 */
export const apiRequest = async (requestFn) => {
  try {
    const response = await requestFn();
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    const errorMessage = handleApiError(error);

    let status = 0;
    
    if (error.isTimeout) {
      status = 408;
    } else if (error.response?.status) {
      status = error.response.status;
    }
    
    if (process.env.NODE_ENV === 'development') {
      safeConsole.error('❌ API Request failed:', errorMessage);
    }
    
    const result = {
      success: false,
      data: error.response?.data || null,
      error: errorMessage,
      status: error.response?.status || 0,
      response: error.response || null
    };
    
    if (error.isTimeout) {
      result.isTimeout = true;
    }
    
    // Propagate idempotency key for timeout polling
    if (error.idempotencyKey) {
      result.idempotencyKey = error.idempotencyKey;
    }
    //  Propagate isRateLimited flag to result object
    if (error.isRateLimited) {
      result.isRateLimited = true;
    }
    
    if (error.retryAfterMs) {
      result.retryAfterMs = error.retryAfterMs;
    }
    
    return result;
  }
};

// ==============================|| PROFILE DETECTION ||============================== //

/**
 * ✅ NEW: Detect appropriate profile based on HTTP method and URL
 * 
 * Smart defaults:
 * - GET: 'critical' (main data fetching)
 * - POST/PUT/PATCH/DELETE: 'mutation' (form submissions)
 * - URLs with '/bulk-': 'bulk' (override any default)
 * 
 * @param {string} method - HTTP method (GET, POST, etc.)
 * @param {string} url - Request URL
 * @param {string} explicitProfile - Explicitly provided profile (takes precedence)
 * @returns {string} Profile name to use
 */
function detectProfile(method, url, explicitProfile) {
  // Explicit profile always takes precedence
  if (explicitProfile) {
    return explicitProfile;
  }

  // Auto-detect bulk operations by URL pattern
  if (url && (url.includes('/bulk-') || url.includes('/bulk/'))) {
    return 'bulk';
  }

  // Default by HTTP method
  const upperMethod = method?.toUpperCase();
  
  if (upperMethod === 'GET') {
    return 'critical';
  }
  
  // POST, PUT, PATCH, DELETE → mutation
  return 'mutation';
}

/**
 * ✅ NEW: Select appropriate axios client based on profile
 * 
 * @param {string} profile - Profile name
 * @returns {AxiosInstance} Axios client instance
 */
function selectClient(profile) {
  const client = axiosClients[profile];
  
  if (!client) {
    if (process.env.NODE_ENV === 'development') {
      safeConsole.warn(`⚠️ Unknown profile "${profile}", falling back to mutation client`);
    }
    return axiosClients.mutation;
  }
  
  return client;
}

// ==============================|| EXPORTS ||============================== //

export default axiosClient;

/**
 * ✅ UPDATED: Convenience methods with profile-aware timeout handling
 * 
 * Usage:
 *   api.get(url)                          // Uses 'critical' profile (8s)
 *   api.get(url, { profile: 'widget' })   // Uses 'widget' profile (4s)
 *   api.post(url, data)                   // Uses 'mutation' profile (10s)
 *   api.post(url, data, { profile: 'bulk' }) // Uses 'bulk' profile (60s)
 * 
 * Auto-detection:
 *   api.get('/bulk-delete')               // Auto-detects 'bulk' profile
 *   api.post('/client/bulk-create/', {})  // Auto-detects 'bulk' profile
 */
export const api = {
  /**
   * GET request with profile-aware timeout
   * Default: 'critical' profile (8s)
   * Override: { profile: 'widget' } for 4s timeout
   */
  get: (url, config = {}) => {
    const profile = detectProfile('GET', url, config.profile);
    const client = selectClient(profile);
    
    // Remove profile from config to avoid passing it to axios
    const { profile: _removed, ...axiosConfig } = config;
    
    return apiRequest(() => client.get(url, axiosConfig));
  },

  /**
   * POST request with profile-aware timeout
   * Default: 'mutation' profile (10s)
   * Override: { profile: 'bulk' } for 60s timeout
   */
  post: (url, data = {}, config = {}) => {
    const profile = detectProfile('POST', url, config.profile);
    const client = selectClient(profile);
    
    // Remove profile from config to avoid passing it to axios
    const { profile: _removed, ...axiosConfig } = config;
    
    return apiRequest(() => client.post(url, data, axiosConfig));
  },

  /**
   * PUT request with profile-aware timeout
   * Default: 'mutation' profile (10s)
   */
  put: (url, data = {}, config = {}) => {
    const profile = detectProfile('PUT', url, config.profile);
    const client = selectClient(profile);
    
    // Remove profile from config to avoid passing it to axios
    const { profile: _removed, ...axiosConfig } = config;
    
    return apiRequest(() => client.put(url, data, axiosConfig));
  },

  /**
   * PATCH request with profile-aware timeout
   * Default: 'mutation' profile (10s)
   */
  patch: (url, data = {}, config = {}) => {
    const profile = detectProfile('PATCH', url, config.profile);
    const client = selectClient(profile);
    
    // Remove profile from config to avoid passing it to axios
    const { profile: _removed, ...axiosConfig } = config;
    
    return apiRequest(() => client.patch(url, data, axiosConfig));
  },

  /**
   * DELETE request with profile-aware timeout
   * Default: 'mutation' profile (10s)
   * Override: { profile: 'bulk' } for bulk delete operations
   */
  delete: (url, config = {}) => {
    const profile = detectProfile('DELETE', url, config.profile);
    const client = selectClient(profile);
    
    // Remove profile from config to avoid passing it to axios
    const { profile: _removed, ...axiosConfig } = config;
    
    return apiRequest(() => client.delete(url, axiosConfig));
  }
};