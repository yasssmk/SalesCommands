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
  const initializationRef = useRef(false);
  const refreshTimerRef = useRef(null);
  const isRefreshingRef = useRef(false);

  // ==============================|| HELPER FUNCTIONS ||============================== //

  /**
   * ✅ SET AUTHENTICATED USER - Action unifiée
   */
  const setAuthenticatedUser = useCallback((userData) => {
    setUser(userData);
    setIsAuthenticated(true);
    setError(null);
    setIsLoading(false);
    debugLog('✅ User authenticated:', userData);
  }, []);

  /**
   * ✅ CLEAR AUTH STATE - Nettoyage complet
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
   * ✅ HANDLE AUTH ERROR - Gestion centralisée d'erreurs
   */
  const handleAuthError = useCallback((errorMessage) => {
    setError(errorMessage);
    clearAuthState();
    debugLog('❌ Auth error:', errorMessage);
  }, [clearAuthState]);

  // ==============================|| AUTO-REFRESH SYSTEM ||============================== //

   /**
   * ✅ AUTO-REFRESH TOKENS
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
  }, [performTokenRefresh]);

  const stopAutoRefresh = useCallback(() => {
    if (refreshTimerRef.current) {
      clearInterval(refreshTimerRef.current);
      refreshTimerRef.current = null;
      debugLog('⏹ Stopped auto-refresh timer');
    }
  }, []);

  // ==============================|| MAIN AUTH FUNCTIONS ||============================== //

  /**
   * ✅ LOGIN FUNCTION - Version originale fonctionnelle
   */
  const login = useCallback(async (email, password) => {
    // Laisse Formik gérer l'état de soumission; ne touche pas à isLoading ici.
    try {
      setError(null);
      debugLog('🔐 Login attempt for:', email);

      const result = await loginUser(email, password);
      if (!result.success) {
        setError(result.error);
        setIsLoading(false);
        return { success: false, error: result.error };
      }

      setAuthenticatedUser(result.user);

      // Hard reload vers le dashboard pour garantir l'isolation
      debugLog('🚀 Login successful, hard reload to dashboard...');
      window.location.assign(authConfig.PAGES.DASHBOARD);

      startAutoRefresh();

      return { success: true };
    } catch (error) {
      const errorMessage = error.message || authConfig.ERROR_MESSAGES.SERVER_ERROR;
      debugLog('❌ Login error:', errorMessage);
      setError(errorMessage);
      return { success: false, error: errorMessage };
    }
  }, [setAuthenticatedUser, startAutoRefresh]);

  /**
   * ✅ LOGOUT FUNCTION - Version originale
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

      // Étape 1: Appel backend (optionnel, continue même si échoue)
      try {
        await logoutUser();
        debugLog('✅ Server logout successful');
      } catch (backendError) {
        debugLog('⚠️ Server logout failed, continuing client logout:', backendError.message);
      }

      // Étape 2: Nettoyage client (toujours exécuté)
      stopAutoRefresh();
      clearAuthState();
      
      // Étape 3: Redirection
      debugLog('🚀 Redirecting to login...');
      window.location.assign(authConfig.PAGES.LOGIN);

      return { success: true };
    } catch (error) {
      debugLog('❌ Unexpected logout error:', error.message);
      
      // Force logout même en cas d'erreur
      clearAuthState();
      window.location.assign(authConfig.PAGES.LOGIN);
      
      return { success: false, error: error.message };
    } finally {
      setIsLoading(false);
    }
  }, [router, clearAuthState, isLoading, stopAutoRefresh]);

  /**
   * ✅ REFRESH USER DATA
   */
  const refreshUser = useCallback(async () => {
  try {
    debugLog('🔄 Refreshing user data...');
    
    // Stratégie 1: Essayer d'abord via refresh token (plus efficace)
    const refreshResult = await refreshTokens();
    
    if (refreshResult.success && refreshResult.user) {
      // ✅ Le refresh a retourné les données user
      setUser(refreshResult.user);
      debugLog('✅ User data refreshed via token refresh');
      return refreshResult.user;
    }
    
    // Stratégie 2: Si pas de user dans refresh, faire un appel dédié
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
    
    // Si le refresh a échoué
    handleAuthError(refreshResult.error);
    return null;
    
  } catch (error) {
    debugLog('❌ Refresh user error:', error.message);
    handleAuthError(error.message);
    return null;
  }
}, [handleAuthError]);

  /**
   * ✅ CHECK AUTH STATUS
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
   * ✅ INITIALIZATION EFFECT - Avec optimisation page publique SEULEMENT
   */
  useEffect(() => {
    let mounted = true;

    const initializeAuth = async () => {
      try {
        debugLog('🚀 Initializing authentication...');
        const result = await getCurrentUser(); // un seul appel
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

    // Cleanup uniquement à la destruction du provider (pas à chaque navigation)
    return () => {
      mounted = false;
      stopAutoRefresh();
    };
    // 🚫 Pas de pathname ici : on initialise une seule fois
  }, [setAuthenticatedUser, clearAuthState, startAutoRefresh, stopAutoRefresh]);

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
    clearAuthState,
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
}

// ==============================|| HOOKS ||============================== //

/**
 * ✅ MAIN AUTH HOOK
 */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default useAuth;