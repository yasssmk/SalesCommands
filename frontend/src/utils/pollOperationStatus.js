// frontend/src/utils/pollOperationStatus.js

/**
 * ✅ POLLING HELPER FOR LONG-RUNNING OPERATIONS
 * 
 * Polls GET /ops/{key} endpoint to check status of async bulk operations.
 * Implements exponential backoff with respect for backend Retry-After hints.
 * 
 * Used when backend returns 202 Accepted with poll_url.
 * 
 * **Flow:**
 * 1. Backend returns 202 + poll_url
 * 2. Frontend calls pollOperationStatus(idempotencyKey)
 * 3. Polls with exponential backoff (6 attempts max)
 * 4. Returns when status is 'succeeded', 'failed', or max attempts reached
 * 
 * **Architecture:**
 * - Standalone function (no React coupling)
 * - Testable in isolation
 * - Reusable across API layer, hooks, components
 * - Integrates with handleBulkRevalidation()
 * 
 * @module utils/pollOperationStatus
 */

import { api } from 'utils/axiosClient';

/**
 * Default polling configuration
 */
export const DEFAULT_CONFIG = {
  maxAttempts: 6,          // Total polling attempts (≈31s with default delays)
  baseDelay: 1000,         // Base delay in ms (1 second)
  maxDelay: 8000,          // Cap delay at 8 seconds
  exponentialFactor: 2     // Multiply delay by 2 each attempt
};

/**
 * Parse Retry-After header value
 * 
 * Supports two formats:
 * - Seconds: "2" → 2000ms
 * - HTTP date: "Wed, 21 Oct 2015 07:28:00 GMT" → calculated delay
 * 
 * @param {string|undefined} retryAfter - Retry-After header value
 * @returns {number} Delay in milliseconds, or 0 if invalid
 */
function parseRetryAfter(retryAfter) {
  if (!retryAfter) return 0;
  
  // Try parsing as seconds
  const seconds = parseInt(retryAfter, 10);
  if (!isNaN(seconds) && seconds > 0) {
    return seconds * 1000;
  }
  
  // Try parsing as HTTP date
  try {
    const date = new Date(retryAfter);
    if (!isNaN(date.getTime())) {
      const delay = date.getTime() - Date.now();
      return delay > 0 ? delay : 0;
    }
  } catch (e) {
    // Invalid date format
  }
  
  return 0;
}

/**
 * Calculate next polling delay with exponential backoff
 * 
 * Strategy:
 * - Attempt 1: baseDelay (default 1s)
 * - Attempt 2: baseDelay * 2 (2s)
 * - Attempt 3: baseDelay * 4 (4s)
 * - Attempt 4+: capped at maxDelay (8s)
 * 
 * Respects Retry-After hint from backend if provided.
 * 
 * @param {number} attempt - Current attempt number (1-based)
 * @param {number} retryAfterMs - Backend's Retry-After hint in ms
 * @param {Object} config - Polling configuration
 * @returns {number} Delay in milliseconds
 */
function calculateDelay(attempt, retryAfterMs, config) {
  const { baseDelay, maxDelay, exponentialFactor } = config;
  
  // If backend provides Retry-After, respect it for first attempt
  if (attempt === 1 && retryAfterMs > 0) {
    return Math.min(retryAfterMs, maxDelay);
  }
  
  // Exponential backoff: baseDelay * (factor ^ (attempt - 1))
  const exponentialDelay = baseDelay * Math.pow(exponentialFactor, attempt - 1);
  
  // Cap at maxDelay
  return Math.min(exponentialDelay, maxDelay);
}

