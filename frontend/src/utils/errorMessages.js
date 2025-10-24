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
import { isRetryableError } from './retryLogic';

// ==============================|| ERROR SEVERITY MAPPING ||============================== //

/**
 * Maps HTTP status codes to Material-UI Alert severity levels
 * @param {number} status - HTTP status code
 * @returns {string} Material-UI severity ('error', 'warning', 'info')
 */
const getSeverityFromStatus = (status) => {
  if (status === 401 || status === 408 || status === 429) return 'warning';
  if (status === 403) return 'error';
  if (status === 404) return 'warning';
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

// ==============================|| MESSAGE VALIDATION ||============================== //

/**
 * ✅ ENHANCED: Validate extracted message
 * 
 * Checks if a message is valid and user-displayable.
 * Rejects: null, undefined, empty strings, '[object Object]', 'null', 'undefined'
 * 
 * @param {any} message - Message to validate
 * @returns {boolean} true if valid message
 */
const isValidMessage = (message) => {
  // Must be string
  if (typeof message !== 'string') {
    if (process.env.NODE_ENV === 'development') {
      console.debug('[isValidMessage] Not a string:', typeof message, message);
    }
    return false;
  }
  
  // Must not be empty after trim
  const trimmed = message.trim();
  if (trimmed.length === 0) {
    if (process.env.NODE_ENV === 'development') {
      console.debug('[isValidMessage] Empty string after trim');
    }
    return false;
  }
  
  // Reject common invalid values
  const lowerTrimmed = trimmed.toLowerCase();
  const invalidValues = ['[object object]', 'null', 'undefined', 'nan', 'error'];
  if (invalidValues.includes(lowerTrimmed)) {
    if (process.env.NODE_ENV === 'development') {
      console.debug('[isValidMessage] Invalid value:', trimmed);
    }
    return false;
  }
  
  // Must not be just special characters
  if (/^[^a-zA-Z0-9]+$/.test(trimmed)) {
    if (process.env.NODE_ENV === 'development') {
      console.debug('[isValidMessage] Only special characters:', trimmed);
    }
    return false;
  }
  
  return true;
};

// ==============================|| MAIN UTILITY FUNCTION ||============================== //

/**
 * ✅ GET STRUCTURED ERROR INFO FOR UI DISPLAY (ENHANCED)
 * 
 * Combines backend message extraction with UI metadata.
 * Reusable across all components that need to display errors.
 * 
 * ⚠️ ALWAYS RETURNS A VALID OBJECT - Never returns null
 * 
 * ENHANCEMENTS:
 * - Detailed dev logging at each step
 * - Better message validation
 * - More aggressive fallback strategy
 * - Should almost NEVER return DEFAULT_ERROR
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
 * const errorInfo = getErrorDisplayInfo(error);
 * <Alert severity={errorInfo.severity}>
 *   <AlertTitle>{errorInfo.title}</AlertTitle>
 *   {errorInfo.message}
 * </Alert>
 */
/**
 * ✅ CRASH-PROOF: GET STRUCTURED ERROR INFO FOR UI DISPLAY
 * 
 * Combines backend message extraction with UI metadata.
 * Reusable across all components that need to display errors.
 * 
 * ⚠️ ALWAYS RETURNS A VALID OBJECT - Never throws, never returns null
 * ⚠️ WRAPPED IN TRY-CATCH - Handles all unexpected parsing failures
 * 
 * PRIORITY:
 * 1. Backend message (if valid)
 * 2. Fallback message (if backend invalid/missing)
 * 3. Default error (only if catastrophic failure)
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
 * const errorInfo = getErrorDisplayInfo(error);
 * <Alert severity={errorInfo.severity}>
 *   <AlertTitle>{errorInfo.title}</AlertTitle>
 *   {errorInfo.message}
 * </Alert>
 */
export const getErrorDisplayInfo = (error) => {
  // ✅ DEFAULT FALLBACK (used when server down - status == 0) 
  const DEFAULT_ERROR = {
    title: 'Unexpected Error',
    message: 'Server Unavailable. Please try again.',
    severity: 'error',
    status: 0,
    isRetryable: false
  };

  // ====================================================================
  // 🛡️ TOP-LEVEL TRY-CATCH - Ensures function NEVER crashes
  // ====================================================================
  try {
    // ================================================================
    // STEP 1: Validate error object
    // ================================================================
    if (!isValidError(error)) {
      if (process.env.NODE_ENV === 'development') {
        console.warn('[getErrorDisplayInfo] Invalid error object:', error);
      }
      return DEFAULT_ERROR;
    }

    // ================================================================
    // STEP 2: Extract status code
    // ================================================================
    const status = error?.response?.status || 
                 error?.status || 
                 error?.error?.status ||  // Bulk operation format
                 0;
    
    if (process.env.NODE_ENV === 'development') {
      console.group('🔍 [getErrorDisplayInfo] Processing error');
      console.log('Status:', status);
      console.log('Error type:', error.constructor?.name);
      console.log('Has response:', !!error.response);
      console.log('Response data:', error.response?.data);
    }

    // ================================================================
    // STEP 3: Try to extract backend message using handleApiError
    // ================================================================
    let backendMessage = null;
    let extractionFailed = false;
    
    try {
      backendMessage = handleApiError(error);
      
      if (process.env.NODE_ENV === 'development') {
        console.log('handleApiError returned:', backendMessage);
        console.log('Type:', typeof backendMessage);
      }
    } catch (err) {
      extractionFailed = true;
      if (process.env.NODE_ENV === 'development') {
        console.error('handleApiError threw exception:', err);
      }
    }

    // ================================================================
    // STEP 4: Validate extracted backend message
    // ================================================================
    const messageIsValid = isValidMessage(backendMessage);
    
    if (process.env.NODE_ENV === 'development') {
      console.log('Message validation:', messageIsValid ? '✅ VALID' : '❌ INVALID');
    }

    // ================================================================
    // STEP 5: Choose final message (PRIORITY: backend → fallback)
    // ================================================================
    let finalMessage;
    
    if (messageIsValid) {
      // ✅ PRIORITY 1: Use backend message
      finalMessage = backendMessage.trim();
      
      if (process.env.NODE_ENV === 'development') {
        console.log('✅ Using backend message:', finalMessage);
      }
    } else {
      // ❌ PRIORITY 2: Use fallback based on error type
      if (!error.response) {
        // Network error (no response from server)
        finalMessage = FALLBACK_MESSAGES.network;
        
        if (process.env.NODE_ENV === 'development') {
          console.log('🌐 Network error detected, using fallback:', finalMessage);
        }
      } else {
        // Server responded but message extraction failed
        finalMessage = getFallbackMessage(status);
        
        if (process.env.NODE_ENV === 'development') {
          console.log(`📋 Using status-based fallback (${status}):`, finalMessage);
        }
      }
    }

    // ================================================================
    // STEP 6: Determine if error is retryable
    // ================================================================
    const isRetryable = isRetryableError(error);

    // ================================================================
    // STEP 7: Build final result
    // ================================================================
    const result = {
      title: getErrorTitle(error),
      message: finalMessage,
      severity: getSeverityFromStatus(status),
      status,
      isRetryable
    };

    if (process.env.NODE_ENV === 'development') {
      console.log('📤 Final result:', result);
      console.groupEnd();
    }

    return result;

  } catch (unexpectedError) {
    // ================================================================
    // 🚨 CATASTROPHIC FAILURE - Something went very wrong
    // ================================================================
    if (process.env.NODE_ENV === 'development') {
      console.error('🚨 [getErrorDisplayInfo] CATASTROPHIC PARSING FAILURE:', unexpectedError);
      console.error('Original error object:', error);
      console.groupEnd();
    }
    
    // ✅ CRITICAL: Always return valid object, never crash
    return DEFAULT_ERROR;
  }
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
  const info = getErrorDisplayInfo(error);
  
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