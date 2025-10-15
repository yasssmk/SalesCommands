// frontend/src/utils/errorMessages.js

/**
 * ✅ REUSABLE ERROR MESSAGE UTILITY (CRASH-SAFE VERSION)
 * 
 * Provides structured error information for UI components across the app.
 * Combines existing handleApiError (backend message extraction) with 
 * status code → UI metadata mapping.
 * 
 * ALL FUNCTIONS ARE NOW CRASH-SAFE using safe destructuring patterns.
 * 
 * @module utils/errorMessages
 */

import { handleApiError } from './errorHandler';
import { safeGet, safeString, isNonEmptyString, isValidError } from './safeHelpers';

// ==============================|| ERROR SEVERITY MAPPING ||============================== //

/**
 * Maps HTTP status codes to Material-UI Alert severity levels
 * @param {number} status - HTTP status code
 * @returns {string} Material-UI severity ('error', 'warning', 'info')
 */
const getSeverityFromStatus = (status) => {
  if (status === 401 || status === 408 || status === 429) return 'warning';
  if (status === 403) return 'error';
  if (status === 404) return 'info';
  if (status >= 500) return 'error';
  if (status >= 400 && status < 500) return 'warning';
  return 'error'; // Default
};

// ==============================|| ERROR TITLE MAPPING ||============================== //

/**
 * Maps HTTP status codes and error types to user-friendly titles
 * @param {Error} error - Axios error object
 * @returns {string} Error title for display
 */
const getErrorTitle = (error) => {
  if (!error) return 'Error';

  // ✅ SAFE: Use optional chaining + fallback
  const status = error?.response?.status || error?.status || 0;

  // Authentication errors
  if (status === 401) return 'Session Expired';
  if (status === 403) return 'Access Denied';
  if (status === 404) return 'Resource Not Found';
  if (status === 408) return 'Request Timeout';
  if (status === 429) return 'Too Many Requests';
  
  // Server errors (5xx)
  if (status >= 500 && status < 600) {
    return status === 503 ? 'Server Unavailable' : 'Server Error';
  }

  // Network errors (no response)
  if (!error.response && error.message) {
    const msg = String(error.message).toLowerCase();
    if (msg.includes('network') || msg.includes('timeout')) {
      return 'Connection Error';
    }
  }

  // Client errors
  if (status === 400) return 'Validation Error';
  if (status >= 400 && status < 500) return 'Request Error';

  return 'Unexpected Error';
};

// ==============================|| FALLBACK MESSAGES ||============================== //

/**
 * Fallback messages when backend response is malformed or extraction fails
 * These are user-friendly messages in English, matching our standards
 */
const FALLBACK_MESSAGES = {
  // 4xx fallbacks
  '400': 'The request could not be processed. Please check your input or try again.',
  '401': 'Your session has expired. Please log in again.',
  '403': 'You do not have permission to perform this action.',
  '404': 'The requested resource could not be found.',
  '408': 'The request took too long to complete. Please try again.',
  '429': 'Too many requests. Please wait a moment and try again.',
  '4xx': 'The request could not be processed. Please check your input or try again.',
  
  // 5xx fallbacks
  '500': 'The server encountered an error. Please try again later.',
  '502': 'The server is temporarily unavailable. Please try again shortly.',
  '503': 'The service is temporarily unavailable. Please try again shortly.',
  '504': 'The server took too long to respond. Please try again.',
  '5xx': 'The service is temporarily unavailable. Please try again shortly.',
  
  // Network/unknown
  'network': 'Unable to connect to the server. Please check your internet connection.',
  'unknown': 'An unexpected error occurred. Please try again.'
};

/**
 * Get fallback message for a specific status code
 * Returns a user-friendly message when backend response is unusable
 * 
 * @param {number} status - HTTP status code
 * @returns {string} Fallback message
 */
const getFallbackMessage = (status) => {
  if (!status) return FALLBACK_MESSAGES.unknown;
  
  const statusStr = String(status);
  if (FALLBACK_MESSAGES[statusStr]) {
    return FALLBACK_MESSAGES[statusStr];
  }
  
  if (status >= 400 && status < 500) return FALLBACK_MESSAGES['4xx'];
  if (status >= 500 && status < 600) return FALLBACK_MESSAGES['5xx'];
  
  return FALLBACK_MESSAGES.unknown;
};

// ==============================|| MAIN UTILITY FUNCTION ||============================== //

/**
 * ✅ GET STRUCTURED ERROR INFO FOR UI DISPLAY (CRASH-SAFE)
 * 
 * Combines backend message extraction with UI metadata.
 * Reusable across all components that need to display errors.
 * 
 * ⚠️ ALWAYS RETURNS A VALID OBJECT - Never returns null
 * Use this everywhere instead of manual error parsing.
 * 
 * @param {Error|Object|null|undefined} error - Axios error object from API call
 * @returns {Object} Structured error info (guaranteed to be valid object)
 * @returns {string} return.title - User-friendly error title
 * @returns {string} return.message - Detailed error message (from backend or fallback)
 * @returns {string} return.severity - Material-UI severity level (info/warning/error)
 * @returns {number} return.status - HTTP status code (0 if unknown)
 * @returns {boolean} return.isRetryable - Whether retry makes sense for this error
 * 
 * @example
 * // SAFE: Always returns valid object
 * const errorInfo = getErrorDisplayInfo(error);
 * // No need to check if null - always has properties
 * <Alert severity={errorInfo.severity}>
 *   <AlertTitle>{errorInfo.title}</AlertTitle>
 *   {errorInfo.message}
 * </Alert>
 * 
 * @example
 * // Also safe with undefined/null
 * const info = getErrorDisplayInfo(null);  // Returns default error object
 * const info2 = getErrorDisplayInfo(undefined);  // Returns default error object
 */