/**
 * Poll operation status until completion or timeout
 * 
 * Makes repeated GET requests to /ops/{key} with exponential backoff.
 * Stops when operation status is 'succeeded', 'failed', or max attempts reached.
 * 
 * **Return values:**
 * - { status: 'succeeded', result: {...} } - Operation completed successfully
 * - { status: 'failed', error: '...' } - Operation failed
 * - { status: 'still_running', message: '...' } - Max attempts reached, still running
 * 
 * **Integration:**
 * Called by handleBulkRevalidation() when 202 Accepted is detected.
 * 
 * @param {string} idempotencyKey - Idempotency key of the operation
 * @param {Object} [options={}] - Polling options
 * @param {number} [options.maxAttempts=6] - Maximum polling attempts
 * @param {number} [options.baseDelay=1000] - Base delay in ms
 * @param {number} [options.maxDelay=8000] - Maximum delay in ms
 * @param {number} [options.exponentialFactor=2] - Backoff multiplier
 * @param {number} [options.initialRetryAfter=0] - Initial Retry-After from 202 response (ms)
 * @param {Function} [options.onProgress=null] - Progress callback: (attempt, maxAttempts) => void
 * @returns {Promise<Object>} Final operation status
 * 
 * @example
 * // Basic usage
 * const result = await pollOperationStatus('bulk-delete-abc123');
 * if (result.status === 'succeeded') {
 *   console.log('Operation completed:', result.result);
 * }
 * 
 * @example
 * // With progress callback
 * const result = await pollOperationStatus('bulk-update-xyz', {
 *   onProgress: (attempt, max) => {
 *     console.log(`Polling attempt ${attempt}/${max}`);
 *   }
 * });
 * 
 * @example
 * // With custom configuration
 * const result = await pollOperationStatus('bulk-create-def456', {
 *   maxAttempts: 10,
 *   baseDelay: 500,
 *   maxDelay: 10000,
 *   initialRetryAfter: 2000  // From 202 response Retry-After header
 * });
 */
