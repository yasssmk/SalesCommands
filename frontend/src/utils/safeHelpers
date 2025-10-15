// frontend/src/utils/safeHelpers.js
/**
 * ✅ SAFE DESTRUCTURING HELPERS
 * 
 * Utilities to prevent "Right side of assignment cannot be destructured" errors
 * across the entire application.
 * 
 * Use these patterns everywhere you destructure potentially undefined/null values.
 * 
 * @module utils/safeHelpers
 */

// ==============================|| SAFE OBJECT ACCESS ||============================== //

/**
 * Safely get properties from an object that might be null/undefined
 * 
 * @param {Object|null|undefined} obj - Object to extract from
 * @param {Object} defaults - Default values for each property
 * @returns {Object} Object with guaranteed properties
 * 
 * @example
 * // Instead of: const { message, status } = error.response;
 * const { message, status } = safeGet(error?.response, { 
 *   message: 'Unknown error', 
 *   status: 0 
 * });
 * 
 * @example
 * // With nested access:
 * const { title, severity } = safeGet(getErrorDisplayInfo(error), {
 *   title: 'Error',
 *   severity: 'error'
 * });
 */
export function safeGet(obj, defaults = {}) {
  if (!obj || typeof obj !== 'object') {
    return defaults;
  }
  
  const result = {};
  for (const key in defaults) {
    result[key] = obj[key] !== undefined ? obj[key] : defaults[key];
  }
  
  return result;
}

// ==============================|| SAFE ARRAY ACCESS ||============================== //

/**
 * Safely destructure from arrays that might be null/undefined/empty
 * 
 * @param {Array|null|undefined} arr - Array to extract from
 * @param {number} index - Index to extract
 * @param {*} defaultValue - Default if array is invalid or index missing
 * @returns {*} Value at index or default
 * 
 * @example
 * // Instead of: const [first] = messages;
 * const first = safeArrayGet(messages, 0, null);
 * 
 * @example
 * // Multiple values:
 * const first = safeArrayGet(items, 0, {});
 * const second = safeArrayGet(items, 1, {});
 */
export function safeArrayGet(arr, index, defaultValue = null) {
  if (!Array.isArray(arr) || arr.length <= index) {
    return defaultValue;
  }
  
  return arr[index] !== undefined ? arr[index] : defaultValue;
}

// ==============================|| SAFE STRING OPERATIONS ||============================== //

/**
 * Safely call string methods on values that might not be strings
 * 
 * @param {*} value - Value to treat as string
 * @param {string} method - String method to call ('trim', 'toLowerCase', etc)
 * @param {string} fallback - Fallback if not a string
 * @returns {string} Result or fallback
 * 
 * @example
 * // Instead of: backendMessage.trim()
 * safeString(backendMessage, 'trim', '')
 * 
 * @example
 * // Check if contains:
 * safeString(message, 'includes', '', 'Network')
 */
export function safeString(value, method = 'toString', fallback = '', ...args) {
  if (typeof value !== 'string') {
    return fallback;
  }
  
  if (typeof value[method] === 'function') {
    try {
      return value[method](...args);
    } catch {
      return fallback;
    }
  }
  
  return value;
}

// ==============================|| SAFE FUNCTION CALL ||============================== //

/**
 * Safely call a function that might return null/undefined
 * 
 * @param {Function} fn - Function to call
 * @param {*} fallback - Fallback if function returns null/undefined or throws
 * @param  {...any} args - Arguments to pass to function
 * @returns {*} Function result or fallback
 * 
 * @example
 * // Instead of: const info = getErrorDisplayInfo(error) || { ... };
 * const info = safeCall(
 *   () => getErrorDisplayInfo(error),
 *   { severity: 'error', message: 'Unknown error' }
 * );
 */
export function safeCall(fn, fallback, ...args) {
  try {
    const result = fn(...args);
    return result !== null && result !== undefined ? result : fallback;
  } catch (error) {
    if (process.env.NODE_ENV === 'development') {
      console.warn('[safeCall] Function threw error:', error);
    }
    return fallback;
  }
}

// ==============================|| VALIDATION HELPERS ||============================== //

/**
 * Check if value is a valid object (not null, not array)
 */
export function isValidObject(value) {
  return value !== null && 
         value !== undefined && 
         typeof value === 'object' && 
         !Array.isArray(value);
}

/**
 * Check if value is a non-empty string
 */
export function isNonEmptyString(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

/**
 * Check if value is a valid error object
 */
export function isValidError(error) {
  return error instanceof Error || 
         (isValidObject(error) && (error.message || error.response));
}

// ==============================|| USAGE EXAMPLES ||============================== //

/**
 * BEFORE (UNSAFE):
 * 
 * const { message, status } = error.response;  // ❌ Crash if response is undefined
 * const [first] = messages;  // ❌ Crash if messages is undefined
 * const text = backendMessage.trim();  // ❌ Crash if not a string
 * const { title } = getErrorDisplayInfo(error);  // ❌ Crash if returns null
 * 
 * AFTER (SAFE):
 * 
 * const { message, status } = safeGet(error?.response, { message: '', status: 0 });
 * const first = safeArrayGet(messages, 0, null);
 * const text = safeString(backendMessage, 'trim', '');
 * const { title } = safeCall(() => getErrorDisplayInfo(error), { title: 'Error' });
 */

// ==============================|| EXPORTS ||============================== //

export default {
  safeGet,
  safeArrayGet,
  safeString,
  safeCall,
  isValidObject,
  isNonEmptyString,
  isValidError
};