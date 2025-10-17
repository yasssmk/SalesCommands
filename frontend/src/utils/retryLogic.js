// frontend/src/utils/retryLogic.js

/**
 * ✅ CENTRALIZED RETRY LOGIC - Single Source of Truth
 * 
 * This module provides the unified retry decision logic used across:
 * - SWR configuration (ProviderWrapper)
 * - Error message extraction (errorMessages)
 * - Component-level retry buttons (ErrorDisplay)
 * - Authentication retry logic (useAuth)
 * 
 * ALL retry decisions must flow through this module to ensure consistency.
 * 
 * @module utils/retryLogic
 */

// ==============================|| RETRY CATEGORIES ||============================== //

/**
 * Error categories for retry logic and debugging
 */
export const RetryCategory = {
  NETWORK_ERROR: 'network_error',      // No response from server
  SERVER_ERROR: 'server_error',        // 5xx errors
  TIMEOUT: 'timeout',                  // 408 timeout
  RATE_LIMIT: 'rate_limit',           // 429 rate limiting
  CLIENT_ERROR: 'client_error',       // 4xx (except 408, 429)
  AUTH_ERROR: 'auth_error',           // 401, 403
  NOT_FOUND: 'not_found',             // 404
  UNKNOWN: 'unknown'                  // Unable to classify
};

// ==============================|| CLASSIFICATION ||============================== //

/**
 * Classify error into a retry category for debugging and logging
 * 
 * @param {Error|Object} error - Error object from API/network
 * @returns {string} RetryCategory constant
 * 
 * @example
 * const category = getRetryCategory(error);
 * console.log(`Error category: ${category}`); // "server_error"
 */
export function getRetryCategory(error) {
  if (!error) {
    return RetryCategory.UNKNOWN;
  }

  // Extract status code (handle both Error objects and response objects)
  const status = error?.response?.status || error?.status || 0;

  // ✅ SIMPLIFIED: Network errors (no response from server OR status 0)
  if (!error.response || status === 0) {
    return RetryCategory.NETWORK_ERROR;
  }

  // Classify by status code
  if (status === 404) return RetryCategory.NOT_FOUND;
  if (status === 401 || status === 403) return RetryCategory.AUTH_ERROR;
  if (status === 408) return RetryCategory.TIMEOUT;
  if (status === 429) return RetryCategory.RATE_LIMIT;
  if (status >= 500 && status < 600) return RetryCategory.SERVER_ERROR;
  if (status >= 400 && status < 500) return RetryCategory.CLIENT_ERROR;

  return RetryCategory.UNKNOWN;
}

// ==============================|| MAIN RETRY LOGIC ||============================== //

/**
 * ✅ UNIFIED RETRY DECISION FUNCTION
 * 
 * Determines if an error should trigger a retry attempt.
 * This is the SINGLE SOURCE OF TRUTH for all retry logic in the app.
 * 
 * RETRY RULES:
 * ✅ YES - Network errors (no response from server)
 * ✅ YES - Server errors (5xx)
 * ✅ YES - Timeouts (408)
 * ✅ YES - Rate limiting (429)
 * ❌ NO  - Client errors (4xx except 408, 429)
 * ❌ NO  - Auth errors (401, 403) - handled by auth interceptor
 * ❌ NO  - Not found (404)
 * ❌ NO  - Explicitly marked as non-retryable (error.doNotRetry)
 * 
 * @param {Error|Object} error - Error object from API call or catch block
 * @param {Object} [options={}] - Optional configuration
 * @param {boolean} [options.allowAuthRetry=false] - Allow retry on 401/403 (special cases)
 * @param {boolean} [options.force=false] - Force retry even if normally non-retryable
 * @returns {boolean} true if error should trigger retry, false otherwise
 * 
 * @example
 * // Basic usage in SWR config
 * shouldRetryOnError: (error) => isRetryableError(error)
 * 
 * @example
 * // Usage in component with override
 * const shouldRetry = isRetryableError(error, { force: userClickedRetry });
 * 
 * @example
 * // Usage in error display
 * const errorInfo = getErrorDisplayInfo(error);
 * if (errorInfo.isRetryable) {
 *   // Show retry button
 * }
 */
export function isRetryableError(error, options = {}) {
  const {
    allowAuthRetry = false,
    force = false
  } = options;

  // If forced, always retry (manual user action)
  if (force) {
    return true;
  }

  // No error = no retry
  if (!error) {
    return false;
  }

  // Check explicit non-retry flag
  if (error.doNotRetry === true) {
    return false;
  }

  // Get error category for decision
  const category = getRetryCategory(error);

  // ✅ DEBUG MODE: Log retry decisions when flag enabled
  const shouldRetry = _evaluateRetryDecision(category, allowAuthRetry);
  
  if (typeof window !== 'undefined' && window.__DEBUG_RETRY_LOGIC__) {
    console.log(`[RetryDecision] ${category} → ${shouldRetry ? 'RETRY ✅' : 'SKIP ❌'}`, error);
  }
  
  // ✅ GRACEFUL FALLBACK: Warn on unknown errors in development
  if (category === RetryCategory.UNKNOWN && process.env.NODE_ENV === 'development') {
    console.warn('[retryLogic] Unclassified error - please review:', error);
  }
  
  return shouldRetry;
}

