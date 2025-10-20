// frontend/src/components/table/ErrorDisplay.jsx

import PropTypes from 'prop-types';
import { Fragment, useEffect, useCallback } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Button from '@mui/material/Button';
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import TableRow from '@mui/material/TableRow';
import TableCell from '@mui/material/TableCell';
import Typography from '@mui/material/Typography';

// assets
import { WarningOutlined } from '@ant-design/icons';
import ReloadOutlined from '@ant-design/icons/ReloadOutlined';

// utils
import { getErrorDisplayInfo } from 'utils/errorMessages';
import { displayErrorSnackbar } from 'utils/displayError';
import { useRetryCountdown } from 'hooks/useRetryCountdown';
import { safeGet } from 'utils/safeHelpers';
import { 
  isNetworkError, 
  isServerError, 
  isTimeoutError 
} from 'utils/retryLogic';

// ==============================|| ERROR DISPLAY COMPONENT ||============================== //

/**
 * ✅ INTELLIGENT ERROR DISPLAY with contextual UI
 * 
 * Reusable error display component for React Tables.
 * Adapts UI based on error type and cache availability.
 * 
 * Behavior by error type:
 * - 500/5xx, 408, 0 (Network) → Snackbar + (Cached table OR Empty with retry)
 * - 404 (Not Found, invalid pagination) → Contextual empty table (no snackbar)
 * - 403 (Forbidden) → Snackbar + (Cached table OR Empty with retry)
 * - 429 (Rate Limit) → Alert with countdown
 * - Other 4xx → Alert with retry button (fallback)
 * 
 * @param {Object} props - Component props
 * @param {Error} props.error - Error object from API call
 * @param {Function} props.onRetry - Retry callback function
 * @param {boolean} props.isRetrying - Whether a retry is in progress
 * @param {Array} props.columns - Table columns (for colSpan calculation)
 * @param {string} props.globalFilter - Current search/filter term
 * @param {Array} props.data - Current data array (to detect cached data)
 * @param {string} props.emptyMessage - Custom empty state message (optional)
 * @param {string} props.emptyDescription - Custom empty state description (optional)
 */