export async function pollOperationStatus(idempotencyKey, options = {}) {
  // Validate input
  if (!idempotencyKey || typeof idempotencyKey !== 'string') {
    console.error('[pollOperationStatus] Invalid idempotencyKey:', idempotencyKey);
    return {
      status: 'failed',
      error: 'Invalid idempotency key provided'
    };
  }
  
  // Merge options with defaults
  const config = {
    ...DEFAULT_CONFIG,
    ...options
  };
  
  const { maxAttempts, onProgress } = config;
  const initialRetryAfter = options.initialRetryAfter || 0;
  
  if (process.env.NODE_ENV === 'development') {
    console.log(`[pollOperationStatus] Starting polling for key: ${idempotencyKey.slice(0, 8)}...`);
    console.log(`[pollOperationStatus] Config:`, {
      maxAttempts,
      baseDelay: config.baseDelay,
      maxDelay: config.maxDelay,
      initialRetryAfter
    });
  }
  
  // Polling loop
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    // Notify progress callback
    if (onProgress && typeof onProgress === 'function') {
      try {
        onProgress(attempt, maxAttempts);
      } catch (err) {
        console.error('[pollOperationStatus] Progress callback error:', err);
      }
    }
    
    // Calculate delay for this attempt
    const delay = calculateDelay(attempt, initialRetryAfter, config);
    
    if (process.env.NODE_ENV === 'development') {
      console.log(
        `[pollOperationStatus] Attempt ${attempt}/${maxAttempts} - waiting ${delay}ms before polling`
      );
    }
    
    // Wait before polling (exponential backoff)
    await new Promise(resolve => setTimeout(resolve, delay));
    
    // Poll operation status
    try {
      
      const result = await api.get(`/core/operations/${idempotencyKey}/status/`);
      
      if (!result.success) {
        // 404 = operation not found (expired or never existed).
        // Fail-fast: no point retrying, the key will never appear.
        if (result.status === 404) {
          return {
            status: 'not_found',
            error: result.error || 'Operation not found',
          };
        }

        // API call failed (network error, 500, etc.)
        console.error('[pollOperationStatus] API call failed:', result.error);
        
        // Don't fail immediately - backend might still be processing
        // Continue polling unless it's the last attempt
        if (attempt === maxAttempts) {
          return {
            status: 'failed',
            error: result.error || 'Failed to check operation status'
          };
        }
        
        // Continue to next attempt
        continue;
      }
      
      const opStatus = result.data?.status;
      
      if (process.env.NODE_ENV === 'development') {
        console.log(
          `[pollOperationStatus] Attempt ${attempt}: status = ${opStatus}`
        );
      }
      
      // Check operation status
      if (opStatus === 'succeeded') {
        // ✅ Operation completed successfully
        if (process.env.NODE_ENV === 'development') {
          console.log('[pollOperationStatus] Operation succeeded!');
        }
        
        return {
          status: 'succeeded',
          result: result.data.result || {}
        };
      }
      
      if (opStatus === 'failed') {
        // ❌ Operation failed
        if (process.env.NODE_ENV === 'development') {
          console.log('[pollOperationStatus] Operation failed:', result.data.error);
        }
        
        return {
          status: 'failed',
          error: result.data.error || 'Operation failed on server'
        };
      }
      
      if (opStatus === 'running') {
        // ⏳ Still processing - continue polling
        if (process.env.NODE_ENV === 'development') {
          console.log('[pollOperationStatus] Operation still running, will retry...');
        }
        
        // Extract new Retry-After hint if provided
        const newRetryAfter = parseRetryAfter(result.response?.headers?.['retry-after']);
        if (newRetryAfter > 0 && process.env.NODE_ENV === 'development') {
          console.log(`[pollOperationStatus] Backend suggests retry after ${newRetryAfter}ms`);
        }
        
        // Continue to next attempt
        continue;
      }
      
      // Unknown status
      console.warn('[pollOperationStatus] Unknown operation status:', opStatus);
      
      // Continue polling unless last attempt
      if (attempt === maxAttempts) {
        return {
          status: 'still_running',
          message: `Operation status unknown after ${maxAttempts} attempts`
        };
      }
      
    } catch (err) {
      // Unexpected error during polling
      console.error('[pollOperationStatus] Polling error:', err);
      
      // Don't fail immediately - might be transient network issue
      if (attempt === maxAttempts) {
        return {
          status: 'failed',
          error: err?.message || 'Polling failed with unexpected error'
        };
      }
      
      // Continue to next attempt
      continue;
    }
  }
  
  // Max attempts reached, operation still running
  console.warn(
    `[pollOperationStatus] Max attempts (${maxAttempts}) reached, operation still running`
  );
  
  return {
    status: 'still_running',
    message: 'Operation still in progress. It will complete in the background.'
  };
}

/**
 * Extract idempotency key from poll_url
 * 
 * Parses URL like "/ops/{key}" or "http://host/ops/{key}" to extract key.
 * Used as fallback if idempotency key is not available in metadata.
 * 
 * @param {string} pollUrl - Full or relative poll URL
 * @returns {string|null} Extracted idempotency key, or null if invalid
 * 
 * @example
 * extractKeyFromPollUrl('/ops/bulk-delete-abc123') // 'bulk-delete-abc123'
 * extractKeyFromPollUrl('http://api.example.com/ops/bulk-update-xyz') // 'bulk-update-xyz'
 */
export function extractKeyFromPollUrl(pollUrl) {
  if (!pollUrl || typeof pollUrl !== 'string') {
    return null;
  }
  
  // Match /core/operations/{key}/status/ pattern
  // Also supports legacy /ops/{key} for backward compatibility
  const coreMatch = pollUrl.match(/\/core\/operations\/([^/?#]+)\/status/);
  if (coreMatch && coreMatch[1]) {
    return coreMatch[1];
  }
  
  // Legacy fallback: /ops/{key} or /ops/status/{key}
  const opsMatch = pollUrl.match(/\/ops\/(?:status\/)?([^/?#]+)/);
  if (opsMatch && opsMatch[1]) {
    return opsMatch[1];
  }
  
  return null;
}

// ==============================|| EXPORTS ||============================== //

export default pollOperationStatus;