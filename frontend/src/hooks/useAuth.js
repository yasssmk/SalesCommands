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
  checkAuthStatus,
  saveLastRoute, 
  getAndClearLastRoute,
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
    debugLog('✅ User authenticated:', userData);
  }, []);

  // ==============================|| AUTO-REDIRECT LOGIC ||============================== //

  /**
   * ✅ CLEAR AUTH STATE - Nettoyage complet
   */
  const clearAuthState = useCallback(() => {
    setUser(null);
    setIsAuthenticated(false);
    setError(null);
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
   * ✅ REFRESH AUTOMATIQUE - Utilise authConfig.TOKEN_REFRESH_INTERVAL
   */
  const startAutoRefresh = useCallback(() => {
    // Nettoyer l'ancien timer s'il existe
    if (refreshTimerRef.current) {
      clearInterval(refreshTimerRef.current);
    }

    console.log(`🔄 AUTO-REFRESH: Timer started - refresh every ${authConfig.TOKEN_REFRESH_INTERVAL / (60 * 1000)} minutes`);
    debugLog(`⏰ Starting auto-refresh timer (${authConfig.TOKEN_REFRESH_INTERVAL}ms)`);
    
    refreshTimerRef.current = setInterval(async () => {
      // Éviter les refreshs multiples simultanés
      if (isRefreshingRef.current) {
        console.log('🔄 AUTO-REFRESH: Skipping - refresh already in progress');
        return;
      }

      try {
        isRefreshingRef.current = true;
        console.log('🔄 AUTO-REFRESH: Starting automatic token refresh...');
        
        // ✅ Appel DIRECT à refreshTokens() qui fait POST /client/refresh-token/
        const result = await refreshTokens();
        
        if (result.success) {
          setUser(result.user);
          console.log('✅ AUTO-REFRESH: Token refreshed successfully');
          debugLog('✅ Auto-refresh successful');
        } else {
          console.log('❌ AUTO-REFRESH: Failed - ', result.error);
          debugLog('❌ Auto-refresh failed:', result.error);
        }
      } catch (error) {
        console.log('❌ AUTO-REFRESH: Error - ', error.message);
        debugLog('❌ Auto-refresh error:', error.message);
      } finally {
        isRefreshingRef.current = false;
      }
    }, authConfig.TOKEN_REFRESH_INTERVAL);
    
  }, []);

  /**
   * ✅ STOP AUTO-REFRESH TIMER
   */
  const stopAutoRefresh = useCallback(() => {
    if (refreshTimerRef.current) {
      clearInterval(refreshTimerRef.current);
      refreshTimerRef.current = null;
      isRefreshingRef.current = false;
      console.log('🛑 AUTO-REFRESH: Timer stopped');
      debugLog('⏰ Auto-refresh timer stopped');
    }
  }, []);

  /**
   * ✅ REDIRECTION AUTOMATIQUE POUR UTILISATEURS DÉJÀ CONNECTÉS
   * Si user authentifié accède à /login → redirige vers dashboard
   */
  useEffect(() => {
    if (!isLoading && isAuthenticated && pathname === '/login') {
      debugLog('🚀 User already authenticated, redirecting from /login...');
      
      const lastRoute = getAndClearLastRoute();
      const redirectTo = lastRoute || authConfig.PAGES.DASHBOARD;
      
      setTimeout(() => {
        router.push(redirectTo);
      }, 100);
    }
  }, [isLoading, isAuthenticated, pathname, router]);

  // ==============================|| MAIN AUTH FUNCTIONS ||============================== //

  /**
   * ✅ LOGIN FUNCTION
   */
  const login = useCallback(async (email, password) => {
    if (isLoading) {
      return { success: false, error: 'Login already in progress' };
    }

    try {
      setIsLoading(true);
      setError(null);
      debugLog('🔐 Login attempt for:', email);

      const result = await loginUser(email, password);
      
      if (result.success) {
        setAuthenticatedUser(result.user);
        
        // Démarrer l'auto-refresh
        startAutoRefresh();
        
        // Redirection avec lastRoute
        const lastRoute = getAndClearLastRoute();
        const redirectTo = lastRoute || authConfig.PAGES.DASHBOARD;
        
        setTimeout(() => {
          debugLog('🚀 Login successful, redirecting to:', redirectTo);
          router.push(redirectTo);
        }, 100);
        
        return { success: true };
      } else {
        setError(result.error);
        return { success: false, error: result.error };
      }
    } catch (error) {
      const errorMessage = error.message || authConfig.ERROR_MESSAGES.SERVER_ERROR;
      debugLog('❌ Login error:', errorMessage);
      setError(errorMessage);
      return { success: false, error: errorMessage };
    } finally {
      setIsLoading(false);
    }
  }, [router, setAuthenticatedUser, isLoading, startAutoRefresh]);

  /**
   * ✅ LOGOUT FUNCTION - Version optimisée
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
      setTimeout(() => {
        debugLog('🚀 Redirecting to login...');
        router.push(authConfig.PAGES.LOGIN);
      }, 50);

      return { success: true };
    } catch (error) {
      debugLog('❌ Unexpected logout error:', error.message);
      
      // Force logout même en cas d'erreur
      clearAuthState();
      router.push(authConfig.PAGES.LOGIN);
      
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
      const result = await getCurrentUser();
      
      if (result.success) {
        setUser(result.user);
        debugLog('✅ User data refreshed');
        return result.user;
      } else {
        handleAuthError(result.error);
        return null;
      }
    } catch (error) {
      debugLog('❌ Refresh user error:', error.message);
      handleAuthError(error.message);
      return null;
    }
  }, []);

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
   * ✅ INITIALIZATION EFFECT - Version optimisée
   */
  useEffect(() => {
    const initializeAuth = async () => {
      // Éviter les doubles initialisations
      if (initializationRef.current) return;
      initializationRef.current = true;
      
      try {
        debugLog('🚀 Initializing authentication...');
        
        const isAuth = await checkAuthStatus();
        
        if (isAuth) {
          const result = await getCurrentUser();
          if (result.success) {
            setAuthenticatedUser(result.user);
            
            // Démarrer l'auto-refresh si utilisateur déjà connecté
            startAutoRefresh();
            
            debugLog('✅ User already authenticated:', result.user);
          } else {
            debugLog('❌ Failed to get user data, clearing auth');
            clearAuthState();
          }
        } else {
          debugLog('ℹ️ No authenticated user found');
          clearAuthState();
        }
      } catch (error) {
        debugLog('❌ Auth initialization error:', error.message);
        clearAuthState();
      } finally {
        setIsLoading(false);
      }
    };
    
    initializeAuth();
    
    // Cleanup
    return () => {
      stopAutoRefresh();
    };
  }, [setAuthenticatedUser, clearAuthState, startAutoRefresh, stopAutoRefresh]);

  // ==============================|| CONTEXT VALUE ||============================== //

  const contextValue = {
    // États
    user,
    isAuthenticated,
    isLoading,
    error,
    
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
 * ✅ MAIN AUTH HOOK
 */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

/**
 * ✅ PROTECTED ROUTE HOOK
 */
export function useRequireAuth() {
  const { isAuthenticated, isLoading, user } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      debugLog('🛡️ Unauthorized access, redirecting to login');
      saveLastRoute(pathname);
      router.push(authConfig.PAGES.LOGIN);
    }
  }, [isLoading, isAuthenticated, pathname, router]);
  
  return {
    isAuthenticated,
    isLoading,
    user,
    isReady: !isLoading && isAuthenticated,
  };
}



export default useAuth;