function ErrorDisplay({ 
  error, 
  onRetry, 
  isRetrying, 
  columns, 
  globalFilter, 
  data,
  cachedData,
  emptyMessage = 'No data found',
  emptyDescription = 'Start by adding your first item to the system'
}) {
  const errorInfo = getErrorDisplayInfo(error);

  const { 
    severity = 'error', 
    message = 'An error occurred', 
    status = 0, 
    title = 'Error',
    isRetryable = false 
  } = safeGet(errorInfo, {
    severity: 'error',
    message: 'An error occurred',
    status: 0,
    title: 'Error',
    isRetryable: false
  });
  
  // ✅ Hook countdown for 429 rate limiting
  const secondsLeft = useRetryCountdown(error);

  // ✅ Check if we have cached data available
  const hasCachedData = data && Array.isArray(data) && data.length > 0;

  const handleOnRetryClick = useCallback(() => {
    // petit toast pour feedback immédiat
    displayErrorSnackbar(error);
    // déclenche le retry immédiat (mutate) passé par la table
    if (onRetry) onRetry();
    }, [error, onRetry]);

  // ==============================|| USE CENTRALIZED RETRY LOGIC ||============================== //
  
  /**
   * ✅ Use helpers from retryLogic.js for consistent error detection
   * This ensures ErrorDisplay uses THE SAME logic as ProviderWrapper
   */
  const isNetwork = isNetworkError(error);
  const isServer = isServerError(error);
  const isTimeout = isTimeoutError(error);

  // Combined check for temporary errors
//   const isTemporaryError = isNetwork || isServer || isTimeout || status === 403;
  const isTemporaryError = isNetwork || isServer || isTimeout || status === 403;

  // ✅ Debug log in development
  if (process.env.NODE_ENV === 'development') {
    console.log('[ErrorDisplay] Error classification:', {
      status,
      isNetwork,
      isServer,
      isTimeout,
      isTemporaryError,
      hasCachedData,
      errorCode: error?.code,
      hasResponse: !!error?.response
    });
  }

  // ==============================|| SNACKBAR TRIGGER ||============================== //
  
  // ✅ Trigger snackbar once on mount for temporary errors
  useEffect(() => {
  const shouldShowSnackbar = isServer || isTimeout || status === 403;
  
  if (shouldShowSnackbar) {
    displayErrorSnackbar(error);
  }
}, [error, isServer, isTimeout, status]);

  // ==============================|| CASE 1: SERVER ERRORS / TIMEOUT / NETWORK ||============================== //
  
  /**
   * For temporary errors (500, 408, 0):
   * - Show snackbar (handled above)
   * - If cached data exists → Return nothing (let table show cached data)
   * - If no cache → Show empty table with retry button
   */
   if (isTemporaryError) {
    // ✅ If we have cached data, don't render error UI - let the table show cached data
    if (hasCachedData) {
        if (process.env.NODE_ENV === 'development') {
            console.log('[ErrorDisplay] Showing cached data during temporary error');
      }
        return cachedData; // Table will render normally with cached data
    }

    // ✅ No cache available - show empty table with retry button
    return (
      <TableRow>
        <TableCell colSpan={columns.length} align="center" sx={{ py: 6 }}>
          <Stack spacing={2} alignItems="center">
            <Typography variant="body2" color="text.secondary">
              Unable to load data. Please try again.
            </Typography>
            {isRetryable && (
              <Button
                variant="outlined"
                size="small"
                onClick={handleOnRetryClick}
                disabled={isRetrying}
                startIcon={<ReloadOutlined spin={isRetrying} />}
              >
                {isRetrying ? 'Retrying...' : 'Retry'}
              </Button>
            )}
          </Stack>
        </TableCell>
      </TableRow>
    );
  }

  // ==============================|| CASE 2: NOT FOUND (404) ||============================== //
  
  /**
   * For 404 errors (data not found OR invalid pagination):
   * - No snackbar (not a technical error)
   * - Show contextual empty table with helpful message
   * - Message adapts to globalFilter presence
   */
  if (status === 404) {
    return (
      <TableRow>
        <TableCell colSpan={columns.length} align="center" sx={{ py: 6 }}>
          <Stack spacing={1} alignItems="center">
            <Typography variant="h6" color="text.secondary">
              {emptyMessage}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {globalFilter 
                ? `No results for "${globalFilter}"` 
                : emptyDescription}
            </Typography>
          </Stack>
        </TableCell>
      </TableRow>
    );
  }

  

  // ==============================|| CASE 3: FORBIDDEN (403) ||============================== //
  
  /**
   * For 403 errors (permission denied):
   * - Show snackbar (handled above)
   * - If cached data exists → Return nothing (let table show cached data)
   * - If no cache → Show empty table with retry button
   */
  if (status === 403) {
    // ✅ If we have cached data, don't render error UI
    if (hasCachedData) {
      return null;
    }

    // ✅ No cache available - show empty table with retry
    return (
      <TableRow>
        <TableCell colSpan={columns.length} align="center" sx={{ py: 6 }}>
          <Stack spacing={2} alignItems="center">
            <Typography variant="body2" color="text.secondary">
              Unable to load data. Please try again.
            </Typography>
            {isRetryable && (
              <Button
                variant="outlined"
                size="small"
                onClick={onRetry}
                disabled={isRetrying}
                startIcon={<ReloadOutlined spin={isRetrying} />}
              >
                {isRetrying ? 'Retrying...' : 'Retry'}
              </Button>
            )}
          </Stack>
        </TableCell>
      </TableRow>
    );
  }

  // ==============================|| CASE 4: RATE LIMIT (429) ||============================== //
  
  /**
   * For 429 rate limiting:
   * - Show Alert with countdown
   * - Automatic retry after cooldown
   */
  if (status === 429) {
    const errorMessage = (() => {
      // Countdown active
      if (secondsLeft !== null && secondsLeft > 0) {
        return (
          <Fragment>
            {message}
            <Box component="span" sx={{ display: 'block', mt: 1.5, fontWeight: 600, color: 'info.main' }}>
              🕐 Automatic retry in <strong>{secondsLeft}s</strong> - Please wait
            </Box>
          </Fragment>
        );
      }
      
      // Countdown finished, waiting for retry
      if (secondsLeft === 0) {
        return (
          <Fragment>
            {message}
            <Box component="span" sx={{ display: 'block', mt: 1.5, fontStyle: 'italic', opacity: 0.7 }}>
              Retrying automatically...
            </Box>
          </Fragment>
        );
      }
      
      // No countdown info
      return message;
    })();


  return (
      <TableRow>
        <TableCell colSpan={columns.length} align="center" sx={{ py: 6 }}>
          <Stack spacing={1} alignItems="center">
            <Typography variant="h6" color="text.secondary">
              {errorMessage}
            </Typography>
          </Stack>
        </TableCell>
      </TableRow>
    );
  }

  // ==============================|| CASE 5: OTHER ERRORS (Fallback) ||============================== //
  
  /**
   * For other 4xx errors and unknown errors:
   * - Show Alert with retry button (classic behavior)
   * - This is the safe fallback for unexpected errors
   */
  // return (
  //   <TableRow>
  //     <TableCell colSpan={columns.length} sx={{ py: 3 }}>
  //       <Alert
  //         severity={severity}
  //         icon={<WarningOutlined style={{ fontSize: 24 }} />}
  //         action={
  //           isRetryable && (
  //             <Button
  //               color="inherit"
  //               size="small"
  //               onClick={onRetry}
  //               disabled={isRetrying}
  //               startIcon={<ReloadOutlined spin={isRetrying} />}
  //             >
  //               {isRetrying ? 'Retrying...' : 'Retry Now'}
  //             </Button>
  //           )
  //         }
  //       >
  //         <AlertTitle sx={{ fontWeight: 600 }}>{title}</AlertTitle>
  //         <Typography variant="body2">{message}</Typography>
  //       </Alert>
  //     </TableCell>
  //   </TableRow>
  // );
  return (
      <TableRow>
        <TableCell colSpan={columns.length} align="center" sx={{ py: 6 }}>
          <Stack spacing={1} alignItems="center">
            <Typography variant="h6" color="text.secondary">
              {emptyMessage}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {globalFilter 
                ? `No results for "${globalFilter}"` 
                : emptyDescription}
            </Typography>
          </Stack>
        </TableCell>
      </TableRow>
    );
  }

ErrorDisplay.propTypes = {
  error: PropTypes.object,
  onRetry: PropTypes.func.isRequired,
  isRetrying: PropTypes.bool,
  columns: PropTypes.array.isRequired,
  globalFilter: PropTypes.string,
  data: PropTypes.array,
  emptyMessage: PropTypes.string,
  emptyDescription: PropTypes.string
};

export default ErrorDisplay;