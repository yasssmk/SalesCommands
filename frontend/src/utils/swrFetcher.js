// frontend/src/utils/swrFetcher.js

/**
 * SWR Global Fetcher with Monitoring
 * 
 * Centralized fetcher for all SWR hooks in the application
 * with latency monitoring per endpoint.
 * 
 * @module utils/swrFetcher
 */

import { api } from 'utils/axiosClient';
import metricsCollector from 'utils/monitoring';

// ==============================|| ERROR HELPER ||============================== //

/**
 * Create an Error object that preserves the HTTP status code
 * This is crucial for error handling in components
 * 
 * @param {string} message - Error message
 * @param {number} status - HTTP status code
 * @param {Object} response - Optional response object
 * @returns {Error} Enhanced error with status
 */
const createApiError = (message, status, response = null) => {
  const error = new Error(message);
  
  // ✅ Attach status in multiple formats for compatibility
  error.status = status;
  
  // ✅ Create a response-like object (Axios format)
  error.response = {
    status,
    data: response?.data || null,
    statusText: response?.statusText || ''
  };
  
  return error;
};

// ==============================|| PERFORMANCE HELPERS ||============================== //

/**
 * Wrapper to measure request performance
 * @param {Function} asyncFn - Async function to measure
 * @param {string} endpoint - URL endpoint
 * @returns {Promise} Result with monitoring
 */
