// frontend/src/utils/validators.js

/**
 * Client-side validation utilities for form inputs and API calls.
 * 
 * Purpose:
 * - Validate UUIDs before sending to backend
 * - Sanitize string inputs (trim whitespace)
 * - Prevent 400/500 errors from malformed data
 * - Improve data quality and user experience
 * 
 * Phase 5.3 - Security & Robustness
 */

// ==============================|| UUID VALIDATION ||============================== //

/**
 * UUID v4 regex pattern
 * Format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
 * where x is any hexadecimal digit and y is one of 8, 9, A, or B
 */
const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/**
 * Validate if a value is a valid UUID v4.
 * 
 * @param {*} value - Value to validate
 * @returns {boolean} - True if valid UUID v4, false otherwise
 * 
 * @example
 * isValidUUID('550e8400-e29b-41d4-a716-446655440000') // true
 * isValidUUID('invalid-uuid') // false
 * isValidUUID(null) // false
 * isValidUUID('') // false
 */
export function isValidUUID(value) {
  // Handle null, undefined, non-string
  if (!value || typeof value !== 'string') {
    return false;
  }

  // Trim and test against UUID v4 pattern
  return UUID_V4_REGEX.test(value.trim());
}

/**
 * Validate multiple UUIDs at once.
 * Useful for batch operations or form validation.
 * 
 * @param {Array<*>} values - Array of values to validate
 * @returns {boolean} - True if ALL values are valid UUIDs, false otherwise
 * 
 * @example
 * areValidUUIDs(['550e8400-e29b-41d4-a716-446655440000', '6ba7b810-9dad-11d1-80b4-00c04fd430c8']) // true
 * areValidUUIDs(['valid-uuid', 'invalid']) // false
 * areValidUUIDs([]) // true (empty array is valid)
 */
export function areValidUUIDs(values) {
  if (!Array.isArray(values)) {
    return false;
  }

  // Empty array is considered valid (no invalid UUIDs)
  if (values.length === 0) {
    return true;
  }

  return values.every((value) => isValidUUID(value));
}

// ==============================|| STRING SANITIZATION ||============================== //

/**
 * Safely trim a string value.
 * Handles null, undefined, and non-string values.
 * 
 * @param {*} value - Value to trim
 * @returns {string|null} - Trimmed string, or null if input is null/undefined/empty
 * 
 * @example
 * trimString('  hello  ') // 'hello'
 * trimString('') // null
 * trimString(null) // null
 * trimString(undefined) // null
 * trimString(123) // '123' (converted to string)
 */
export function trimString(value) {
  // Handle null/undefined
  if (value === null || value === undefined) {
    return null;
  }

  // Convert to string and trim
  const trimmed = String(value).trim();

  // Return null for empty strings after trim
  return trimmed.length > 0 ? trimmed : null;
}

/**
 * Sanitize email address (trim + lowercase).
 * Best practice for email storage and comparison.
 * 
 * @param {*} email - Email address to sanitize
 * @returns {string|null} - Sanitized email or null if invalid
 * 
 * @example
 * sanitizeEmail('  John.Doe@Example.COM  ') // 'john.doe@example.com'
 * sanitizeEmail('') // null
 * sanitizeEmail(null) // null
 */
export function sanitizeEmail(email) {
  const trimmed = trimString(email);

  if (!trimmed) {
    return null;
  }

  // Convert to lowercase for consistent storage
  return trimmed.toLowerCase();
}

/**
 * Sanitize an object's string properties.
 * Recursively trims all string values in an object.
 * 
 * @param {Object} obj - Object to sanitize
 * @param {Array<string>} fields - Optional array of field names to sanitize (default: all)
 * @returns {Object} - New object with sanitized strings
 * 
 * @example
 * sanitizeObject({ name: '  John  ', email: '  test@example.com  ' })
 * // { name: 'John', email: 'test@example.com' }
 * 
 * sanitizeObject({ name: '  John  ', age: 25 }, ['name'])
 * // { name: 'John', age: 25 }
 */
