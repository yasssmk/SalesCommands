// frontend/src/utils/errorHandler.js

/**
 * ✅ ENHANCED ERROR HANDLER - Robust Backend Message Extraction
 * 
 * Extracts user-facing messages from Django/DRF error responses.
 * Handles all common DRF formats:
 * - Simple strings: "Error message"
 * - Detail field: {detail: "Message"}
 * - Error field: {error: "Message"} or {error: ["Message"]}
 * - Validation dicts: {field: ["Error"], field2: ["Error2"]}
 * - Nested objects: {user: {email: ["Invalid"]}}
 * - Arrays: ["Error1", "Error2"]
 * 
 * ENHANCEMENTS:
 * - Recursive extraction for nested structures
 * - Smart concatenation for multiple errors
 * - Better handling of edge cases
 * - Detailed dev logging
 * 
 * @module utils/errorHandler
 */

// ==============================|| HELPER FUNCTIONS ||============================== //

/**
 * Check if value is a plain object (not Array, not null)
 * @param {any} obj - Value to check
 * @returns {boolean} true if plain object
 */
const isPlainObject = (obj) => {
  return obj !== null && 
         typeof obj === 'object' && 
         !Array.isArray(obj) &&
         Object.prototype.toString.call(obj) === '[object Object]';
};

/**
 * ✅ NEW: Extract all error messages from a nested structure
 * 
 * Recursively walks through objects and arrays to find all error messages.
 * Returns an array of user-facing messages.
 * 
 * @param {any} data - Data to extract from (object, array, string)
 * @param {number} depth - Current recursion depth (safety limit)
 * @returns {string[]} Array of error messages
 */
const extractAllMessages = (data, depth = 0) => {
  const MAX_DEPTH = 5; // Prevent infinite recursion
  const messages = [];
  
  // Safety: prevent infinite recursion
  if (depth > MAX_DEPTH) {
    if (process.env.NODE_ENV === 'development') {
      console.warn('[extractAllMessages] Max depth reached, stopping recursion');
    }
    return messages;
  }
  
  // Case 1: String message (leaf node)
  if (typeof data === 'string' && data.trim().length > 0) {
    messages.push(data.trim());
    return messages;
  }
  
  // Case 2: Array of messages or objects
  if (Array.isArray(data)) {
    data.forEach(item => {
      const extracted = extractAllMessages(item, depth + 1);
      messages.push(...extracted);
    });
    return messages;
  }
  
  // Case 3: Plain object - extract from all values
  if (isPlainObject(data)) {
    Object.values(data).forEach(value => {
      const extracted = extractAllMessages(value, depth + 1);
      messages.push(...extracted);
    });
    return messages;
  }
  
  // Case 4: Other types (numbers, booleans, null) - ignore
  return messages;
};

/**
 * ✅ NEW: Smart concatenation of multiple error messages
 * 
 * Combines multiple messages intelligently:
 * - Single message: return as-is
 * - 2 messages: "Message1. Message2."
 * - 3+ messages: "Message1. Message2. And 1 more error."
 * 
 * @param {string[]} messages - Array of error messages
 * @param {number} maxDisplay - Maximum messages to display explicitly
 * @returns {string} Concatenated message
 */
const concatenateMessages = (messages, maxDisplay = 2) => {
  if (messages.length === 0) {
    return '';
  }
  
  if (messages.length === 1) {
    return messages[0];
  }
  
  // Deduplicate messages (case-insensitive)
  const uniqueMessages = [];
  const seenLower = new Set();
  
  messages.forEach(msg => {
    const lower = msg.toLowerCase();
    if (!seenLower.has(lower)) {
      seenLower.add(lower);
      uniqueMessages.push(msg);
    }
  });
  
  if (uniqueMessages.length === 1) {
    return uniqueMessages[0];
  }
  
  // Display first N messages explicitly
  const displayed = uniqueMessages.slice(0, maxDisplay);
  const remaining = uniqueMessages.length - maxDisplay;
  
  let result = displayed.join('. ');
  
  // Ensure proper punctuation
  if (!result.endsWith('.')) {
    result += '.';
  }
  
  // Add "And N more" if there are remaining messages
  if (remaining > 0) {
    result += ` And ${remaining} more error${remaining > 1 ? 's' : ''}.`;
  }
  
  return result;
};

