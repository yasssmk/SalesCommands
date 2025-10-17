// frontend/src/hooks/useAuth.js

'use client';

import React, { createContext, useContext, useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { useRouter, usePathname } from 'next/navigation';

// project imports
import { 
  loginUser, 
  logoutUser, 
  getCurrentUser, 
  refreshTokens,
  resetAuthState
} from '../api/auth';
import { authConfig, debugLog } from '../config/auth';
import { displayWarningSnackbar } from '../utils/displayError';
import { ErrorMessages } from '../utils/errorMessages';

// ==============================|| AUTH CONTEXT ||============================== //

const AuthContext = createContext(null);

// ==============================|| FLASH MESSAGE HELPERS ||============================== //

/**
 * Store auth flash message for display on login page
 */
const setAuthFlash = (message) => {
  try {
    const flash = { m: message, t: Date.now() };
    sessionStorage.setItem('authFlash', JSON.stringify(flash));
    debugLog('💾 Auth flash stored:', message);
  } catch (e) {
    debugLog('⚠️ Failed to store auth flash:', e.message);
  }
};

/**
 * Read and clear auth flash message (expires after 30s)
 */
export const getAuthFlash = () => {
  try {
    const raw = sessionStorage.getItem('authFlash');
    if (!raw) return null;

    const flash = JSON.parse(raw);
    const age = Date.now() - (flash.t || 0);
    
    if (age > 30000) {
      sessionStorage.removeItem('authFlash');
      return null;
    }

    sessionStorage.removeItem('authFlash');
    debugLog('📖 Auth flash read and cleared:', flash.m);
    return flash.m || null;
  } catch (e) {
    debugLog('⚠️ Failed to read auth flash:', e.message);
    return null;
  }
};

// ==============================|| AUTH PROVIDER ||============================== //

export function AuthProvider({ children }) {
  // Main auth states
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isNetworkDown, setIsNetworkDown] = useState(false);
  
  // Navigation hooks
  const router = useRouter();
  const pathname = usePathname();
  
  // Refs for optimization
  const refreshTimerRef = useRef(null);
  const isRefreshingRef = useRef(false);
  const hasInitializedRef = useRef(false);
  const lastSnackbarRef = useRef(0);

  // ==============================|| HELPER FUNCTIONS ||============================== //

  /**
   * Stop the auto-refresh timer
   */
  const stopAutoRefresh = useCallback(() => {
    if (refreshTimerRef.current) {
      clearInterval(refreshTimerRef.current);
      refreshTimerRef.current = null;
      debugLog('⏹ Stopped auto-refresh timer');
    }
  }, []);

  /**
   * Clear all auth state (user, session, errors)
   */
  const clearAuthState = useCallback(() => {
    setUser(null);
    setIsAuthenticated(false);
    setError(null);
    setIsLoading(false);
    setIsNetworkDown(false);
    resetAuthState();
    debugLog('🧹 Auth state cleared');
  }, []);

  /**
   * Handle soft auth issue (network down, 5xx errors)
   * Preserves session, activates degraded mode, shows snackbar
   */
  const handleSoftAuthIssue = useCallback((errorMessage) => {
    debugLog('⚠️ Soft auth issue (network down):', errorMessage);
    setIsNetworkDown(true);
    setError(errorMessage);
    setIsLoading(false);
    
    // Show snackbar (max 1 every 10 seconds to avoid spam)
    const now = Date.now();
    if (now - lastSnackbarRef.current > 10000) {
      displayWarningSnackbar(ErrorMessages.NETWORK_ERROR.message);
      lastSnackbarRef.current = now;
    }
  }, []);

  /**
   * Handle hard auth error (real 401/403 from server)
   * Clears session, stops timer, redirects to login
   */
  const handleAuthError = useCallback((errorMessage) => {
    debugLog('❌ Hard auth error (session expired):', errorMessage);
    setError(errorMessage);
    setIsLoading(false);
    setIsNetworkDown(false);
    stopAutoRefresh();
    clearAuthState();
    setAuthFlash(errorMessage);
  }, [clearAuthState, stopAutoRefresh]);

  // ==============================|| TOKEN REFRESH ||============================== //

  /**
   * Auto-refresh tokens (called by timer)
   * Distinguishes network errors from real session expirations
   */
  const performTokenRefresh = useCallback(async () => {
    if (isRefreshingRef.current) return;

    try {
      isRefreshingRef.current = true;
      debugLog('🔄 Auto-refreshing tokens...');

      const result = await refreshTokens();
      
      if (result.success) {
        setIsNetworkDown(false);
        
        if (result.user) {
          setUser(result.user);
          debugLog('✅ Token refresh successful with user data');
        } else {
          debugLog('✅ Token refresh successful (no user data)');
        }
      } else {
        if (result.shouldLogout) {
          debugLog('🚪 Real session expiration detected');
          handleAuthError(ErrorMessages.SESSION_EXPIRED.message);
        } else {
          debugLog('⚠️ Network issue during refresh, entering degraded mode');
          handleSoftAuthIssue(result.error || ErrorMessages.NETWORK_ERROR.message);
        }
      }
    } catch (error) {
      debugLog('❌ Unexpected refresh error:', error.message);
      handleSoftAuthIssue('Connection issue. Retrying...');
    } finally {
      isRefreshingRef.current = false;
    }
  }, [handleAuthError, handleSoftAuthIssue]);

  /**
   * Start auto-refresh timer with random jitter
   */
  const startAutoRefresh = useCallback(() => {
    stopAutoRefresh();
    const jitter = Math.floor(Math.random() * 30000) - 15000;
    const interval = authConfig.TOKEN_REFRESH_INTERVAL + jitter;
    debugLog(`⏰ Starting auto-refresh timer (interval: ${(interval / 1000).toFixed(0)}s)`);
    
    refreshTimerRef.current = setInterval(performTokenRefresh, interval);
  }, [performTokenRefresh, stopAutoRefresh]);

  /**
   * Set authenticated user and start timer
   */
  const setAuthenticatedUser = useCallback((userData) => {
    setUser(userData);
    setIsAuthenticated(true);
    setError(null);
    setIsLoading(false);
    setIsNetworkDown(false);
    startAutoRefresh();
    debugLog('✅ User authenticated + timer started:', userData);
  }, [startAutoRefresh]);

  // ==============================|| AUTH ACTIONS ||============================== //

  /**
   * Login user with email and password
   */
  const login = useCallback(async (email, password) => {
    try {
      setError(null);
      setIsNetworkDown(false);
      debugLog('🔐 Login attempt for:', email);

      const result = await loginUser(email, password);
      if (!result.success) {
        setError(result.error);
        setIsLoading(false);
        return { success: false, error: result.error };
      }

      setAuthenticatedUser(result.user);
      
      debugLog('🚀 Login successful, navigating to dashboard...');
      router.replace(authConfig.PAGES.DASHBOARD);
      router.refresh();

      return { success: true };
    } catch (error) {
      const errorMessage = error.message || authConfig.ERROR_MESSAGES.SERVER_ERROR;
      debugLog('❌ Login error:', errorMessage);
      setError(errorMessage);
      setIsLoading(false);
      return { success: false, error: errorMessage };
    }
  }, [router, setAuthenticatedUser]);

  /**
   * Logout user (best-effort backend call, always clears client state)
   */
  const logout = useCallback(async () => {
    if (isLoading) {
      debugLog('⚠️ Logout already in progress');
      return { success: false, error: 'Logout already in progress' };
    }

    try {
      setIsLoading(true);
      setError(null);
      debugLog('🚪 Starting logout process...');

      try {
        await logoutUser();
        debugLog('✅ Server logout successful');
      } catch (backendError) {
        debugLog('⚠️ Server logout failed, continuing client logout:', backendError.message);
      }

      // handleAuthError('You have been signed out. Please sign in again to continue.');
      handleAuthError('');

      debugLog('🚀 Redirecting to login...');
      router.replace(authConfig.PAGES.LOGIN);
      router.refresh();

      return { success: true };
    } catch (error) {
      debugLog('❌ Unexpected logout error:', error.message);
      // handleAuthError('You have been signed out. Please sign in again to continue.');
      handleAuthError('');
      router.replace(authConfig.PAGES.LOGIN);
      router.refresh();
      return { success: false, error: error.message };
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, handleAuthError, router]);

  /**
   * Refresh user data manually
   */
  const refreshUser = useCallback(async () => {
    try {
      debugLog('🔄 Refreshing user data...');
      
      const refreshResult = await refreshTokens();
      
      if (refreshResult.success && refreshResult.user) {
        setIsNetworkDown(false);
        setUser(refreshResult.user);
        debugLog('✅ User data refreshed via token refresh');
        return refreshResult.user;
      }
      
      if (refreshResult.success && !refreshResult.user) {
        debugLog('⚠️ Token refreshed but no user data, fetching separately...');
        const userResult = await getCurrentUser();
        
        if (userResult.success) {
          setIsNetworkDown(false);
          setUser(userResult.user);
          debugLog('✅ User data fetched separately');
          return userResult.user;
        } else {
          if (userResult.shouldLogout) {
            handleAuthError(ErrorMessages.SESSION_EXPIRED.message);
          } else {
            handleSoftAuthIssue(userResult.error || ErrorMessages.NETWORK_ERROR.message);
          }
          return null;
        }
      }
      
      if (refreshResult.shouldLogout) {
        handleAuthError(ErrorMessages.SESSION_EXPIRED.message);
      } else {
        handleSoftAuthIssue(refreshResult.error || ErrorMessages.NETWORK_ERROR.message);
      }
      return null;
      
    } catch (error) {
      debugLog('❌ Refresh user error:', error.message);
      handleSoftAuthIssue(ErrorMessages.NETWORK_ERROR.message);
      return null;
    }
  }, [handleAuthError, handleSoftAuthIssue]);

  /**
   * Check if user is authenticated
   */
  const checkAuth = useCallback(async () => {
    try {
      const result = await getCurrentUser();
      
      if (result.success) {
        setIsNetworkDown(false);
        setAuthenticatedUser(result.user);
        debugLog('✅ User already authenticated:', result.user);
        return true;
      } else {
        if (result.shouldLogout) {
          handleAuthError(ErrorMessages.SESSION_EXPIRED.message);
        } else {
          handleSoftAuthIssue(result.error || ErrorMessages.NETWORK_ERROR.message);
        }
        return false;
      }
    } catch (error) {
      debugLog('❌ Check auth error:', error.message);
      handleSoftAuthIssue(ErrorMessages.NETWORK_ERROR.message);
      return false;
    }
  }, [setAuthenticatedUser, handleAuthError, handleSoftAuthIssue]);

  // ==============================|| INITIALIZATION ||============================== //

  /**
   * Initialize auth on mount
   */
  useEffect(() => {
    let mounted = true;

    const handleSessionExpired = (event) => {
      debugLog('🚨 Session expired event received from interceptor');
      handleAuthError(event.detail.error);
    };
    
    window.addEventListener('auth:session-expired', handleSessionExpired);

    const initializeAuth = async () => {
      if (hasInitializedRef.current && user) {
        debugLog('ℹ️ Auth already initialized with user, skipping re-fetch');
        return;
      }

      const publicRoutes = authConfig.PUBLIC_ROUTES || ['/login', '/register', '/forgot-password'];
      
      if (publicRoutes.includes(pathname)) {
        debugLog('ℹ️ Public route, skipping auth initialization');
        setIsLoading(false);
        return;
      }

      try {
        debugLog('🚀 Initializing authentication...');
        const result = await getCurrentUser();
        if (!mounted) return;

        if (result.success) {
          setAuthenticatedUser(result.user);
          debugLog('✅ User already authenticated:', result.user);
        } else {
          if (result.shouldLogout) {
            handleAuthError(ErrorMessages.SESSION_EXPIRED.message);
          } else {
            debugLog('⚠️ Network issue during init, degraded mode');
            handleSoftAuthIssue(result.error || ErrorMessages.NETWORK_ERROR.message);
          }
        }
      } catch (error) {
        if (!mounted) return;
        debugLog('❌ Auth initialization error:', error.message);
        handleSoftAuthIssue(ErrorMessages.NETWORK_ERROR.message);
      } finally {
        if (mounted) {
          setIsLoading(false);
          hasInitializedRef.current = true;
        }
      }
    };

    initializeAuth();

    return () => {
      mounted = false;
      stopAutoRefresh();
      window.removeEventListener('auth:session-expired', handleSessionExpired);
    };
  }, []);

  // ==============================|| SILENT RECONNECTION RETRY ||============================== //

/**
 * Silent retry mechanism when backend is down
 * Attempts reconnection every 15 seconds
 */
useEffect(() => {
  // Only run retry loop when in degraded mode
  if (!isNetworkDown) {
    return;
  }

  debugLog('🔄 Starting silent reconnection attempts (every 15s)...');

  const attemptReconnection = async () => {
    try {
      debugLog('🔄 Silent retry: attempting to reconnect...');
      
      const result = await getCurrentUser();
      
      if (result.success) {
        // ✅ SUCCESS: Backend is back online
        debugLog('✅ Silent retry: Reconnection successful!');
        
        // Restore normal state
        setIsNetworkDown(false);
        setUser(result.user);
        setError(null);
        
        debugLog('✅ Normal mode restored, retry loop stopped');
      } else {
        if (result.shouldLogout) {
          // Hard error - stop retrying
          debugLog('🚪 Silent retry: Session expired detected, stopping retry');
          handleAuthError(result.error || ErrorMessages.SESSION_EXPIRED.message);
        } else {
          // Soft error - continue retrying
          debugLog('⚠️ Silent retry: Still unreachable, will retry in 15s');
        }
      }
    } catch (error) {
      debugLog('⚠️ Silent retry: Attempt failed, will retry in 15s');
    }
  };

  // First attempt immediately
  attemptReconnection();

  // Then retry every 15 seconds
  const retryInterval = setInterval(() => {
    attemptReconnection();
  }, 15000);

  // Cleanup
  return () => {
    debugLog('⏹ Stopping silent retry loop');
    clearInterval(retryInterval);
  };
}, [isNetworkDown, handleAuthError]);

  // ==============================|| OPTIMIZATIONS ||============================== //
  
  /**
   * Memoize tenant info to avoid recalculations
   */
  const tenantInfo = useMemo(
    () => ({
      tenantId: user?.client_id || null,
      tenantName: user?.client_name || null,
    }),
    [user?.client_id, user?.client_name]
  );

  /**
   * Clear error state
   */
  const clearError = useCallback(() => setError(null), []);

  /**
   * Memoize context value to prevent unnecessary re-renders
   */
  const contextValue = useMemo(
    () => ({
      user,
      isAuthenticated,
      isLoading,
      error,
      isNetworkDown,
      ...tenantInfo,
      login,
      logout,
      refreshUser,
      checkAuth,
      clearError,
      clearAuthState
    }),
    [
      user,
      isAuthenticated,
      isLoading,
      error,
      isNetworkDown,
      tenantInfo,
      login,
      logout,
      refreshUser,
      checkAuth,
      clearError,
      clearAuthState
    ]
  );

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
}

// ==============================|| HOOKS ||============================== //

/**
 * Hook to access auth context
 */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default useAuth;