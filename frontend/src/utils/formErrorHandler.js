// frontend/src/utils/formErrorHandler.js

/**
 * ✅ CENTRALIZED FORM ERROR HANDLER (MVP-FRIENDLY)
 * 
 * Intelligent error handling for Formik forms:
 * - 4XX with field validation → setFieldError() for each field
 * - 4XX generic (no fields) → snackbar
 * - 5XX / network / timeout → snackbar
 * - All error messages in English
 * 
 * This replaces scattered displayErrorSnackbar() calls in forms with
 * a single, intelligent handler that decides the best UX approach.
 * 
 * @module utils/formErrorHandler
 */

import { displayErrorSnackbar } from './displayError';
import { getErrorDisplayInfo } from './errorMessages';

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
 * ✅ Extract field-level validation errors from response
 * 
 * Handles common DRF validation formats:
 * - {field: ["error"]} → {field: "error"}
 * - {field: "error"} → {field: "error"}
 * - {field: ["error1", "error2"]} → {field: "error1. error2."}
 * 
 * @param {Object} data - Response data from backend
 * @returns {Object|null} Field errors object or null if no field errors
 */
const extractFieldErrors = (data) => {
  if (!isPlainObject(data)) {
    return null;
  }
  
  // Skip if data has standard non-field keys (these are general errors)
  const nonFieldKeys = ['detail', 'error', 'message', 'non_field_errors'];
  const hasOnlyNonFieldKeys = Object.keys(data).every(key => nonFieldKeys.includes(key));
  
  if (hasOnlyNonFieldKeys) {
    return null;
  }
  
  const fieldErrors = {};
  let foundFieldError = false;
  
  Object.entries(data).forEach(([field, value]) => {
    // Skip meta fields
    if (nonFieldKeys.includes(field)) {
      return;
    }
    
    // Extract error message from various formats
    let errorMessage = null;
    
    if (typeof value === 'string') {
      // Direct string: {email: "Invalid email"}
      errorMessage = value;
    } else if (Array.isArray(value) && value.length > 0) {
      // Array of strings: {email: ["Invalid email"]}
      const stringMessages = value
        .filter(v => typeof v === 'string')
        .map(v => v.trim())
        .filter(v => v.length > 0);
      
      if (stringMessages.length > 0) {
        errorMessage = stringMessages.join('. ');
        if (!errorMessage.endsWith('.')) {
          errorMessage += '.';
        }
      }
    } else if (isPlainObject(value)) {
      // Nested object: {user: {email: ["Invalid"]}}
      // For forms, we typically flatten: user.email → email
      // Or concatenate messages if multiple fields
      const nestedMessages = [];
      Object.values(value).forEach(nestedVal => {
        if (typeof nestedVal === 'string') {
          nestedMessages.push(nestedVal);
        } else if (Array.isArray(nestedVal)) {
          nestedVal.forEach(item => {
            if (typeof item === 'string') {
              nestedMessages.push(item);
            }
          });
        }
      });
      
      if (nestedMessages.length > 0) {
        errorMessage = nestedMessages.join('. ');
        if (!errorMessage.endsWith('.')) {
          errorMessage += '.';
        }
      }
    }
    
    if (errorMessage) {
      fieldErrors[field] = errorMessage;
      foundFieldError = true;
    }
  });
  
  return foundFieldError ? fieldErrors : null;
};

/**
 * ✅ Check if error should show field-level errors vs snackbar
 * 
 * Field-level errors are appropriate when:
 * - Status is 4XX (client error)
 * - Response contains field-specific validation errors
 * - Not a generic 401/403/404/429
 * 
 * @param {number} status - HTTP status code
 * @param {Object} fieldErrors - Extracted field errors
 * @returns {boolean} true if should use field errors
 */
const shouldUseFieldErrors = (status, fieldErrors) => {
  // Must be 4XX
  if (status < 400 || status >= 500) {
    return false;
  }
  
  // Skip auth/rate-limit errors (always snackbar)
  if (status === 401 || status === 403 || status === 429) {
    return false;
  }
  
  // Must have field errors
  if (!fieldErrors || Object.keys(fieldErrors).length === 0) {
    return false;
  }
  
  return true;
};

// ==============================|| MAIN HANDLER ||============================== //

/**
 * ✅ HANDLE FORMIK ERROR - Intelligent routing to field errors or snackbar
 * 
 * This is the main entry point for all form error handling.
 * Use this in all Formik onSubmit handlers instead of displayErrorSnackbar.
 * 
 * Decision tree:
 * 1. Extract status and data from error
 * 2. Try to extract field-level validation errors
 * 3. If 4XX + has field errors → setFieldError() for each field + optional snackbar
 * 4. Otherwise → snackbar only
 * 
 * @param {Error|Object} error - Error from API call (Axios error or result object)
 * @param {Object} formik - Formik instance (from useFormik hook)
 * @param {Object} [options={}] - Optional configuration
 * @param {boolean} [options.showSnackbarWithFields=false] - Show snackbar even when using field errors
 * @param {boolean} [options.setSubmittingFalse=true] - Automatically call setSubmitting(false)
 * @param {string} [options.fallbackMessage] - Custom fallback message if extraction fails
 * 
 * @example
 * // Basic usage in form onSubmit
 * const formik = useFormik({
 *   onSubmit: async (values, { setSubmitting }) => {
 *     try {
 *       const result = await insertUser(values);
 *       if (result.success) {
 *         displaySuccessSnackbar('User created');
 *         closeModal();
 *       } else {
 *         handleFormikError(result, formik); // 🆕 One call handles everything
 *       }
 *     } catch (err) {
 *       handleFormikError(err, formik); // 🆕 Works with exceptions too
 *     }
 *   }
 * });
 * 
 * @example
 * // With options
 * handleFormikError(error, formik, {
 *   showSnackbarWithFields: true, // Show snackbar even if field errors exist
 *   setSubmittingFalse: true,     // Auto-call setSubmitting(false)
 * });
 */