// ==============================|| MAIN ERROR HANDLER ||============================== //

/**
 * ✅ ENHANCED: Extract user-facing message from Django/DRF error
 * 
 * Tries extraction in this order:
 * 1. Network errors (no response)
 * 2. 5XX errors (server errors with generic fallbacks)
 * 3. DRF standard formats (detail, error fields)
 * 4. Validation dicts (field-level errors)
 * 5. Arrays (multiple messages)
 * 6. Nested structures (recursive extraction)
 * 7. Status-based fallbacks
 * 
 * @param {Error} axiosError - Axios error object
 * @returns {string} User-facing error message
 */
export const handleApiError = (axiosError) => {
  
  if (process.env.NODE_ENV === 'development') {
    console.group('🔍 [handleApiError] Extracting backend message');
    console.log('Error object:', axiosError);
    console.log('Has response:', !!axiosError?.response);
    console.log('Response data:', axiosError?.response?.data);
  }

  // ==============================
  // 1. NETWORK ERROR (Backend down, DNS failure, etc.)
  // ==============================
  if (!axiosError?.response) {
    // Check if it's a genuine Axios network error
    const isAxiosNetworkError = 
      axiosError?.message === 'Network Error' || 
      axiosError?.code === 'ERR_NETWORK' ||
      axiosError?.code === 'ECONNREFUSED';
    
    if (isAxiosNetworkError) {
      if (process.env.NODE_ENV === 'development') {
        console.log('🌐 Network error detected');
        console.groupEnd();
      }
      return 'Unable to connect to the server. Please check your internet connection.';
    }
    
    // For other cases without response, check custom error properties
    if (axiosError.error && typeof axiosError.error === 'string') {
      if (process.env.NODE_ENV === 'development') {
        console.log('📋 Using custom error property');
        console.groupEnd();
      }
      return axiosError.error;
    }
    
    if (axiosError.message && typeof axiosError.message === 'string') {
      if (process.env.NODE_ENV === 'development') {
        console.log('📋 Using error.message');
        console.groupEnd();
      }
      return axiosError.message;
    }
    
    if (process.env.NODE_ENV === 'development') {
      console.log('🤷 Unknown no-response error');
      console.groupEnd();
    }
    return 'Network error. Please check your connection.';
  }

  // ==============================
  // 2. EXTRACT STATUS & DATA
  // ==============================
  const { status, data } = axiosError.response;
  
  if (process.env.NODE_ENV === 'development') {
    console.log('Status:', status);
    console.log('Data type:', typeof data);
  }

  // ==============================
  // 2.5 STATUS 0 = NETWORK ERROR (created by swrFetcher)
  // ==============================
  // When swrFetcher creates errors via createApiError(), it sets
  // error.response = {status: 0, data: null} for network errors.
  // We must detect this case and return the appropriate message.
  if (status === 0) {
    // Check if the error message already contains a good network error message
    if (axiosError.message && typeof axiosError.message === 'string') {
      const msg = axiosError.message.toLowerCase();
      // If message already contains network-related info, use it
      if (msg.includes('connect') || msg.includes('network') || msg.includes('server')) {
        if (process.env.NODE_ENV === 'development') {
          console.log('🌐 Status 0 with network message detected');
          console.groupEnd();
        }
        return axiosError.message;
      }
    }
    
    // Default network error message
    if (process.env.NODE_ENV === 'development') {
      console.log('🌐 Status 0 detected (network error)');
      console.groupEnd();
    }
    return 'Unable to connect to the server. Please check your internet connection.';
  }

  // ==============================
  // 3. 5XX SERVER ERRORS (Generic fallbacks)
  // ==============================
  if (status >= 500) {
    // Path 1: Plain string response
  if (typeof data === 'string' && data.trim().length > 0 && data.length < 500) {
    if (!data.trim().startsWith('<')) { // Avoid HTML error pages
      if (process.env.NODE_ENV === 'development') {
        console.log('✅ Using custom 5XX string message:', data.trim());
        console.groupEnd();
      }
      return data.trim();
    }
  }
  
  // Path 2: data.detail
  if (data?.detail && typeof data.detail === 'string') {
    if (process.env.NODE_ENV === 'development') {
      console.log('✅ Using custom 5XX detail message:', data.detail);
      console.groupEnd();
    }
    return data.detail;
  }
  
  // Path 3: data.error
  if (data?.error) {
    if (typeof data.error === 'string') {
      if (process.env.NODE_ENV === 'development') {
        console.log('✅ Using custom 5XX error message:', data.error);
        console.groupEnd();
      }
      return data.error;
    }
    
    // data.error as array
    if (Array.isArray(data.error) && data.error.length > 0) {
      const messages = extractAllMessages(data.error);
      const result = concatenateMessages(messages);
      if (result) {
        if (process.env.NODE_ENV === 'development') {
          console.log('✅ Using custom 5XX error array:', result);
          console.groupEnd();
        }
        return result;
      }
    }
  }
  
  // Path 4: data.message
  if (data?.message && typeof data.message === 'string') {
    if (process.env.NODE_ENV === 'development') {
      console.log('✅ Using custom 5XX message field:', data.message);
      console.groupEnd();
    }
    return data.message;
  }
  
  // ✅ ONLY use fallbacks if ALL extraction paths failed
  if (status === 503) {
    if (process.env.NODE_ENV === 'development') {
      console.log('📋 503 Service Unavailable (fallback)');
      console.groupEnd();
    }
    return 'Service temporarily unavailable. Please try again shortly.';
  }
  if (status === 502) {
    if (process.env.NODE_ENV === 'development') {
      console.log('📋 502 Bad Gateway (fallback)');
      console.groupEnd();
    }
    return 'Bad gateway. The server is temporarily unavailable.';
  }
  if (status === 504) {
    if (process.env.NODE_ENV === 'development') {
      console.log('📋 504 Gateway Timeout (fallback)');
      console.groupEnd();
    }
    return 'Gateway timeout. The server took too long to respond.';
  }
  
  // Generic 500 fallback
  if (process.env.NODE_ENV === 'development') {
    console.log('📋 Generic 500 error (fallback)');
    console.groupEnd();
  }
  return 'Server error. Please try again later.';
}

  // ==============================
  // 4. DRF STANDARD FORMATS
  // ==============================
  
  // 4a. DRF standard: {detail: "message"}
  if (data?.detail && typeof data.detail === 'string') {
    if (process.env.NODE_ENV === 'development') {
      console.log('✅ Found detail field:', data.detail);
      console.groupEnd();
    }
    return data.detail;
  }

  // 4b. Custom format: {error: "message"}
  if (typeof data?.error === 'string') {
    if (process.env.NODE_ENV === 'development') {
      console.log('✅ Found error string:', data.error);
      console.groupEnd();
    }
    return data.error;
  }

  // 4c. Custom format: {error: ["message1", "message2"]}
  if (Array.isArray(data?.error) && data.error.length > 0) {
    const messages = extractAllMessages(data.error);
    const result = concatenateMessages(messages);
    
    if (result) {
      if (process.env.NODE_ENV === 'development') {
        console.log('✅ Found error array, extracted:', result);
        console.groupEnd();
      }
      return result;
    }
  }

  // 4d. Custom format: {message: "..."}
  if (typeof data?.message === 'string') {
    if (process.env.NODE_ENV === 'development') {
      console.log('✅ Found message field:', data.message);
      console.groupEnd();
    }
    return data.message;
  }

  // ==============================
  // 5. DRF VALIDATION DICT (field-level errors)
  // ==============================
  // Format: {field1: ["error1"], field2: ["error2"], ...}
  if (isPlainObject(data) && !data.detail && !data.error && !data.message) {
    const keys = Object.keys(data);
    
    if (keys.length > 0) {
      if (process.env.NODE_ENV === 'development') {
        console.log('🔍 Checking for validation dict with keys:', keys);
      }

      // Extract messages per field, prefixing each with its field name so the
      // user sees WHICH field failed (e.g. "metric_text: This field may not be
      // null."). non_field_errors carries no useful field name — keep it raw.
      const fieldMessages = [];
      Object.entries(data).forEach(([field, value]) => {
        extractAllMessages(value).forEach((msg) => {
          fieldMessages.push(
            field === 'non_field_errors' ? msg : `${field}: ${msg}`
          );
        });
      });

      if (fieldMessages.length > 0) {
        const result = concatenateMessages(fieldMessages, 3); // Show up to 3 errors

        if (process.env.NODE_ENV === 'development') {
          console.log('✅ Extracted from validation dict:', result);
          console.groupEnd();
        }
        return result;
      }
    }
  }

  // ==============================
  // 6. DRF ARRAY ROOT (multiple messages)
  // ==============================
  // Format: ["message1", "message2"]
  if (Array.isArray(data) && data.length > 0) {
    const messages = extractAllMessages(data);
    const result = concatenateMessages(messages);
    
    if (result) {
      if (process.env.NODE_ENV === 'development') {
        console.log('✅ Extracted from array root:', result);
        console.groupEnd();
      }
      return result;
    }
  }

  // ==============================
  // 7. STRING DATA (plain text response)
  // ==============================
  if (typeof data === 'string' && data.trim().length > 0) {
    // Avoid HTML responses (usually error pages)
    if (!data.trim().startsWith('<') && data.length < 500) {
      if (process.env.NODE_ENV === 'development') {
        console.log('✅ Using plain string data:', data);
        console.groupEnd();
      }
      return data.trim();
    }
  }

  // ==============================
  // 8. STATUS-BASED FALLBACKS (4XX)
  // ==============================
  if (status >= 400 && status < 500) {
    // Validation errors
    if (status === 400 || status === 422) {
      if (process.env.NODE_ENV === 'development') {
        console.log('📋 Validation error fallback (400/422)');
        console.groupEnd();
      }
      return 'Validation error. Please review your input.';
    }
    
    // Authentication required
    if (status === 401) {
      if (process.env.NODE_ENV === 'development') {
        console.log('📋 Auth error fallback (401)');
        console.groupEnd();
      }
      return 'Authentication required. Please sign in again.';
    }
    
    // Permission denied
    if (status === 403) {
      if (process.env.NODE_ENV === 'development') {
        console.log('📋 Permission error fallback (403)');
        console.groupEnd();
      }
      return 'You do not have permission to perform this action.';
    }
    
    // Resource not found
    if (status === 404) {
      if (process.env.NODE_ENV === 'development') {
        console.log('📋 Not found fallback (404)');
        console.groupEnd();
      }
      return 'Resource not found.';
    }
    
    // Generic 4xx fallback
    if (process.env.NODE_ENV === 'development') {
      console.log('📋 Generic 4xx fallback');
      console.groupEnd();
    }
    return 'Request failed. Please check your input and try again.';
  }

  // ==============================
  // 9. FINAL FALLBACK (should rarely happen)
  // ==============================
  if (process.env.NODE_ENV === 'development') {
    console.warn('⚠️ Reached final fallback, no message extracted');
    console.groupEnd();
  }
  return `Request failed (${status})`;
};


// ==============================|| FORMIK INTEGRATION ||============================== //

/**
 * ✅ HANDLER FOR FORMIK
 * 
 * Note: This will be deprecated in favor of the new centralized
 * formErrorHandler.js (Step 3). Kept for backward compatibility.
 * 
 * @deprecated Use handleFormikError from formErrorHandler.js instead
 * @param {Error} axiosError - Axios error
 * @param {Function} setErrors - Formik setErrors
 * @param {Function} setSubmitting - Formik setSubmitting
 */
export const handleFormError = (axiosError, setErrors, setSubmitting) => {
  const errorMessage = handleApiError(axiosError);
  setErrors({ submit: errorMessage });
  setSubmitting(false);
};

// ==============================|| EXPORTS ||============================== //

export default {
  handleApiError,
  handleFormError
};