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

import { displayWarningSnackbar } from './displayError';
import { showSnackbar } from './snackbar';
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
 * - 0% success → ERROR snackbar with backend message (from errorMessage field)
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
 *   handleBulkError(res, null, { 
 *     onComplete: () => {
 *       closeModal();
 *       onComplete();
 *     }
 *   });
 * }
 * ```
 * 
 * @param {Object} responseData - Bulk operation response from backend
 * @param {Error} originalError - Original Axios error (optional, for 0% failures)
 * @param {Object} options - Handler options
 * @param {Function} options.onComplete - Callback to execute after displaying snackbar
 * @returns {boolean} true if handled, false if not a bulk operation
 */
export function handleBulkError(responseData, originalError = null, options = {}) {
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
  // STEP 2: Extract counts from summary (support both formats)
  // ====================================================================
  
  // ⭐ NEW: Support two formats
  // Format 1 (bulk operations): { requested, created/updated/deleted/archived, failed, skipped }
  // Format 2 (CSV import): { total, success, failed, skipped }
  
  const requested = summary?.requested || summary?.total || 0;
  
  // Try Format 1 first (bulk ops), then Format 2 (CSV import)
  const successCount = summary?.updated || 
                      summary?.created || 
                      summary?.deleted || 
                      summary?.archived || 
                      summary?.success ||  // ⭐ CSV import format
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
    if (process.env.NODE_ENV === 'development') {
      console.log('[handleBulkError] Total failure (0%), displaying ERROR snackbar');
    }
    
    // // ⭐ CRITICAL FIX: Use errorMessage field for 0% failures, not the summary message
    // const errorMessage = responseData.errorMessage || 
    //                     responseData.message || 
    //                     'Operation failed';
    
    // // ⭐ Extract status for proper severity mapping
    // const status = responseData.httpStatus || 
    //               responseData.status || 
    //               0;
    
    // if (process.env.NODE_ENV === 'development') {
    //   console.log('[handleBulkError] Error details:', { 
    //     errorMessage, 
    //     status,
    //     hasErrorMessage: !!responseData.errorMessage,
    //     hasMessage: !!responseData.message
    //   });
    // }

   // ---- 
    // const errorInfo = getErrorDisplayInfo(responseData);
    // const errorMessage = errorInfo.errorMessage || 'Operation failed';
    // const status = errorInfo.status || 0;

    // ---

    console.log('[RESPONSE FORMAT]', {responseData})
    // ✅ EXTRACT MESSAGE DIRECTLY FROM RESPONSE DATA
    const errorMessage = responseData.errorMessage || responseData.message ||
                    'Operation failed XXX';

    const status = responseData.httpStatus || 
                  responseData.status || responseData.error?.status ||
                  0;
    
    if (process.env.NODE_ENV === 'development') {
      console.log('[handleBulkError] Error info from getErrorDisplayInfo:', { 
        errorMessage, 
        status,
      });
    }
  
    
    // Map status to severity
    let severity = 'error';
    if (status === 404) {
      severity = 'warning';
    } else if (status === 403 || status >= 500) {
      severity = 'error';
    } else if (status >= 400) {
      severity = 'warning';
    }
    
    // Display with appropriate severity
    if (severity === 'error') {
      showSnackbar.error(errorMessage);
    } else if (severity === 'warning') {
      showSnackbar.warning(errorMessage);
    } else {
      showSnackbar.info(errorMessage);
    }
    
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