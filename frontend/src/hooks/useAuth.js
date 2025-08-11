'use client';
import { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { 
  loginUser, 
  logoutUser, 
  getCurrentUser, 
  checkAuthStatus, 
  refreshTokens,
  saveLastRoute,
  getAndClearLastRoute 
} from '../api/auth';
import { authConfig, debugLog } from '../config/auth';

// ==============================|| AUTH CONTEXT ||============================== //

const AuthContext = createContext();

// ==============================|| AUTH PROVIDER ||============================== //

export function AuthProvider({ children }) {
  const router = useRouter();
  const pathname = usePathname();
  
  // États principaux
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Refs pour éviter les fuites mémoire et doubles initialisations
  const refreshTimerRef = useRef(null);
  const initializationRef = useRef(false);
  
  // ==============================|| HELPER FUNCTIONS ||============================== //
  
  /**
   * Nettoyer l'état d'authentification (fonction de base)
   */
  const clearAuthState = useCallback(() => {
    setUser(null);
    setIsAuthenticated(false);
    setError(null);
    
    // Nettoyer le timer de refresh
    if (refreshTimerRef.current) {
      clearInterval(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
  }, []);
  
  /**
   * Gérer les erreurs d'authentification avec redirection
   */
  const handleAuthError = useCallback((errorMessage) => {
    debugLog('Gestion erreur auth:', errorMessage);
    setError(errorMessage);
    clearAuthState();
    
    // Sauvegarder la route actuelle pour redirection post-login
    if (pathname !== authConfig.PAGES.LOGIN) {
      saveLastRoute(pathname);
    }
    
    // Rediriger vers la page de connexion
    router.push(authConfig.PAGES.LOGIN);
  }, [pathname, router, clearAuthState]);
  
  /**
   * Démarrer le timer de refresh automatique des tokens
   */
  const startRefreshTimer = useCallback(() => {
    // Nettoyer le timer existant
    if (refreshTimerRef.current) {
      clearInterval(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
    
    debugLog('Démarrage du timer de refresh automatique');
    refreshTimerRef.current = setInterval(async () => {
      try {
        debugLog('Refresh automatique des tokens...');
        await refreshTokens();
        debugLog('Refresh automatique réussi');
      } catch (error) {
        debugLog('Erreur lors du refresh automatique:', error);
        handleAuthError(error.message);
      }
    }, authConfig.TOKEN_REFRESH_INTERVAL);
  }, [handleAuthError]);
  
  /**
   * Définir l'utilisateur authentifié et démarrer le refresh
   */
  const setAuthenticatedUser = useCallback((userData) => {
    debugLog('Définition utilisateur authentifié:', userData);
    setUser(userData);
    setIsAuthenticated(true);
    setError(null);
    
    // Démarrer le timer de refresh automatique
    startRefreshTimer();
  }, [startRefreshTimer]);
  
  // ==============================|| AUTH FUNCTIONS ||============================== //
  
  /**
   * Connexion utilisateur avec redirection intelligente
   */
  const login = useCallback(async (email, password) => {
    try {
      setIsLoading(true);
      setError(null);
      debugLog('Tentative de connexion...');
      
      const result = await loginUser(email, password);
      
      if (result.success) {
        setAuthenticatedUser(result.user);
        
         setTimeout(() => {
            const lastRoute = getAndClearLastRoute();
            const redirectTo = lastRoute && lastRoute !== authConfig.PAGES.LOGIN 
              ? lastRoute 
              : authConfig.PAGES.DASHBOARD;
            
            debugLog('Redirection vers:', redirectTo);
            router.push(redirectTo);
          }, 100); // Petit délai pour laisser React mettre à jour le state
          
          return { success: true };
        } else {
          setError(result.error);
          return { success: false, error: result.error };
        }
      } catch (error) {
        const errorMessage = error.message || authConfig.ERROR_MESSAGES.SERVER_ERROR;
        debugLog('Erreur de connexion:', errorMessage);
        setError(errorMessage);
        return { success: false, error: errorMessage };
      } finally {
        setIsLoading(false);
      }
    }, [router, setAuthenticatedUser]);
  
  /**
   * Déconnexion utilisateur avec nettoyage complet
   */
  const logout = useCallback(async () => {
    try {
      setIsLoading(true);
      debugLog('Tentative de déconnexion...');
      await logoutUser();
      debugLog('Déconnexion réussie');
    } catch (error) {
      debugLog('Erreur lors de la déconnexion:', error);
    } finally {
      clearAuthState();
      setIsLoading(false);
      router.push(authConfig.PAGES.LOGIN);
    }
  }, [router, clearAuthState]);
  
  /**
   * Rafraîchir les données utilisateur
   */
  const refreshUser = useCallback(async () => {
    try {
      debugLog('Rafraîchissement des données utilisateur...');
      const result = await getCurrentUser();
      if (result.success) {
        setUser(result.user);
        debugLog('Données utilisateur rafraîchies');
        return result.user;
      }
    } catch (error) {
      debugLog('Erreur lors du refresh utilisateur:', error);
      handleAuthError(error.message);
    }
  }, [handleAuthError]);
  
  /**
   * Vérifier manuellement le statut d'authentification
   */
  const checkAuth = useCallback(async () => {
    try {
      const isAuth = await checkAuthStatus();
      if (isAuth) {
        const result = await getCurrentUser();
        if (result.success) {
          setAuthenticatedUser(result.user);
          return true;
        }
      }
      return false;
    } catch (error) {
      debugLog('Erreur lors de la vérification auth:', error);
      return false;
    }
  }, [setAuthenticatedUser]);
  
  // ==============================|| EFFECTS ||============================== //
  
  /**
   * Initialisation de l'authentification au chargement
   * Effect optimisé avec dépendances minimales
   */
  useEffect(() => {
    const initializeAuth = async () => {
      // Éviter les doubles initialisations
      if (initializationRef.current) return;
      initializationRef.current = true;
      
      try {
        debugLog('Initialisation de l\'authentification...');
        
        const isAuth = await checkAuthStatus();
        
        if (isAuth) {
          const result = await getCurrentUser();
          if (result.success) {
            setAuthenticatedUser(result.user);
            debugLog('Utilisateur déjà connecté:', result.user);
          } else {
            throw new Error('Impossible de récupérer les données utilisateur');
          }
        } else {
          debugLog('Aucun utilisateur connecté');
          clearAuthState();
        }
      } catch (error) {
        debugLog('Erreur lors de l\'initialisation:', error);
        clearAuthState();
      } finally {
        setIsLoading(false);
      }
    };
    
    initializeAuth();
    
    // Cleanup à la destruction du composant
    return () => {
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    };
  }, [setAuthenticatedUser, clearAuthState]); // Dépendances optimales
  
  
  // ==============================|| CONTEXT VALUE MEMOIZED ||============================== //
  
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
  };
  
  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
}

// ==============================|| AUTH HOOK ||============================== //

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth doit être utilisé dans un AuthProvider');
  }
  return context;
}

// ==============================|| AUTH GUARD HOOK OPTIMISÉ ||============================== //

/**
 * Hook pour protéger les composants qui nécessitent une authentification
 * Version optimisée avec gestion d'erreur
 */
export function useRequireAuth() {
  const { isAuthenticated, isLoading, user } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
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