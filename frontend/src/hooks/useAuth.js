// frontend/src/hooks/useAuth.js

'use client';

import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
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

// ==============================|| AUTH CONTEXT ||============================== //

const AuthContext = createContext(null);

// ==============================|| AUTH PROVIDER ||============================== //

export function AuthProvider({ children }) {
  // États principaux
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Navigation hooks
  const router = useRouter();
  const pathname = usePathname();
  
  // Refs pour optimisation
  const refreshTimerRef = useRef(null);
  const isRefreshingRef = useRef(false);

  // ==============================|| HELPER FUNCTIONS ||============================== //

  /**
   * STOP AUTO REFRESH
   */
  const stopAutoRefresh = useCallback(() => {
    if (refreshTimerRef.current) {
      clearInterval(refreshTimerRef.current);
      refreshTimerRef.current = null;
      debugLog('⏹ Stopped auto-refresh timer');
    }
  }, []);

  /**
   * SET AUTHENTICATED USER - Action unifiée
   */
  const setAuthenticatedUser = useCallback((userData) => {
    setUser(userData);
    setIsAuthenticated(true);
    setError(null);
    setIsLoading(false);
    debugLog('✅ User authenticated:', userData);
  }, []);

  /**
   * CLEAR AUTH STATE - Nettoyage complet
   */
  const clearAuthState = useCallback(() => {
    setUser(null);
    setIsAuthenticated(false);
    setError(null);
    setIsLoading(false);
    resetAuthState();
    debugLog('🧹 Auth state cleared');
  }, []);

  /**
   * HANDLE AUTH ERROR - Avec arrêt du timer
   */
  const handleAuthError = useCallback((errorMessage) => {
    setError(errorMessage);
    setIsLoading(false);
    stopAutoRefresh(); // ✅ Arrêt du timer en cas d'erreur d'auth
    clearAuthState();
    debugLog('❌ Auth error handled:', errorMessage);
  }, [clearAuthState, stopAutoRefresh]);

  // ==============================|| TOKEN REFRESH ||============================== //

  /**
   * AUTO-REFRESH TOKENS
   */
  const performTokenRefresh = useCallback(async () => {
    if (isRefreshingRef.current) return;

    try {
      isRefreshingRef.current = true;
      debugLog('🔄 Auto-refreshing tokens...');

      const result = await refreshTokens();
      if (result.success) {
        if (result.user) {
          setUser(result.user);
          debugLog('✅ Token refresh successful with user data');
        } else {
          debugLog('✅ Token refresh successful (no user data)');
        }
      } else {
        debugLog('❌ Token refresh failed:', result.error);
        handleAuthError(result.error);
      }
    } catch (error) {
      debugLog('❌ Token refresh error:', error.message);
      handleAuthError(error.message);
    } finally {
      isRefreshingRef.current = false;
    }
  }, [handleAuthError]);

  const startAutoRefresh = useCallback(() => {
    stopAutoRefresh();
    debugLog('⏰ Starting auto-refresh timer');
    
    refreshTimerRef.current = setInterval(
      performTokenRefresh,
      authConfig.TOKEN_REFRESH_INTERVAL
    );
  }, [performTokenRefresh, stopAutoRefresh]);

  // ==============================|| AUTH ACTIONS ||============================== //

  /**
   * LOGIN FUNCTION - Navigation Next + re-hydratation
   */
  const login = useCallback(async (email, password) => {
    try {
      setError(null);
      debugLog('🔐 Login attempt for:', email);

      const result = await loginUser(email, password);
      if (!result.success) {
        setError(result.error);
        setIsLoading(false);
        return { success: false, error: result.error };
      }

      // Store user
      setAuthenticatedUser(result.user);
      
      // Navigation Next.js avec re-hydratation
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
   * LOGOUT FUNCTION - Navigation Next + re-hydratation
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

      // Étape 1: Appel backend
      try {
        await logoutUser();
        debugLog('✅ Server logout successful');
      } catch (backendError) {
        debugLog('⚠️ Server logout failed, continuing client logout:', backendError.message);
      }

      // Étape 2: Nettoyage client
      stopAutoRefresh();
      clearAuthState();
      
      // Étape 3: Navigation Next.js avec re-hydratation
      debugLog('🚀 Redirecting to login...');
      router.replace(authConfig.PAGES.LOGIN);
      router.refresh();

      return { success: true };
    } catch (error) {
      debugLog('❌ Unexpected logout error:', error.message);
      clearAuthState();
      router.replace(authConfig.PAGES.LOGIN);
      router.refresh();
      return { success: false, error: error.message };
    }
  }, [router, clearAuthState, isLoading, stopAutoRefresh]);

  /**
   * REFRESH USER DATA
   */
  const refreshUser = useCallback(async () => {
    try {
      debugLog('🔄 Refreshing user data...');
      
      const refreshResult = await refreshTokens();
      
      if (refreshResult.success && refreshResult.user) {
        setUser(refreshResult.user);
        debugLog('✅ User data refreshed via token refresh');
        return refreshResult.user;
      }
      
      if (refreshResult.success && !refreshResult.user) {
        debugLog('⚠️ Token refreshed but no user data, fetching separately...');
        const userResult = await getCurrentUser();
        
        if (userResult.success) {
          setUser(userResult.user);
          debugLog('✅ User data fetched separately');
          return userResult.user;
        } else {
          handleAuthError(userResult.error);
          return null;
        }
      }
      
      handleAuthError(refreshResult.error);
      return null;
      
    } catch (error) {
      debugLog('❌ Refresh user error:', error.message);
      handleAuthError(error.message);
      return null;
    }
  }, [handleAuthError]);

  /**
   * CHECK AUTH STATUS
   */
  const checkAuth = useCallback(async () => {
    try {
      const result = await getCurrentUser();
      
      if (result.success) {
        setAuthenticatedUser(result.user);
        return true;
      } else {
        clearAuthState();
        return false;
      }
    } catch (error) {
      debugLog('❌ Check auth error:', error.message);
      clearAuthState();
      return false;
    }
  }, [setAuthenticatedUser, clearAuthState]);

  // ==============================|| INITIALIZATION ||============================== //

  /**
   * INITIALIZATION EFFECT - Skip sur routes publiques
   */
  useEffect(() => {
    let mounted = true;

    const initializeAuth = async () => {
      // Routes publiques où l'auth n'est pas nécessaire
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
          startAutoRefresh();
          debugLog('✅ User already authenticated:', result.user);
        } else {
          clearAuthState();
          debugLog('ℹ️ No authenticated user found');
        }
      } catch (error) {
        debugLog('❌ Auth initialization error:', error.message);
        clearAuthState();
      } finally {
        if (mounted) setIsLoading(false);
      }
    };

    initializeAuth();

    return () => {
      mounted = false;
      stopAutoRefresh();
    };
  }, [pathname, setAuthenticatedUser, clearAuthState, startAutoRefresh, stopAutoRefresh]);

  // ==============================|| CONTEXT VALUE ||============================== //

  const contextValue = {
    // États
    user,
    isAuthenticated,
    isLoading,
    error,
    
    // Exposition explicite du tenantId pour l'isolation
    tenantId: user?.client_id || null,
    tenantName: user?.client_name || null,
    
    // Actions
    login,
    logout,
    refreshUser,
    checkAuth,
    
    // Utilities
    clearError: useCallback(() => setError(null), []),
    clearAuthState
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
}

// ==============================|| HOOKS ||============================== //

/**
 * MAIN AUTH HOOK
 */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default useAuth;