'use client';
import PropTypes from 'prop-types';
import { useEffect, useState, createContext, useContext, useCallback, useRef } from 'react';
import { useRouter, usePathname } from 'next/navigation';

// project imports
import Loader from 'components/Loader';
import { authConfig, debugLog } from 'config/auth';
import { loginUser, logoutUser, getCurrentUser, refreshTokens, getAndClearLastRoute } from 'api/auth';

// ==============================|| AUTH CONTEXT FOR PUBLIC GUARD ||============================== //

const PublicAuthContext = createContext(null);

// ==============================|| PUBLIC AUTH PROVIDER ||============================== //

function PublicAuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const refreshTimerRef = useRef(null);
  const router = useRouter();

  // ==============================|| HELPERS ||============================== //

  const setAuthenticatedUser = useCallback((userData) => {
    setUser(userData);
    setIsAuthenticated(true);
    setError(null);
    debugLog('PublicAuth: User authenticated successfully');
  }, []);

  const clearAuthState = useCallback(() => {
    setUser(null);
    setIsAuthenticated(false);
    setError(null);
    debugLog('PublicAuth: Auth state cleared');
  }, []);

  // ==============================|| AUTH ACTIONS ||============================== //

  const login = useCallback(async (email, password) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await loginUser(email, password);
      
      if (response.success) {
        setAuthenticatedUser(response.user);
        
        // Redirection vers la dernière route visitée ou dashboard
        const lastRoute = getAndClearLastRoute();
        const redirectPath = lastRoute || authConfig.PAGES.DASHBOARD;
        router.push(redirectPath);
        
        return { success: true };
      } else {
        setError(response.error);
        return { success: false, error: response.error };
      }
    } catch (err) {
      const errorMessage = err.message || 'Login failed';
      setError(errorMessage);
      return { success: false, error: errorMessage };
    } finally {
      setIsLoading(false);
    }
  }, [setAuthenticatedUser, router]);

  const logout = useCallback(async () => {
    try {
      await logoutUser();
    } catch (err) {
      debugLog('Logout error:', err.message);
    } finally {
      clearAuthState();
      router.push(authConfig.PAGES.LOGIN);
    }
  }, [clearAuthState, router]);

  const checkAuth = useCallback(async () => {
    try {
      const response = await getCurrentUser();
      
      if (response.success) {
        setAuthenticatedUser(response.user);
        return true;
      } else {
        clearAuthState();
        return false;
      }
    } catch (err) {
      debugLog('Check auth error:', err.message);
      clearAuthState();
      return false;
    }
  }, [setAuthenticatedUser, clearAuthState]);

  const refreshUser = useCallback(async () => {
    try {
      const response = await refreshTokens();
      
      if (response.success) {
        setAuthenticatedUser(response.user);
        return true;
      } else {
        clearAuthState();
        return false;
      }
    } catch (err) {
      debugLog('Refresh user error:', err.message);
      clearAuthState();
      return false;
    }
  }, [setAuthenticatedUser, clearAuthState]);

  // ==============================|| INITIALIZATION ||============================== //

  useEffect(() => {
    let isMounted = true;

    const initializeAuth = async () => {
      try {
        debugLog('PublicAuth: Initializing authentication...');
        
        // Vérifier si l'utilisateur est déjà authentifié
        const isAuth = await checkAuth();
        
        if (isMounted) {
          if (isAuth) {
            debugLog('PublicAuth: User found, setting up refresh timer');
            
            // Configurer le timer de refresh automatique
            refreshTimerRef.current = setInterval(async () => {
              await refreshUser();
            }, 14 * 60 * 1000); // Refresh toutes les 14 minutes
          }
          
          setIsLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          debugLog('PublicAuth: Initialization error:', err.message);
          setIsLoading(false);
        }
      }
    };

    initializeAuth();

    return () => {
      isMounted = false;
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    };
  }, [checkAuth, refreshUser]);

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
  };

  return (
    <PublicAuthContext.Provider value={contextValue}>
      {children}
    </PublicAuthContext.Provider>
  );
}

// ==============================|| PUBLIC AUTH HOOK ||============================== //

function usePublicAuth() {
  const context = useContext(PublicAuthContext);
  if (!context) {
    throw new Error('usePublicAuth must be used within PublicAuthProvider');
  }
  return context;
}

// ==============================|| PUBLIC GUARD (GUEST GUARD) ||============================== //

/**
 * Guard pour les pages publiques (login, register, forgot-password)
 * 
 * RESPONSABILITÉS MVP :
 * ✅ Fournir le context d'authentification aux pages publiques
 * ✅ Rediriger vers dashboard si déjà connecté
 * ✅ Permettre l'accès aux pages d'auth si non connecté
 * ✅ Gérer les états de loading
 * 
 * USAGE :
 * - Wraps app/(auth)/layout.jsx
 * - Utilisé pour login, register, forgot-password
 */
export default function PublicGuard({ children, fallback = null }) {
  return (
    <PublicAuthProvider>
      <PublicGuardLogic fallback={fallback}>
        {children}
      </PublicGuardLogic>
    </PublicAuthProvider>
  );
}

function PublicGuardLogic({ children, fallback }) {
  const { isAuthenticated, isLoading } = usePublicAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Si authentifié et sur une page publique, rediriger vers dashboard
    if (!isLoading && isAuthenticated) {
      debugLog('PublicGuard: User already authenticated, redirecting to dashboard');
      
      // Redirection vers la dernière route ou dashboard
      const lastRoute = getAndClearLastRoute();
      const redirectPath = lastRoute || authConfig.PAGES.DASHBOARD;
      router.push(redirectPath);
    }
  }, [isAuthenticated, isLoading, pathname, router]);

  // Affichage du loader pendant la vérification
  if (isLoading) {
    return fallback || <Loader />;
  }

  // Si authentifié, ne pas afficher le contenu (redirection en cours)
  if (isAuthenticated) {
    return fallback || <Loader />;
  }

  // Afficher les pages publiques pour les utilisateurs non authentifiés
  return children;
}

PublicGuard.propTypes = {
  children: PropTypes.node.isRequired,
  fallback: PropTypes.node,
};

PublicGuardLogic.propTypes = {
  children: PropTypes.node.isRequired,
  fallback: PropTypes.node,
};

// ==============================|| EXPORT PUBLIC AUTH HOOK ||============================== //

export { usePublicAuth };