export const getErrorDisplayInfo = (error) => {
  // ✅ CRITICAL FIX: Always return a valid object, never null
  // This prevents "cannot destructure" errors everywhere this is used
  const DEFAULT_ERROR = {
    title: 'Unexpected Error',
    message: 'An unexpected error occurred. Please try again.',
    severity: 'error',
    status: 0,
    isRetryable: false
  };

  // Early return with default if error is invalid
  if (!isValidError(error)) {
    if (process.env.NODE_ENV === 'development') {
      console.warn('[getErrorDisplayInfo] Invalid error object:', error);
    }
    return DEFAULT_ERROR;
  }

  // ✅ SAFE: Extract status with fallbacks
  const status = error?.response?.status || error?.status || 0;

  // ✅ SAFE: Extract backend message using existing helper (wrapped in try-catch)
  let backendMessage;
  try {
    backendMessage = handleApiError(error);
  } catch (err) {
    if (process.env.NODE_ENV === 'development') {
      console.warn('[getErrorDisplayInfo] handleApiError failed:', err);
    }
    backendMessage = null;
  }

  // ✅ SAFE: Validate extracted message (NO MORE CRASHES on .trim())
  const isValidMessage = 
    isNonEmptyString(backendMessage) &&
    !safeString(backendMessage, 'includes', false, '[object Object]') &&
    backendMessage !== 'undefined' &&
    backendMessage !== 'null';

  // ✅ Use fallback if extraction failed or message is invalid
  if (!isValidMessage) {
    if (!error.response) {
      // True network error (no response from server)
      backendMessage = FALLBACK_MESSAGES.network;
    } else {
      // Server responded but message extraction failed
      backendMessage = getFallbackMessage(status);
    }
  }

  // Determine if error is retryable
  const isRetryable =
    status === 401 ||
    status >= 500 ||
    status === 408 ||
    status === 429 ||
    (!error.response && error.message);

  return {
    title: getErrorTitle(error),
    message: backendMessage,
    severity: getSeverityFromStatus(status),
    status,
    isRetryable
  };
};

// ==============================|| SPECIFIC ERROR MESSAGES ||============================== //

/**
 * Pre-defined error messages for common scenarios
 * Use these for consistent messaging across the app
 */
export const ErrorMessages = {
  SESSION_EXPIRED: {
    title: 'Session Expired',
    message: 'Your session has expired. Please log in again.',
    severity: 'warning'
  },
  
  UNAUTHORIZED: {
    title: 'Authentication Required',
    message: 'You must be logged in to access this resource.',
    severity: 'warning'
  },

  FORBIDDEN: {
    title: 'Access Denied',
    message: 'You do not have permission to access this resource.',
    severity: 'error'
  },

  NOT_FOUND: {
    title: 'Resource Not Found',
    message: 'The requested resource could not be found. It may have been deleted.',
    severity: 'info'
  },

  NETWORK_ERROR: {
    title: 'Connection Error',
    message: 'Unable to connect to the server. Please check your internet connection.',
    severity: 'warning'
  },

  TIMEOUT: {
    title: 'Request Timeout',
    message: 'The request took too long to complete. Please try again.',
    severity: 'warning'
  },

  SERVER_ERROR: {
    title: 'Server Error',
    message: 'The server encountered an error. Please try again later.',
    severity: 'error'
  },

  SERVICE_UNAVAILABLE: {
    title: 'Server Unavailable',
    message: 'The service is temporarily unavailable. Please try again shortly.',
    severity: 'error'
  },

  VALIDATION_ERROR: {
    title: 'Validation Error',
    message: 'Please check your input and try again.',
    severity: 'warning'
  },

  UNEXPECTED_ERROR: {
    title: 'Unexpected Error',
    message: 'An unexpected error occurred. Please try again.',
    severity: 'error'
  }
};

// ==============================|| HELPER FUNCTIONS ||============================== //

/**
 * Get error message by status code
 * @param {number} status - HTTP status code
 * @returns {Object} Error info object
 */
export const getErrorByStatus = (status) => {
  if (status === 401) return ErrorMessages.SESSION_EXPIRED;
  if (status === 403) return ErrorMessages.FORBIDDEN;
  if (status === 404) return ErrorMessages.NOT_FOUND;
  if (status === 408) return ErrorMessages.TIMEOUT;
  if (status >= 500) return ErrorMessages.SERVER_ERROR;
  if (status === 400) return ErrorMessages.VALIDATION_ERROR;
  return ErrorMessages.UNEXPECTED_ERROR;
};

/**
 * Check if an error should trigger a retry
 * @param {Error} error - Axios error object
 * @returns {boolean} True if retry is recommended
 */
export const shouldRetry = (error) => {
  const info = getErrorDisplayInfo(error);
  return info.isRetryable;
};

/**
 * Format error for toast/snackbar display
 * @param {Error} error - Axios error object
 * @returns {Object} Toast-friendly error object
 */
export const getErrorForToast = (error) => {
  const info = getErrorDisplayInfo(error);  // Always returns valid object now
  
  return {
    message: info.message,
    variant: 'alert',
    alert: {
      color: info.severity === 'warning' ? 'warning' : 
             info.severity === 'info' ? 'info' : 'error',
      variant: 'filled'
    }
  };
};

// ==============================|| EXPORTS ||============================== //

export default {
  getErrorDisplayInfo,
  getErrorByStatus,
  shouldRetry,
  getErrorForToast,
  ErrorMessages
};