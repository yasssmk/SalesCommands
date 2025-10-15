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

// ==============================|| AUTH CONTEXT ||============================== //

const AuthContext = createContext(null);

// ==============================|| FLASH MESSAGE HELPERS ||============================== //

/**
 * Store auth flash message for display on login page
 * @param {string} message - Error message to display
 */
const setAuthFlash = (message) => {
  try {
    const flash = {
      m: message,
      t: Date.now()
    };
    sessionStorage.setItem('authFlash', JSON.stringify(flash));
    debugLog('💾 Auth flash stored:', message);
  } catch (e) {
    // Silent fail - sessionStorage might be unavailable
    debugLog('⚠️ Failed to store auth flash:', e.message);
  }
};

/**
 * Read and clear auth flash message
 * @returns {string|null} Flash message or null
 */
export const getAuthFlash = () => {
  try {
    const raw = sessionStorage.getItem('authFlash');
    if (!raw) return null;

    const flash = JSON.parse(raw);
    const age = Date.now() - (flash.t || 0);
    
    // Flash expires after 30 seconds (prevents stale messages)
    if (age > 30000) {
      sessionStorage.removeItem('authFlash');
      return null;
    }

    // Clear flash after reading
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
  const hasInitializedRef = useRef(false);

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
    setAuthFlash(errorMessage);
    debugLog('❌ Auth error handled:', errorMessage);
  }, [clearAuthState, stopAutoRefresh]);

  // ==============================|| TOKEN REFRESH ||============================== //

  /**
   * AUTO-REFRESH TOKENS (called by timer)
   * ⚠️ Uses setUser() directly to avoid infinite loop with setAuthenticatedUser()
   */
  const performTokenRefresh = useCallback(async () => {
    if (isRefreshingRef.current) return;

    try {
      isRefreshingRef.current = true;
      debugLog('🔄 Auto-refreshing tokens...');

      const result = await refreshTokens();
      if (result.success) {
        if (result.user) {
          setUser(result.user); // ✅ Direct setUser, not setAuthenticatedUser
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

  /**
   * START AUTO REFRESH with jitter
   */
  const startAutoRefresh = useCallback(() => {
    stopAutoRefresh();
    const jitter = Math.floor(Math.random() * 30000) - 15000; // ±15s
    const interval = authConfig.TOKEN_REFRESH_INTERVAL + jitter;
    debugLog(`⏰ Starting auto-refresh timer (interval: ${(interval / 1000).toFixed(0)}s)`);
    
    refreshTimerRef.current = setInterval(
      performTokenRefresh,
      interval
    );
  }, [performTokenRefresh, stopAutoRefresh]);

  /**
   * ✅ SET AUTHENTICATED USER + START TIMER
   * Called after login and initialization
   */
  const setAuthenticatedUser = useCallback((userData) => {
    setUser(userData);
    setIsAuthenticated(true);
    setError(null);
    setIsLoading(false);
    startAutoRefresh(); // ✅ Start proactive refresh timer
    debugLog('✅ User authenticated + timer started:', userData);
  }, [startAutoRefresh]);

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

      // Store user + start timer
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

    const handleSessionExpired = (event) => {
      debugLog('🚨 Session expired event received from interceptor');
      handleAuthError(event.detail.error);
    };
    
    window.addEventListener('auth:session-expired', handleSessionExpired);

    const initializeAuth = async () => {

      // ✅ Skip si déjà initialisé avec un user
      if (hasInitializedRef.current && user) {
        debugLog('ℹ️ Auth already initialized with user, skipping re-fetch');
        return;
      }

      // Routes publiques où l'auth n'est pas nécessaire
      const publicRoutes = authConfig.PUBLIC_ROUTES || ['/login', '/register', '/forgot-password'];
      
      if (publicRoutes.includes(pathname)) {
        debugLog('ℹ️ Public route, skipping auth initialization');
        setIsLoading(false);
        return;
      }

      // ✅ Skip re-init sur navigation interne si user déjà chargé
      if (hasInitializedRef.current && user) {
        debugLog('ℹ️ Navigation within admin with existing user, skipping re-init');
        setIsLoading(false);
        return;
      }


      try {
        debugLog('🚀 Initializing authentication...');
        const result = await getCurrentUser();
        if (!mounted) return;

        if (result.success) {
          // ✅ setAuthenticatedUser starts timer automatically
          setAuthenticatedUser(result.user);
          debugLog('✅ User already authenticated:', result.user);
        } else {
          clearAuthState();
          debugLog('ℹ️ No authenticated user found');
        }
      } catch (error) {
        debugLog('❌ Auth initialization error:', error.message);
        clearAuthState();
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

 // ==============================|| OPTIMISATIONS ||============================== //
  
  /**
   * ✅ MÉMOÏSATION DES INFOS TENANT
   * Évite de recalculer tenantId/tenantName à chaque render
   * Impact: Réduction des re-renders sur tous les composants utilisant ces valeurs
   */
  const tenantInfo = useMemo(
    () => ({
      tenantId: user?.client_id || null,
      tenantName: user?.client_name || null,
    }),
    [user?.client_id, user?.client_name]
  );

  /**
   * ✅ CLEAR ERROR AVEC DÉPENDANCES CORRECTES
   * Fixe le warning React sur les dépendances manquantes
   */
  const clearError = useCallback(() => setError(null), []);

  /**
   * ✅ MÉMOÏSATION DE LA CONTEXT VALUE
   * CRITIQUE: Évite que TOUS les composants utilisant useAuth() se re-render
   * à chaque render du AuthProvider
   * 
   * Gain attendu: 100-200ms économisés sur navigation + réduction massive des re-renders
   */
  const contextValue = useMemo(
    () => ({
      // États
      user,
      isAuthenticated,
      isLoading,
      error,
      
      // Infos tenant mémoïsées
      ...tenantInfo,
      
      // Actions
      login,
      logout,
      refreshUser,
      checkAuth,
      
      // Utilities
      clearError,
      clearAuthState
    }),
    [
      user,
      isAuthenticated,
      isLoading,
      error,
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


