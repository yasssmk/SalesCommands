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
  // 🛡️ Protection contre les appels multiples simultanés
  if (isLoading) {
    debugLog('Logout déjà en cours, ignore la demande');
    return { success: false, error: 'Logout already in progress' };
  }

  try {
    setIsLoading(true);
    setError(null);
    debugLog('🔓 Début du processus de déconnexion sécurisée...');

    // 🎯 ÉTAPE 1: Appel backend pour invalider les tokens HttpOnly
    try {
      debugLog('📡 Invalidation des tokens côté serveur...');
      await logoutUser();
      debugLog('✅ Tokens invalidés côté serveur avec succès');
    } catch (backendError) {
      // ⚠️ Si le backend échoue, on continue quand même le logout côté client
      // pour éviter de laisser l'utilisateur "bloqué"
      debugLog('⚠️ Erreur backend lors du logout (continuer quand même):', backendError.message);
      
      // On peut logger l'erreur pour monitoring, mais on ne bloque pas
      console.warn('[LOGOUT] Backend error (continuing client logout):', backendError);
    }

    // 🧹 ÉTAPE 2: Nettoyage complet côté client (TOUJOURS exécuté)
    debugLog('🧹 Nettoyage complet de l\'état client...');
    
    // 2a. Nettoyer les timers et refs
    if (refreshTimerRef.current) {
      clearInterval(refreshTimerRef.current);
      refreshTimerRef.current = null;
      debugLog('⏰ Timer de refresh automatique nettoyé');
    }
    
    // 2b. Nettoyer l'état d'authentification
    setUser(null);
    setIsAuthenticated(false);
    setError(null);
    debugLog('🗑️ État d\'authentification nettoyé');
    
    // 2c. Nettoyer le localStorage des données non-sensibles (si utilisé)
    try {
      // Nettoyage sélectif - garder les préférences générales
      if (typeof window !== 'undefined') {
        const keysToRemove = [
          authConfig.STORAGE_KEYS.LAST_ROUTE,
          // Ajouter d'autres clés spécifiques au user si nécessaire
        ];
        
        keysToRemove.forEach(key => {
          if (localStorage.getItem(key)) {
            localStorage.removeItem(key);
            debugLog(`🗂️ Clé localStorage supprimée: ${key}`);
          }
        });
      }
    } catch (storageError) {
      debugLog('⚠️ Erreur lors du nettoyage localStorage:', storageError);
    }

    // 🚀 ÉTAPE 3: Redirection sécurisée
    debugLog('🚀 Redirection vers la page de connexion...');
    
    // Délai court pour permettre à React de finir ses mises à jour
    setTimeout(() => {
      router.push(authConfig.PAGES.LOGIN);
      debugLog('✅ Déconnexion terminée avec succès');
    }, 50);

    return { success: true };

  } catch (unexpectedError) {
    // 🚨 Erreur inattendue - logger pour debug mais continuer le logout
    debugLog('🚨 Erreur inattendue lors du logout:', unexpectedError);
    console.error('[LOGOUT] Unexpected error:', unexpectedError);
    
    // Forcer le nettoyage même en cas d'erreur
    setUser(null);
    setIsAuthenticated(false);
    setError('Logout completed with warnings');
    
    // Redirection forcée
    router.push(authConfig.PAGES.LOGIN);
    
    return { success: false, error: unexpectedError.message };
    
  } finally {
    // 🏁 Toujours nettoyer le loading state
    setIsLoading(false);
    debugLog('🏁 Processus de logout terminé');
  }
}, [router, isLoading]);

  
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