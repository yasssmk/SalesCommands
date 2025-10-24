// frontend/src/utils/snackbar.js
// ✅ HELPER STANDARDISÉ pour uniformiser tous les snackbars de l'app

import { openSnackbar as openSnackbarBase } from 'api/snackbar';
import { getErrorDisplayInfo } from './errorMessages';

/**
 * ✅ STANDARD DURATIONS (locked, no per-call overrides)
 * 
 * - Info: 4s (moderate reading time)
 * - Warning: 5s (more details to read)
 * - Error: 6s (time to read and understand)
 * - Success: 3s (quick confirmation) - kept short for positive feedback
 */
const DURATIONS = {
  SUCCESS: 3000,  // Quick positive feedback
  INFO: 4000,     // Informational messages
  WARNING: 5000,  // Warnings, partial success
  ERROR: 6000     // Errors, critical messages
};

/**
 * ✅ LOCKED ANCHOR POSITION
 * Always top-right for visual consistency across the app
 */
const STANDARD_ANCHOR = {
  vertical: 'top',
  horizontal: 'right'
};

// ==============================|| DEDUPLICATION GUARD ||============================== //

/**
 * Global deduplication state (in-memory, module-scoped)
 * Prevents spam from identical messages shown within a short time window
 */
const _recentMessages = new Map(); // key: `${message}:${status}`, value: timestamp
const DEDUP_WINDOW_MS = 5000; // 5 seconds
const DEDUP_WINDOW_MS_500 = 45000 // 45 seconds
const MAX_DEDUP_ENTRIES = 50; // Prevent unbounded growth

/**
 * BEHAVIOR:
 * - Same message + same status within window → Suppressed (deduplicated)
 * - Different message within window → Shown (NEW FIX)
 * - Different status within window → Shown (NEW FIX)
 * - 403 errors → Always shown (no dedup)
 * - 500+ errors → 45s dedup window instead of 5s
 * 
 * Check if a message should be suppressed (duplicate within dedup window)
 * @param {string} message - The snackbar message
 * @param {string|number} status - The severity/status identifier
 * @returns {boolean} true if message should be shown, false if suppressed
 */
function shouldShowMessage(message, status) {
  const key = `${message}:${status}`;
  const now = Date.now();
  const lastShown = _recentMessages.get(key);
  const is_403 = status === 403; // We want user to be averted everytime he makes a forbiden request
  const is_500 = status >= 500;
  
  // Check if same message was shown recently
  if (!is_403 && !is_500 && lastShown && (now - lastShown) < DEDUP_WINDOW_MS) {
    if (process.env.NODE_ENV === 'development') {
      console.debug(`🔕 [Snackbar Dedup] Suppressed duplicate: "${message}" (${status})`);
    }
    return false; // Suppress
  }

  if (is_500 && lastShown && (now - lastShown) < DEDUP_WINDOW_MS_500) {
    if (process.env.NODE_ENV === 'development') {
      console.debug(`🔕 [Snackbar Dedup Error 500] Suppressed duplicate: "${message}" (${status})`);
    }
    return false; // Suppress
  }
  
  // Allow and record this message
  _recentMessages.set(key, now);
  
  // Cleanup old entries to prevent unbounded growth
  if (_recentMessages.size > MAX_DEDUP_ENTRIES) {
    const cutoffTime = now - Math.max(DEDUP_WINDOW_MS, DEDUP_WINDOW_MS_500);
    for (const [msgKey, timestamp] of _recentMessages.entries()) {
      if (timestamp < cutoffTime) {
        _recentMessages.delete(msgKey);
      }
    }
  }
  
  return true; // Show
}

// ==============================|| HELPER FUNCTIONS ||============================== //

/**
 * Auto-determine duration for legacy/custom cases
 * (Used by custom() method for backward compatibility)
 */
function getAutoDuration(color, message = '', hasDetails = false) {
  if (color === 'error') return DURATIONS.ERROR;
  if (color === 'warning') return DURATIONS.WARNING;
  if (color === 'info') return DURATIONS.INFO;
  
  // Success with details
  if (hasDetails || (message && message.length > 50)) {
    return DURATIONS.INFO;
  }
  
  return DURATIONS.SUCCESS;
}

// ==============================|| MAIN SNACKBAR API ||============================== //

/**
 * ✅ STANDARDIZED SNACKBAR HELPER
 * 
 * Provides consistent notification behavior across the entire app:
 * - Locked anchor position (top-right)
 * - Locked durations by severity
 * - Global deduplication (5s window)
 * - English messages only
 * 
 * Usage:
 *   showSnackbar.success('User created');
 *   showSnackbar.error('Failed to save');
 *   showSnackbar.fromError(error);
 */
