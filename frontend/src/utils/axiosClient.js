// frontend/src/utils/axiosClient.js

import axios from 'axios';
import { authConfig, debugLog } from '../config/auth';
import { handleApiError } from '../utils/errorHandler';
import { safeConsole } from './logSanitizer';

// ==============================|| SINGLE-FLIGHT REFRESH PATTERN ||============================== //

/**
 * ✅ SINGLE-FLIGHT PATTERN
 * 
 * Ensures only ONE token refresh happens at a time.
 * Multiple concurrent 401s will wait for the same refresh and then retry.
 * 
 * This prevents:
 * - Multiple simultaneous refresh calls
 * - Race conditions on token rotation
 * - Backend throttling on refresh endpoint
 */

let refreshPromise = null; // Tracks the ongoing refresh operation
const subscriberQueue = []; // Queue of requests waiting for refresh

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


// ==============================|| CENTRAL AXIOS CLIENT ||============================== //

/**
 * ✅ AXIOS CLIENT CENTRAL WITH CORRELATION IDs
 * 
 * Features:
 * - HTTP-only cookies automatic (withCredentials: true)  
 * - Auto-refresh on 401 (single retry, no infinite loops)
 * - Uses existing handleApiError for backend messages
 * - 🔒 PII sanitization on all logs
 * - 🔗 Correlation ID for distributed tracing
 * -  Retry-After header support for 429 responses
 * 
 * @module utils/axiosClient
 */

const axiosClient = axios.create({
  baseURL: authConfig.API_BASE_URL,
  timeout: authConfig.REQUEST_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Essential for HTTP-only cookies
});

// ==============================|| CORRELATION ID GENERATOR ||============================== //

/**
 * Generate unique correlation ID for request tracing
 * Uses crypto.randomUUID() with fallback for older browsers
 * 
 * @returns {string} UUID v4
 */