/**
 * Internal helper: Evaluate retry decision based on category
 * @private
 */
function _evaluateRetryDecision(category, allowAuthRetry) {
  // Decision tree based on category
  switch (category) {
    case RetryCategory.NETWORK_ERROR:
      return true; // Always retry network errors

    case RetryCategory.SERVER_ERROR:
      return true; // Always retry 5xx

    case RetryCategory.TIMEOUT:
      return true; // Always retry timeouts (408)

    case RetryCategory.RATE_LIMIT:
      return true; // Always retry rate limits (429, with Retry-After)

    case RetryCategory.AUTH_ERROR:
      return allowAuthRetry; // Usually false, handled by auth interceptor

    case RetryCategory.NOT_FOUND:
      return false; // Never retry 404

    case RetryCategory.CLIENT_ERROR:
      return false; // Never retry other 4xx

    case RetryCategory.UNKNOWN:
      return false; // Don't retry unknown errors (safe default)

    default:
      return false;
  }
}

// ==============================|| RETRY DELAY CALCULATION ||============================== //

/**
 * Calculate retry delay with exponential backoff and jitter
 * 
 * This function provides the delay calculation logic but does NOT
 * replace the existing SWR retry scheduling. It's provided for:
 * - Custom retry implementations
 * - Manual retry buttons
 * - Auth retry logic
 * 
 * SWR's onErrorRetry already handles scheduling, so this is supplementary.
 * 
 * @param {Error} error - The error object
 * @param {number} attempt - Current retry attempt (0-indexed)
 * @param {Object} [options={}] - Configuration options
 * @param {number} [options.baseDelay=1000] - Base delay in ms (default 1s)
 * @param {number} [options.maxDelay=30000] - Max delay in ms (default 30s)
 * @param {number} [options.jitterFactor=0.1] - Jitter factor (default 10%)
 * @returns {number} Delay in milliseconds
 * 
 * @example
 * // Calculate delay for 3rd retry attempt
 * const delay = getRetryDelay(error, 2); // ~4000ms with jitter
 * setTimeout(() => retry(), delay);
 */
export function getRetryDelay(error, attempt = 0, options = {}) {
  const {
    baseDelay = 1000,
    maxDelay = 30000,
    jitterFactor = 0.1
  } = options;

  // Check if error has explicit retry delay (429 with Retry-After)
  if (error?.retryAfterMs && error.retryAfterMs > 0) {
    return error.retryAfterMs;
  }

  // Exponential backoff: baseDelay * 2^attempt
  const exponentialDelay = baseDelay * Math.pow(2, attempt);
  
  // Cap at max delay
  const cappedDelay = Math.min(exponentialDelay, maxDelay);
  
  // Add jitter to prevent thundering herd
  const jitter = cappedDelay * jitterFactor * Math.random();
  
  return Math.floor(cappedDelay + jitter);
}

// ==============================|| NOTE ON ERROR MESSAGES ||============================== //

/**
 * ⚠️ ERROR MESSAGES ARE NOT IN THIS FILE
 * 
 * All user-facing error messages are centralized in utils/errorMessages.js
 * This module (retryLogic.js) focuses ONLY on retry decision logic.
 * 
 * To get user-facing messages:
 * - Import ErrorMessages from 'utils/errorMessages'
 * - Use getErrorDisplayInfo(error) for complete error info (title, message, severity)
 * 
 * This separation ensures:
 * - Single Responsibility Principle (SRP)
 * - No duplication of messages
 * - Clear module boundaries
 */

// ==============================|| HELPER FUNCTIONS ||============================== //

/**
 * Check if error is a network error (no response)
 * @param {Error} error - Error object
 * @returns {boolean} true if network error
 */
export function isNetworkError(error) {
  return getRetryCategory(error) === RetryCategory.NETWORK_ERROR;
}

/**
 * Check if error is a server error (5xx)
 * @param {Error} error - Error object
 * @returns {boolean} true if server error
 */
export function isServerError(error) {
  return getRetryCategory(error) === RetryCategory.SERVER_ERROR;
}

/**
 * Check if error is a timeout (408)
 * @param {Error} error - Error object
 * @returns {boolean} true if timeout
 */
export function isTimeoutError(error) {
  return getRetryCategory(error) === RetryCategory.TIMEOUT;
}

/**
 * Check if error is rate limited (429)
 * @param {Error} error - Error object
 * @returns {boolean} true if rate limited
 */
export function isRateLimitError(error) {
  return getRetryCategory(error) === RetryCategory.RATE_LIMIT;
}

// ==============================|| EXPORTS ||============================== //

export default {
  isRetryableError,
  getRetryCategory,
  getRetryDelay,
  RetryCategory,
  // Helper functions
  isNetworkError,
  isServerError,
  isTimeoutError,
  isRateLimitError
};