export const showSnackbar = {
  /**
   * Success snackbar (3s duration)
   * For positive confirmations
   */
  success: (message, options = {}) => {
    if (!shouldShowMessage(message, 'success')) return;
    
    openSnackbarBase({
      open: true,
      message,
      variant: 'alert',
      alert: { color: 'success' },
      anchorOrigin: STANDARD_ANCHOR,
      autoHideDuration: DURATIONS.SUCCESS,
      ...options
    });
  },

  /**
   * Error snackbar (6s duration)
   * For failures and critical issues
   */
  error: (message, options = {}) => {
    if (!shouldShowMessage(message, 'error')) return;
    
    openSnackbarBase({
      open: true,
      message,
      variant: 'alert',
      alert: { color: 'error' },
      anchorOrigin: STANDARD_ANCHOR,
      autoHideDuration: DURATIONS.ERROR,
      ...options
    });
  },

  /**
   * Warning snackbar (5s duration)
   * For warnings and partial success
   */
  warning: (message, options = {}) => {
    if (!shouldShowMessage(message, 'warning')) return;
    
    openSnackbarBase({
      open: true,
      message,
      variant: 'alert',
      alert: { color: 'warning' },
      anchorOrigin: STANDARD_ANCHOR,
      autoHideDuration: DURATIONS.WARNING,
      ...options
    });
  },

  /**
   * Info snackbar (4s duration)
   * For informational messages
   */
  info: (message, options = {}) => {
    if (!shouldShowMessage(message, 'info')) return;
    
    openSnackbarBase({
      open: true,
      message,
      variant: 'alert',
      alert: { color: 'info' },
      anchorOrigin: STANDARD_ANCHOR,
      autoHideDuration: DURATIONS.INFO,
      ...options
    });
  },

  /**
   * ✅ NEW: Create snackbar from Error object
   * 
   * Automatically extracts user-facing message and maps to appropriate severity.
   * Maps backend errors (500, 4xx, timeouts, 429, network) to consistent UI notifications.
   * 
   * @param {Error} error - Axios error or Error object from API/client
   * @param {Object} [options={}] - Optional overrides (not recommended)
   * @param {boolean} [options.suppressDedup=false] - Force show even if duplicate
   * 
   * @example
   * // Basic usage in catch block:
   * try {
   *   await updateUser(data);
   * } catch (error) {
   *   showSnackbar.fromError(error);
   * }
   * 
   * @example
   * // With custom handling:
   * try {
   *   await deleteUser(id);
   * } catch (error) {
   *   if (error.response?.status === 404) {
   *     showSnackbar.info('User already deleted');
   *   } else {
   *     showSnackbar.fromError(error);
   *   }
   * }
   */
  fromError: (error, options = {}) => {
    if (!error) {
      console.warn('[showSnackbar.fromError] Called with null/undefined error');
      return;
    }

    // Extract structured error info using existing utility
    const errorInfo = getErrorDisplayInfo(error);
    
    if (!errorInfo) {
      console.warn('[showSnackbar.fromError] Could not extract error info');
      return;
    }

    const { message, severity, status } = errorInfo;
    
    // Map severity to MUI colors (info/warning/error only)
    // severity from getErrorDisplayInfo is: 'error' | 'warning' | 'info'
    const color = severity === 'info' ? 'info' 
                : severity === 'warning' ? 'warning' 
                : 'error';
    
    // Dedup check (unless explicitly suppressed)
    if (!options.suppressDedup && !shouldShowMessage(message, status)) {
      return;
    }

    // Select appropriate duration based on severity
    const duration = color === 'error' ? DURATIONS.ERROR
                   : color === 'warning' ? DURATIONS.WARNING
                   : DURATIONS.INFO;

    // Show snackbar with locked standards
    openSnackbarBase({
      open: true,
      message,
      variant: 'alert',
      alert: { color },
      anchorOrigin: STANDARD_ANCHOR,
      autoHideDuration: duration,
      ...options
    });
  },

  /**
   * Custom snackbar (for special cases, backward compatibility)
   * Use specific methods (success/error/warning/info) when possible
   */
  custom: (message, color, options = {}) => {
    if (!shouldShowMessage(message, color)) return;
    
    const duration = options.duration ?? getAutoDuration(color, message, options.hasDetails);
    
    openSnackbarBase({
      open: true,
      message,
      variant: 'alert',
      alert: { color },
      anchorOrigin: STANDARD_ANCHOR,
      autoHideDuration: duration,
      ...options
    });
  }
};

// ==============================|| BACKWARD COMPATIBILITY ||============================== //

/**
 * ✅ Keep old import working during transition
 * Components can still import { openSnackbar } from 'api/snackbar'
 */
export { openSnackbar as openSnackbarBase } from 'api/snackbar';

// Default export
export default showSnackbar;