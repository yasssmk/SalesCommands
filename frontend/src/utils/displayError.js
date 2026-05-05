// frontend/src/utils/displayError.js
// ✅ UNIFIED ERROR-TO-UI BRIDGE - Single entry point for all error notifications

/**
 * Thin wrapper over the standardized snackbar helper.
 *
 * This is the ONLY module components should import to display errors and messages.
 * Provides a stable API that insulates components from snackbar implementation changes.
 *
 * All messages are in English. All UI behavior (position, duration, dedup) is standardized.
 *
 * @module utils/displayError
 */

import { showSnackbar } from "./snackbar";

// ==============================|| ERROR DISPLAY ||============================== //

/**
 * Display an error notification from a caught error object or API response
 *
 * This is the primary function for displaying API errors, network failures,
 * timeouts, and any other errors caught in try-catch blocks.
 *
 * Handles two input formats:
 * 1. Error objects (from catch blocks): { response: { status, data }, message }
 * 2. Response objects (from API calls): { success: false, error: '...', status: 404 }
 *
 * Automatically extracts user-facing message and maps to appropriate severity.
 * Inherits standardized behavior: top-right position, locked durations, deduplication.
 *
 * @param {Error|Object} error - Error object or API response object
 * @param {Object} [options={}] - Optional overrides (rarely needed)
 * @param {boolean} [options.suppressDedup=false] - Force show even if duplicate
 *
 * @example
 * // Usage with Error object (catch block):
 * try {
 *   await api.updateUser(data);
 * } catch (error) {
 *   displayErrorSnackbar(error);
 * }
 *
 * @example
 * // Usage with response object (API response):
 * const res = await deleteUser(id);
 * if (res?.success) {
 *   displaySuccessSnackbar('User deleted');
 * } else {
 *   displayErrorSnackbar(res);  // Works with response objects too!
 * }
 *
 * @example
 * // With custom handling for specific status codes:
 * try {
 *   await api.getUser(id);
 * } catch (error) {
 *   if (error.response?.status === 404) {
 *     displayInfoSnackbar('User not found');
 *   } else {
 *     displayErrorSnackbar(error);
 *   }
 * }
 */
export function displayErrorSnackbar(error, options = {}) {
  // Handle response objects from API calls (not Error objects)
  // Format: { success: false, error: 'message', status: 404 }
  if (error && !error.response && error.status && error.error) {
    // Convert response object to Error-like object for consistent handling
    const errorLike = new Error(error.error);
    errorLike.response = {
      status: error.status,
      data: { detail: error.error },
    };
    errorLike.status = error.status;
    showSnackbar.fromError(errorLike, options);
    return;
  }

  // Handle standard Error objects
  showSnackbar.fromError(error, options);
}

// ==============================|| SUCCESS DISPLAY ||============================== //

/**
 * Display a success notification
 *
 * Use for positive confirmations after successful operations.
 * Duration: 3 seconds (quick positive feedback).
 *
 * @param {string} message - Success message in English
 * @param {Object} [options={}] - Optional overrides (rarely needed)
 *
 * @example
 * displaySuccessSnackbar('User created successfully');
 *
 * @example
 * displaySuccessSnackbar('5 users updated');
 */
export function displaySuccessSnackbar(message, options = {}) {
  showSnackbar.success(message, options);
}

// ==============================|| WARNING DISPLAY ||============================== //

/**
 * Display a warning notification
 *
 * Use for warnings, partial successes, or situations requiring user attention.
 * Duration: 5 seconds (more time to read details).
 *
 * @param {string} message - Warning message in English
 * @param {Object} [options={}] - Optional overrides (rarely needed)
 *
 * @example
 * displayWarningSnackbar('Some fields could not be updated');
 *
 * @example
 * displayWarningSnackbar('5 updated, 2 failed');
 */
export function displayWarningSnackbar(message, options = {}) {
  showSnackbar.warning(message, options);
}

// ==============================|| INFO DISPLAY ||============================== //

/**
 * Display an informational notification
 *
 * Use for neutral informational messages that don't indicate success or failure.
 * Duration: 4 seconds (moderate reading time).
 *
 * @param {string} message - Info message in English
 * @param {Object} [options={}] - Optional overrides (rarely needed)
 *
 * @example
 * displayInfoSnackbar('Changes will take effect after refresh');
 *
 * @example
 * displayInfoSnackbar('Data sync in progress');
 */
export function displayInfoSnackbar(message, options = {}) {
  showSnackbar.info(message, options);
}