const generateCorrelationId = () => {
  // Modern browsers (preferred)
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  
  // Fallback for older browsers
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

// ==============================|| RETRY-AFTER PARSER ||============================== //

/**
 * Parse Retry-After header
 * 
 * The Retry-After header can be either:
 * - An integer (seconds to wait)
 * - An HTTP date string (absolute time)
 * 
 * @param {string} retryAfter - Value from Retry-After header
 * @returns {number} Delay in milliseconds, or 0 if invalid
 */
const parseRetryAfter = (retryAfter) => {
  if (!retryAfter) return 0;

  // Case 1: Integer (seconds)
  const seconds = parseInt(retryAfter, 10);
  if (!isNaN(seconds) && seconds > 0) {
    return seconds * 1000; // Convert to milliseconds
  }

  // Case 2: HTTP date string
  try {
    const retryDate = new Date(retryAfter);
    if (!isNaN(retryDate.getTime())) {
      const now = Date.now();
      const delay = retryDate.getTime() - now;
      return Math.max(0, delay); // Never negative
    }
  } catch (e) {
    // Invalid date format, fall through
  }

  // Fallback: invalid format
  return 0;
};

// ==============================|| REQUEST INTERCEPTOR ||============================== //

axiosClient.interceptors.request.use(
  (config) => {
    // 🔗 Generate and attach correlation ID
    const correlationId = generateCorrelationId();
    config.headers['X-Correlation-ID'] = correlationId;
    
    // Store for response logging
    config.metadata = {
      correlationId,
      startTime: performance.now()
    };
    
    // 🔒 Sanitized debug log with correlation ID
    if (process.env.NODE_ENV === 'development') {
      debugLog(
        `🚀 [${correlationId.slice(0, 8)}] API Request: ${config.method?.toUpperCase()} ${config.url}`
      );
    }
    
    return config;
  },
  (error) => {
    // 🔒 Sanitized error log
    safeConsole.error('❌ Request interceptor error:', error);
    return Promise.reject(error);
  }
);

// ==============================|| RESPONSE INTERCEPTOR ||============================== //

axiosClient.interceptors.response.use(
  (response) => {
    const correlationId = response.config.metadata?.correlationId || 'unknown';
    const startTime = response.config.metadata?.startTime;
    
    // Calculate request duration
    let duration = 0;
    if (startTime) {
      duration = performance.now() - startTime;
    }
    
    // 🔒 Sanitized debug log with correlation ID and duration
    if (process.env.NODE_ENV === 'development') {
      debugLog(
        `✅ [${correlationId.slice(0, 8)}] API Response: ${response.status} ${response.config.url} (${duration.toFixed(0)}ms)`
      );
    }
    
    return response;
  },
   async (error) => {
    const correlationId = error?.config?.metadata?.correlationId || 'unknown';
    const startTime = error?.config?.metadata?.startTime;
    const status = error?.response?.status;
    const url = error?.config?.url;
    const originalRequest = error.config;
    
    // Calculate request duration
    let duration = 0;
    if (startTime) {
      duration = performance.now() - startTime;
    }

    // ==============================
    // 🔄 HANDLE 401 UNAUTHORIZED - AUTO REFRESH TOKEN
    // ==============================
    
    // Check if this is a refresh endpoint call (prevent infinite loop)
    const isRefreshCall = url?.includes('/client/refresh-token/');
    
    // Only attempt refresh if:
    // 1. Status is 401
    // 2. Not already retried (prevent double refresh)
    // 3. Not the refresh endpoint itself
    if (status === 401 && !originalRequest._retry && !isRefreshCall) {
      originalRequest._retry = true; // Mark as retried
      
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
              resolve(axiosClient(originalRequest));
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
        
        // Create the refresh promise
        refreshPromise = refreshTokens();
        const refreshResult = await refreshPromise;
        
        if (!refreshResult.success) {
          throw new Error(refreshResult.error || 'Token refresh failed');
        }
        
        // Refresh succeeded - notify all queued requests
        onRefreshed();
        
        if (process.env.NODE_ENV === 'development') {
          debugLog(
            `✅ [${correlationId.slice(0, 8)}] Token refresh successful, retrying original request`
          );
        }
        
        // Retry the original request
        return axiosClient(originalRequest);
        
      } catch (refreshError) {
        // Refresh failed - notify all queued requests
        onRefreshFailed(refreshError);
        
        if (process.env.NODE_ENV === 'development') {
          debugLog(
            `❌ [${correlationId.slice(0, 8)}] Token refresh failed: ${refreshError.message}`
          );
        }
        
        // Import handleAuthError dynamically to trigger logout
        // This will stop the proactive timer and redirect to login
        try {
          // Signal to the app that session has expired
          // The app will handle logout via useAuth context
          if (typeof window !== 'undefined') {
            window.dispatchEvent(new CustomEvent('auth:session-expired', {
              detail: { error: 'Session expired. Please sign in again.' }
            }));
          }
        } catch (e) {
          // Fallback if event dispatch fails
          safeConsole.error('Failed to dispatch session-expired event:', e);
        }
        
        // Reject with original 401 error
        return Promise.reject(error);
        
      } finally {
        refreshPromise = null;
      }
    }

    // ==============================
    // ⏱️ HANDLE TIMEOUT
    // ==============================

    // Axios timeout errors have code 'ECONNABORTED' or message contains 'timeout'
    const isTimeout = 
      error.code === 'ECONNABORTED' || 
      error.code === 'ETIMEDOUT' ||
      (error.message && error.message.toLowerCase().includes('timeout'));
    
    if (isTimeout) {
      // Marquer l'erreur comme timeout avec status 408
      error.isTimeout = true;
      
      // Si pas de response, créer une pseudo-response avec status 408
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
          `⏱️ [${correlationId.slice(0, 8)}] TIMEOUT: ${url ?? '—'} (${duration.toFixed(0)}ms)`
        );
      }
    }
    
    if (status === 429) {
      // Axios normalizes headers to lowercase
      const retryAfter = error?.response?.headers?.['retry-after'];
      
      if (retryAfter) {
        const retryAfterMs = parseRetryAfter(retryAfter);
        
        if (retryAfterMs > 0) {
          // Attach parsed delay to error for SWR
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
          // Fallback: use minimal default
          error.retryAfterMs = 5000; // 5s default
        }
      } else {
        // Missing Retry-After header on 429
        if (process.env.NODE_ENV === 'development') {
          debugLog(
            `⚠️ [${correlationId.slice(0, 8)}] 429 response missing Retry-After header, using 5s default`
          );
        }
        error.retryAfterMs = 5000; // 5s default fallback
      }
    }
    
    // 🔒 Sanitized error log with correlation ID
    if (process.env.NODE_ENV === 'development') {
      debugLog(
        `❌ [${correlationId.slice(0, 8)}] API Error: ${status ?? '—'} ${url ?? '—'} (${duration.toFixed(0)}ms)`
      );
    }
    
    return Promise.reject(error);
  }
);

// ==============================|| HELPER FUNCTIONS ||============================== //

/**
 * ✅ WRAPPER FOR REQUESTS WITH AUTOMATIC ERROR HANDLING
 * @param {Function} requestFn - Axios request function
 * @returns {Promise<{success: boolean, data?: any, error?: string, status?: number, response?: Object}>}
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
    
    // 🔒 Sanitized error log
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
    
    // ✅ Si retryAfterMs existe sur l'erreur (ajouté par interceptor), le propager
    if (error.retryAfterMs) {
      result.retryAfterMs = error.retryAfterMs;
    }
    
    return result;
  }
};

// ==============================|| EXPORTS ||============================== //

export default axiosClient;

/**
 * Convenience methods with integrated error handling
 * All methods include correlation IDs automatically
 */
export const api = {
  get: (url, config = {}) => apiRequest(() => axiosClient.get(url, config)),
  post: (url, data = {}, config = {}) => apiRequest(() => axiosClient.post(url, data, config)),
  put: (url, data = {}, config = {}) => apiRequest(() => axiosClient.put(url, data, config)),
  patch: (url, data = {}, config = {}) => apiRequest(() => axiosClient.patch(url, data, config)),
  delete: (url, config = {}) => apiRequest(() => axiosClient.delete(url, config))
};