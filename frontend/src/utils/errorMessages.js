// frontend/src/utils/errorMessages.js

/**
 * ✅ REUSABLE ERROR MESSAGE UTILITY
 * 
 * Provides structured error information for UI components across the app.
 * Combines existing handleApiError (backend message extraction) with 
 * status code → UI metadata mapping.
 * 
 * @module utils/errorMessages
 */

import { handleApiError } from './errorHandler';

// ==============================|| ERROR SEVERITY MAPPING ||============================== //

/**
 * Maps HTTP status codes to Material-UI Alert severity levels
 * @param {number} status - HTTP status code
 * @returns {string} Material-UI severity ('error', 'warning', 'info', 'success')
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

  const status = error.response?.status || error.status || 0;

  // Authentication errors
  if (status === 401) {
    return 'Session Expired';
  }

  // Permission errors
  if (status === 403) {
    return 'Access Denied';
  }

  // Not found errors
  if (status === 404) {
    return 'Resource Not Found';
  }

  // Timeout
  if (status === 408) {
    return 'Request Timeout';
  }

  // Rate limiting
  if (status === 429) {
    return 'Too Many Requests';
  }

  // Server errors (5xx)
  if (status >= 500 && status < 600) {
    return 'Server Error';
  }

  // Network errors (no response)
  if (!error.response && error.message) {
    if (error.message.includes('Network') || error.message.includes('timeout')) {
      return 'Connection Error';
    }
  }

  // Validation errors (400)
  if (status === 400) {
    return 'Validation Error';
  }

  // Generic client error
  if (status >= 400 && status < 500) {
    return 'Request Error';
  }

  // Default
  return 'Unexpected Error';
};

// ==============================|| MAIN UTILITY FUNCTION ||============================== //

/**
 * ✅ GET STRUCTURED ERROR INFO FOR UI DISPLAY
 * 
 * Combines backend message extraction with UI metadata.
 * Reusable across all components that need to display errors.
 * 
 * @param {Error} error - Axios error object from API call
 * @returns {Object|null} Structured error info or null
 * @returns {string} return.title - User-friendly error title
 * @returns {string} return.message - Detailed error message (from backend or fallback)
 * @returns {string} return.severity - Material-UI severity level
 * @returns {number} return.status - HTTP status code
 * @returns {boolean} return.isRetryable - Whether retry makes sense for this error
 * 
 * @example
 * // In a component
 * const errorInfo = getErrorDisplayInfo(error);
 * if (errorInfo) {
 *   return (
 *     <Alert severity={errorInfo.severity}>
 *       <AlertTitle>{errorInfo.title}</AlertTitle>
 *       {errorInfo.message}
 *     </Alert>
 *   );
 * }
 */
export const getErrorDisplayInfo = (error) => {
  if (!error) return null;

  const status = error.response?.status || error.status || 0;

  // Use existing handleApiError to extract backend message
  const backendMessage = handleApiError(error);

  // Determine if error is retryable
  const isRetryable =
    status === 401 ||
    status >= 500 || // Server errors
    status === 408 || // Timeout
    status === 429 || // Rate limit (retry after delay)
    (!error.response && error.message); // Network errors

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
  // Authentication
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

  // Permissions
  FORBIDDEN: {
    title: 'Access Denied',
    message: 'You do not have permission to access this resource.',
    severity: 'error'
  },

  // Not Found
  NOT_FOUND: {
    title: 'Resource Not Found',
    message: 'The requested resource could not be found. It may have been deleted.',
    severity: 'info'
  },

  // Network
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

  // Server
  SERVER_ERROR: {
    title: 'Server Error',
    message: 'The server encountered an error. Please try again later.',
    severity: 'error'
  },

  // Validation
  VALIDATION_ERROR: {
    title: 'Validation Error',
    message: 'Please check your input and try again.',
    severity: 'warning'
  },

  // Generic
  UNEXPECTED_ERROR: {
    title: 'Unexpected Error',
    message: 'An unexpected error occurred. Please try again.',
    severity: 'error'
  }
};

// ==============================|| HELPER FUNCTIONS ||============================== //

/**
 * Get error message by status code
 * Useful for simple cases where you only have the status
 * 
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
 * 
 * @param {Error} error - Axios error object
 * @returns {boolean} True if retry is recommended
 */
export const shouldRetry = (error) => {
  const info = getErrorDisplayInfo(error);
  return info?.isRetryable ?? false;
};

/**
 * Format error for toast/snackbar display
 * Returns a simplified version for notification systems
 * 
 * @param {Error} error - Axios error object
 * @returns {Object} Toast-friendly error object
 */
export const getErrorForToast = (error) => {
  const info = getErrorDisplayInfo(error);
  if (!info) return null;

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