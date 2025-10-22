// frontend/src/utils/bulkErrorHandler.js

/**
 * ✅ BULK ERROR HANDLER - Centralized error handling for bulk operations
 * 
 * This utility provides consistent error handling for bulk operations across the app:
 * - Analyzes bulk operation responses (success, summary, results)
 * - Displays appropriate snackbars (error/warning) with details
 * - Executes onComplete callback for modal closure
 * 
 * Used by components WITHOUT Formik (e.g., AlertUserBulkDelete).
 * Components WITH Formik continue using handleFormikError.
 * 
 * @module utils/bulkErrorHandler
 */

import { displayErrorSnackbar, displayWarningSnackbar } from './displayError';

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
 * Detect if response is a bulk operation response
 * 
 * Bulk operations have this structure:
 * {
 *   success: true | 'partial' | false,
 *   summary: { requested, created/updated/deleted/archived, failed, skipped },
 *   results: { success: [], failed: [], skipped: [] },
 *   message: "..."
 * }
 * 
 * @param {Object} data - Response data from backend
 * @returns {boolean} true if bulk operation
 */
const isBulkOperation = (data) => {
  if (!isPlainObject(data)) {
    return false;
  }
  
  const hasSummary = data.summary && isPlainObject(data.summary);
  const hasResults = data.results && isPlainObject(data.results);
  const hasValidSuccess = data.success !== undefined && 
                         (data.success === true || 
                          data.success === false || 
                          data.success === 'partial');
  
  return hasSummary && hasResults && hasValidSuccess;
};

// ==============================|| MAIN HANDLER ||============================== //

/**
 * ✅ HANDLE BULK OPERATION ERRORS
 * 
 * Analyzes bulk operation responses and displays appropriate snackbars.
 * 
 * **Behavior**:
 * - 0% success → ERROR snackbar with backend message
 * - 1-99% success → WARNING snackbar with counts
 * - Always executes onComplete callback at the end
 * 
 * **Usage**:
 * ```javascript
 * const res = await bulkDeleteUsers(...);
 * 
 * if (res?.success === true) {
 *   displaySuccessSnackbar('Users deleted');
 * } else if (res?.isTimeout) {
 *   // Wait for sync
 * } else {
 *   handleBulkError(res, { 
 *     onComplete: () => {
 *       closeModal();
 *       onComplete();
 *     }
 *   });
 * }
 * ```
 * 
 * @param {Object} responseData - Bulk operation response from backend
 * @param {Object} options - Handler options
 * @param {Function} options.onComplete - Callback to execute after displaying snackbar
 * @returns {boolean} true if handled, false if not a bulk operation
 */
export function handleBulkError(responseData, options = {}) {
  const { onComplete = null } = options;
  
  // ====================================================================
  // STEP 1: Validate input
  // ====================================================================
  
  if (!responseData || !isPlainObject(responseData)) {
    if (process.env.NODE_ENV === 'development') {
      console.warn('[handleBulkError] Invalid responseData:', responseData);
    }
    return false;
  }
  
  // Check if this is a bulk operation response
  if (!isBulkOperation(responseData)) {
    if (process.env.NODE_ENV === 'development') {
      console.warn('[handleBulkError] Not a bulk operation response:', responseData);
    }
    return false;
  }
  
  const { success, summary, results, message: backendMessage } = responseData;
  
  if (process.env.NODE_ENV === 'development') {
    console.log('[handleBulkError] Processing bulk error:', {
      success,
      summary,
      resultsKeys: Object.keys(results || {})
    });
  }
  
  // ====================================================================
  // STEP 2: Extract counts from summary
  // ====================================================================
  
  const requested = summary?.requested || 0;
  
  // The success count can be under different keys depending on operation
  const successCount = summary?.updated || 
                      summary?.created || 
                      summary?.deleted || 
                      summary?.archived || 
                      0;
  
  const failedCount = summary?.failed || 0;
  const skippedCount = summary?.skipped || 0;
  
  // Calculate success rate
  const successRate = requested > 0 ? (successCount / requested) * 100 : 0;
  
  if (process.env.NODE_ENV === 'development') {
    console.log('[handleBulkError] Counts:', {
      requested,
      successCount,
      failedCount,
      skippedCount,
      successRate: `${successRate.toFixed(1)}%`
    });
  }
  
  // ====================================================================
  // STEP 3: Determine appropriate snackbar and message
  // ====================================================================
  
  let snackbarDisplayed = false;
  
  // Case 1: Total failure (0% success)
  if (successRate === 0) {
    // Use backend message (most accurate and detailed)
    const errorMessage = backendMessage || 
                        `Operation failed: all ${requested} items failed`;
    
    if (process.env.NODE_ENV === 'development') {
      console.log('[handleBulkError] Total failure (0%), displaying ERROR snackbar');
    }
    
    displayErrorSnackbar(errorMessage)
    
    snackbarDisplayed = true;
  }
  
  // Case 2: Partial success (1-99%)
  else if (successRate < 100) {
    // Construct detailed message with counts
    const warningMessage = `${successCount}/${requested} items processed successfully. ${failedCount} failed${skippedCount > 0 ? `, ${skippedCount} skipped` : ''}.`;
    
    if (process.env.NODE_ENV === 'development') {
      console.log('[handleBulkError] Partial success, displaying WARNING snackbar');
    }
    
    displayWarningSnackbar(warningMessage);
    
    snackbarDisplayed = true;
  }
  
  // Case 3: Unexpected - 100% success should not reach this handler
  else {
    if (process.env.NODE_ENV === 'development') {
      console.warn('[handleBulkError] 100% success passed to error handler - this should not happen');
    }
    
    // Fallback: display backend message as warning
    displayWarningSnackbar(backendMessage || 'Operation completed with unexpected status');
    snackbarDisplayed = true;
  }
  
  // ====================================================================
  // STEP 4: Execute onComplete callback
  // ====================================================================
  
  if (onComplete && typeof onComplete === 'function') {
    if (process.env.NODE_ENV === 'development') {
      console.log('[handleBulkError] Executing onComplete callback');
    }
    
    // Small delay to ensure snackbar is displayed before modal closes
    setTimeout(() => {
      onComplete();
    }, 100);
  }
  
  return snackbarDisplayed;
}

// ==============================|| DEFAULT EXPORT ||============================== //

export default {
  handleBulkError
};