export function sanitizeObject(obj, fields = null) {
  if (!obj || typeof obj !== 'object') {
    return obj;
  }

  const sanitized = { ...obj };
  const keysToSanitize = fields || Object.keys(sanitized);

  keysToSanitize.forEach((key) => {
    if (key in sanitized && typeof sanitized[key] === 'string') {
      const trimmed = trimString(sanitized[key]);
      sanitized[key] = trimmed === null ? '' : trimmed;
    }
  });

  return sanitized;
}

// ==============================|| ID VALIDATION ||============================== //

/**
 * Validate if a value can be used as an ID (UUID or integer).
 * Accepts both UUID strings and numeric IDs.
 * 
 * @param {*} value - Value to validate
 * @returns {boolean} - True if valid ID, false otherwise
 * 
 * @example
 * isValidId('550e8400-e29b-41d4-a716-446655440000') // true (UUID)
 * isValidId(123) // true (numeric ID)
 * isValidId('123') // true (numeric string)
 * isValidId('') // false
 * isValidId(null) // false
 */
export function isValidId(value) {
  // Handle null/undefined
  if (value === null || value === undefined) {
    return false;
  }

  // Check if it's a valid UUID
  if (typeof value === 'string' && isValidUUID(value)) {
    return true;
  }

  // Check if it's a valid number (integer or numeric string)
  if (typeof value === 'number' && Number.isInteger(value) && value > 0) {
    return true;
  }

  // Check if it's a numeric string
  if (typeof value === 'string') {
    const num = Number(value);
    return !isNaN(num) && Number.isInteger(num) && num > 0;
  }

  return false;
}

// ==============================|| FORM VALIDATION HELPERS ||============================== //

/**
 * Validate form payload before API submission.
 * Checks for required UUIDs and sanitizes strings.
 * 
 * @param {Object} payload - Form data to validate
 * @param {Array<string>} requiredUUIDs - Field names that must be valid UUIDs
 * @returns {Object} - { valid: boolean, errors: Object, sanitized: Object }
 * 
 * @example
 * const result = validateFormPayload(
 *   { role: 'invalid-uuid', email: '  test@example.com  ' },
 *   ['role']
 * );
 * // { valid: false, errors: { role: 'Invalid role ID' }, sanitized: {...} }
 */
export function validateFormPayload(payload, requiredUUIDs = []) {
  const errors = {};
  const sanitized = { ...payload };

  // Validate UUID fields
  requiredUUIDs.forEach((field) => {
    const value = sanitized[field];

    // Skip if field is empty/null (nullable fields)
    if (!value) {
      return;
    }

    if (!isValidUUID(value)) {
      errors[field] = `Invalid ${field} ID`;
    }
  });

  // Sanitize string fields
  Object.keys(sanitized).forEach((key) => {
    if (typeof sanitized[key] === 'string') {
      const trimmed = trimString(sanitized[key]);
      sanitized[key] = trimmed === null ? '' : trimmed;
    }
  });

  return {
    valid: Object.keys(errors).length === 0,
    errors,
    sanitized
  };
}

/**
 * Create a validation error message for display.
 * Converts validation errors object into user-friendly message.
 * 
 * @param {Object} errors - Validation errors object
 * @returns {string} - Formatted error message
 * 
 * @example
 * formatValidationErrors({ role: 'Invalid role ID', email: 'Email required' })
 * // 'Invalid role ID. Email required.'
 */
export function formatValidationErrors(errors) {
  if (!errors || Object.keys(errors).length === 0) {
    return '';
  }

  return Object.values(errors).join('. ') + '.';
}

// ==============================|| EXPORTS ||============================== //

export default {
  // UUID validation
  isValidUUID,
  areValidUUIDs,

  // String sanitization
  trimString,
  sanitizeEmail,
  sanitizeObject,

  // ID validation
  isValidId,

  // Form helpers
  validateFormPayload,
  formatValidationErrors
};