export const handleFormikError = (error, formik, options = {}) => {
  const {
    showSnackbarWithFields = false,
    setSubmittingFalse = true,
    fallbackMessage = null
  } = options;
  
  if (process.env.NODE_ENV === 'development') {
    console.group('🔍 [handleFormikError] Processing form error');
    console.log('Error:', error);
    console.log('Options:', options);
  }
  
  // ====================================================================
  // STEP 1: Normalize error object
  // ====================================================================
  // Handle both Axios errors and API result objects
  let normalizedError = error;
  
  // If it's a result object {success: false, error, status}, convert to Error-like
  if (error && !error.response && error.status && (error.error || error.message)) {
    normalizedError = new Error(error.error || error.message);
    normalizedError.response = {
      status: error.status,
      data: error.data || { detail: error.error }
    };
    normalizedError.status = error.status;
  }
  
  // ====================================================================
  // STEP 2: Extract structured error info
  // ====================================================================
  const errorInfo = getErrorDisplayInfo(normalizedError);
  const { status, message } = errorInfo;
  
  if (process.env.NODE_ENV === 'development') {
    console.log('Status:', status);
    console.log('General message:', message);
  }
  
  // ====================================================================
  // STEP 3: Try to extract field-level errors (4XX validation only)
  // ====================================================================
  const responseData = normalizedError?.response?.data;
  const fieldErrors = extractFieldErrors(responseData);
  
  if (process.env.NODE_ENV === 'development') {
    console.log('Field errors extracted:', fieldErrors);
  }
  
  const useFieldErrors = shouldUseFieldErrors(status, fieldErrors);
  
  if (process.env.NODE_ENV === 'development') {
    console.log('Decision: Use field errors?', useFieldErrors);
  }
  
  // ====================================================================
  // STEP 4: Apply field errors to Formik
  // ====================================================================
  if (useFieldErrors && fieldErrors) {
    // Set error for each field
    Object.entries(fieldErrors).forEach(([field, errorMsg]) => {
      if (formik.setFieldError) {
        formik.setFieldError(field, errorMsg);
        
        if (process.env.NODE_ENV === 'development') {
          console.log(`✅ Set field error: ${field} = "${errorMsg}"`);
        }
      }
    });
    
    // Optionally show snackbar with summary
    if (showSnackbarWithFields) {
      const fieldCount = Object.keys(fieldErrors).length;
      const summaryMessage = fieldCount === 1 
        ? 'Please fix the validation error below.'
        : `Please fix ${fieldCount} validation errors below.`;
      
      displayErrorSnackbar({
        message: summaryMessage,
        status: status
      });
      
      if (process.env.NODE_ENV === 'development') {
        console.log('📢 Snackbar shown (with field errors):', summaryMessage);
      }
    }
    
    if (process.env.NODE_ENV === 'development') {
      console.log('✅ Field errors applied to Formik');
      console.groupEnd();
    }
    
    // Stop submitting state
    if (setSubmittingFalse && formik.setSubmitting) {
      formik.setSubmitting(false);
    }
    
    return; // Done - field errors handled
  }
  
  // ====================================================================
  // STEP 5: Show snackbar for non-field errors
  // ====================================================================
  // Use cases:
  // - 5XX server errors
  // - Network/timeout errors
  // - 4XX without field details (401, 403, 404, generic 400)
  // - 429 rate limit
  
  const snackbarMessage = fallbackMessage || message;
  
  displayErrorSnackbar(normalizedError);
  
  if (process.env.NODE_ENV === 'development') {
    console.log('📢 Snackbar shown:', snackbarMessage);
    console.groupEnd();
  }
  
  // Stop submitting state
  if (setSubmittingFalse && formik.setSubmitting) {
    formik.setSubmitting(false);
  }
};

// ==============================|| CONVENIENCE HELPERS ||============================== //

/**
 * ✅ Handle error with field errors AND snackbar
 * 
 * Convenience wrapper that always shows both field errors and snackbar.
 * Useful for important errors that need maximum visibility.
 * 
 * @param {Error|Object} error - Error object
 * @param {Object} formik - Formik instance
 */
export const handleFormikErrorWithSnackbar = (error, formik) => {
  handleFormikError(error, formik, {
    showSnackbarWithFields: true,
    setSubmittingFalse: true
  });
};

/**
 * ✅ Handle error with custom message
 * 
 * Use when you want to override the extracted message.
 * 
 * @param {Error|Object} error - Error object
 * @param {Object} formik - Formik instance
 * @param {string} customMessage - Custom message to display
 */
export const handleFormikErrorWithMessage = (error, formik, customMessage) => {
  handleFormikError(error, formik, {
    fallbackMessage: customMessage,
    setSubmittingFalse: true
  });
};

// ==============================|| EXPORTS ||============================== //

export default {
  handleFormikError,
  handleFormikErrorWithSnackbar,
  handleFormikErrorWithMessage
};