const withPerformanceTracking = async (asyncFn, endpoint) => {
  const startTime = performance.now();
  let success = true;
  let statusCode = null;
  let error = null;
  
  try {
    const result = await asyncFn();
    
    // Extract status code if available
    statusCode = result?.__meta?.status || 200;
    
    return result;
  } catch (err) {
    success = false;
    error = err;
    statusCode = err.response?.status || err.status || 0;
    throw err;
  } finally {
    const duration = performance.now() - startTime;
    
    // Record metric
    if (success) {
      metricsCollector.recordEndpointLatency(endpoint, duration, {
        success: true,
        statusCode,
        cached: false
      });
    } else {
      metricsCollector.recordEndpointError(endpoint, error, {
        duration,
        statusCode
      });
    }
    
    // === ENHANCED LOGS WITH COLORS AND EMOJIS ===
    if (process.env.NODE_ENV === 'development') {
      // Clean endpoint for display
      const cleanUrl = endpoint
        .replace(/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/gi, '{uuid}')
        .replace(/\/\d+\//g, '/{id}/')
        .replace(/\/\d+$/g, '/{id}');
      
      // Determine color based on latency
      let style = '';
      let emoji = '';
      
      if (!success) {
        emoji = '❌';
        style = 'color: #ff4444; font-weight: bold';
      } else if (duration < 200) {
        emoji = '⚡';
        style = 'color: #00cc00; font-weight: normal';
      } else if (duration < 500) {
        emoji = '✅';
        style = 'color: #88cc00; font-weight: normal';
      } else if (duration < 1000) {
        emoji = '⚠️';
        style = 'color: #ff9900; font-weight: bold';
      } else {
        emoji = '🐌';
        style = 'color: #ff4444; font-weight: bold';
      }
      
      // Format message
      const method = success ? 'GET' : 'ERR';
      const time = duration < 1000 
        ? `${duration.toFixed(0)}ms` 
        : `${(duration/1000).toFixed(2)}s`;
      
      // Log with style
      console.log(
        `%c${emoji} [${method}] ${cleanUrl} → ${time} (${statusCode || '?'})`,
        style
      );
      
      // If very slow request, additional log
      if (duration > 2000 && success) {
        console.warn(
          `%c⏰ VERY SLOW REQUEST: ${cleanUrl} took ${(duration/1000).toFixed(2)} seconds!`,
          'color: #ff0000; font-size: 12px; font-weight: bold; background: #ffeeee; padding: 2px 6px; border-radius: 3px'
        );
      }
      
      // If error, detailed log
      if (!success && error) {
        console.group(`%c❌ Error Details for ${cleanUrl}`, 'color: #cc0000');
        console.error('Status:', statusCode);
        console.error('Message:', error.message);
        if (error.response?.data) {
          console.error('Response:', error.response.data);
        }
        console.groupEnd();
      }
    }
  }
};

// ==============================|| MAIN FETCHER ||============================== //

/**
 * Global fetcher for SWR with monitoring - GET method
 * 
 * IMPORTANT: SWR can pass either:
 * 1. The original key (string or array)
 * 2. A stringified version for complex keys (starts with @)
 * 3. Tuple elements as separate arguments
 * 
 * @param {...any} args - Arguments passed by SWR
 * @returns {Promise<any>} - API data
 * @throws {Error} - Error if request fails
 */
const swrFetcher = async (...args) => {
  let url;
  let keyInfo = { raw: args };
  
  // === SWR KEY PARSING ===
  
  // Case 1: Single argument
  if (args.length === 1) {
    const key = args[0];
    
    // If it's a string starting with @, it's a serialized key by SWR
    if (typeof key === 'string' && key.startsWith('@')) {
      // SWR stringified our tuple, can't use it directly
      console.error('[SWR Fetcher] Received serialized key:', key);
      throw new Error('Fetcher received serialized key - check SWR configuration');
    }
    // If it's an array [url, tenantId]
    else if (Array.isArray(key)) {
      url = key[0];
      keyInfo.type = 'tuple';
      keyInfo.tenantId = key[1];
    }
    // If it's a simple string
    else if (typeof key === 'string') {
      url = key;
      keyInfo.type = 'string';
    }
  }
  // Case 2: Multiple arguments (SWR decomposed the tuple)
  else if (args.length >= 2) {
    // First argument is the URL
    url = args[0];
    keyInfo.type = 'spread';
    keyInfo.tenantId = args[1];
  }
  
  // === VALIDATION ===
  
  if (!url || typeof url !== 'string') {
    console.error('[SWR Fetcher] Invalid key structure:', args);
    throw new Error(`Invalid SWR key: URL must be a string, got ${typeof url}`);
  }

  // === DEBUG LOG (OPTIONAL - can be removed) ===
  if (process.env.NODE_ENV === 'development' && process.env.NEXT_PUBLIC_DEBUG_SWR === 'true') {
    console.debug('[SWR Fetcher] Processing:', {
      url,
      keyInfo,
      argsLength: args.length
    });
  }

  // === FETCH WITH MONITORING ===
  
  try {
    const data = await withPerformanceTracking(
      async () => {
        // Use api wrapper which already handles:
        // - HTTP-only cookies for JWT authentication
        // - Tenant headers (X-Client-ID, etc.)
        // - Standardized error handling
        // - Axios interceptors for token refresh
        const result = await api.get(url);
        
        // The api wrapper returns {success, data, error, status}
        if (result.success) {
          return result.data;
        }
        
        // ✅ FIX: If not successful, throw error WITH status code preserved
        // This ensures UI components can access error.response.status
        throw createApiError(
          result.error || 'Failed to fetch data',
          result.status || 0,
          result.response
        );
      },
      url // Pass URL for monitoring
    );
    
    return data;
    
  } catch (error) {
    // Re-throw the error so SWR can:
    // - Use onError if configured
    // - Apply shouldRetryOnError based on config
    // - Display error in component via error state
    throw error;
  }
};

// ==============================|| MUTATION FETCHERS WITH MONITORING ||============================== //

/**
 * Fetcher for POST requests with monitoring
 * 
 * @param {string | [string, string]} keyOrTuple - URL string or tuple [url, tenantId]
 * @param {Object} options - Mutation options
 * @param {any} options.arg - Data to send in POST
 * @returns {Promise<any>} - Response data
 */
export const swrPostFetcher = async (keyOrTuple, { arg }) => {
  const url = Array.isArray(keyOrTuple) ? keyOrTuple[0] : keyOrTuple;
  
  if (!url || typeof url !== 'string') {
    throw new Error('Invalid SWR key: URL must be a string');
  }

  return withPerformanceTracking(
    async () => {
      const result = await api.post(url, arg);
      
      if (result.success) {
        return result.data;
      }
      
      // ✅ Preserve status code in error
      throw createApiError(
        result.error || 'Failed to post data',
        result.status || 0,
        result.response
      );
    },
    url
  );
};

/**
 * Fetcher for PUT/PATCH requests with monitoring
 * 
 * @param {string | [string, string]} keyOrTuple - URL string or tuple [url, tenantId]
 * @param {Object} options - Mutation options
 * @param {any} options.arg - Data to send
 * @param {string} options.method - HTTP method (PUT or PATCH)
 * @returns {Promise<any>} - Response data
 */
export const swrMutateFetcher = async (keyOrTuple, { arg, method = 'PATCH' }) => {
  const url = Array.isArray(keyOrTuple) ? keyOrTuple[0] : keyOrTuple;
  
  if (!url || typeof url !== 'string') {
    throw new Error('Invalid SWR key: URL must be a string');
  }

  return withPerformanceTracking(
    async () => {
      const result = method === 'PUT' 
        ? await api.put(url, arg)
        : await api.patch(url, arg);
      
      if (result.success) {
        return result.data;
      }
      
      // ✅ Preserve status code in error
      throw createApiError(
        result.error || `Failed to ${method} data`,
        result.status || 0,
        result.response
      );
    },
    url
  );
};

/**
 * Fetcher for DELETE requests with monitoring
 * 
 * @param {string | [string, string]} keyOrTuple - URL string or tuple [url, tenantId]
 * @returns {Promise<any>} - Deletion confirmation
 */
export const swrDeleteFetcher = async (keyOrTuple) => {
  const url = Array.isArray(keyOrTuple) ? keyOrTuple[0] : keyOrTuple;
  
  if (!url || typeof url !== 'string') {
    throw new Error('Invalid SWR key: URL must be a string');
  }

  return withPerformanceTracking(
    async () => {
      const result = await api.delete(url);
      
      if (result.success) {
        return result.data || { success: true };
      }
      
      // ✅ Preserve status code in error
      throw createApiError(
        result.error || 'Failed to delete',
        result.status || 0,
        result.response
      );
    },
    url
  );
};

// ==============================|| CACHE ANALYSIS HELPER ||============================== //

/**
 * Helper to analyze SWR cache (dev only)
 * @param {Function} useSWRConfig - SWR config hook
 */
export const analyzeSWRCache = (useSWRConfig) => {
  if (process.env.NODE_ENV !== 'development') return;
  
  const { cache } = useSWRConfig();
  const cacheKeys = Array.from(cache.keys());
  
  console.group('📦 SWR Cache Analysis');
  console.log('Total cached keys:', cacheKeys.length);
  
  // Group by endpoint
  const byEndpoint = {};
  cacheKeys.forEach(key => {
    const clean = key.replace(/\?.*/, '').replace(/\/\d+/g, '/{id}');
    byEndpoint[clean] = (byEndpoint[clean] || 0) + 1;
  });
  
  console.table(byEndpoint);
  console.groupEnd();
  
  return { total: cacheKeys.length, byEndpoint };
};

// Export GET fetcher as default (most used)
export default swrFetcher;