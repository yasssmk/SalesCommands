// frontend/src/api/auth.js

import axiosClient, { api } from '../utils/axiosClient';
import { authConfig, debugLog } from '../config/auth';
import useSWR from 'swr';



// ==============================|| AUTH API FUNCTIONS ||============================== //

/**
 * ✅ LOGIN USER
 * @param {string} email - User email
 * @param {string} password - User password
 * @returns {Promise<Object>} {success: boolean, user?: Object, error?: string}
 */
export const loginUser = async (email, password) => {
  
  const result = await api.post(authConfig.ENDPOINTS.LOGIN, {
    email,
    password
  });
  
  if (result.success) {
    debugLog('✅ Login successful for:', email);
    return {
      success: true,
      user: result.data.user || result.data
    };
  } else {
    debugLog('❌ Login failed:', result.error);
    return {
      success: false,
      error: result.error
    };
  }
};

/**
 * ✅ REFRESH TOKENS - Appel direct endpoint refresh-token
 * @returns {Promise<Object>} {success: boolean, user?: Object, error?: string}
 */
export const refreshTokens = async () => {
  debugLog('🔄 Refreshing tokens via POST /client/refresh-token/...');
  
  const result = await api.post(authConfig.ENDPOINTS.REFRESH);
  
  if (result.success) {
    debugLog('✅ Tokens refreshed successfully');
    return {
      success: true,
      user: result.data.user || result.data
    };
  } else {
    debugLog('❌ Token refresh failed:', result.error);
    // ✅ Déconnexion forcée / session expirée → on nettoie lastRoute
    resetAuthState();

    return {
      success: false,
      error: result.error
    };
  }
};

/**
 * ✅ LOGOUT USER
 * @returns {Promise<Object>} Response confirmation
 */
export const logoutUser = async () => {
  debugLog('🚪 Logging out user...');
  
  try {
    // Appel direct avec axiosClient (pas d'auto-refresh needed)
    const response = await axiosClient.post(authConfig.ENDPOINTS.LOGOUT);

    // ✅ Nettoyage de lastRoute lors d'un logout explicite
    resetAuthState();
    
    debugLog('✅ Logout successful');
    return response.data;
    
  } catch (error) {
    debugLog('❌ Logout failed:', error.message);

    // ✅ Même si le serveur échoue, on nettoie côté client
    resetAuthState();
    
    // Même si logout échoue côté serveur, on continue le logout côté client
    // Car l'utilisateur veut se déconnecter
    return { 
      success: true, 
      message: 'Logged out locally' 
    };
  }
};

/**
 * ✅ GET CURRENT USER - Fonction centrale pour vérification auth
 * @returns {Promise<Object>} {success: boolean, user?: Object, error?: string}
 */
export const getCurrentUser = async () => {
  debugLog('👤 Getting current user...');
  
  const result = await api.get(authConfig.ENDPOINTS.USER);
  
  if (result.success) {
    debugLog('✅ Current user retrieved successfully');
    return {
      success: true,
      user: result.data.user || result.data
    };
  } else {
    debugLog('❌ Failed to get current user:', result.error);
    // ✅ Session invalide / non authentifié → on nettoie lastRoute
    resetAuthState();
    
    return {
      success: false,
      error: result.error
    };
  }
};

export function useGetCurrentUserClient() {
  const { data, error, isLoading, isValidating } = useSWR(
    'auth/current-user',
    async () => {
      const res = await api.get(authConfig.ENDPOINTS.USER); 
      if (!res.success) throw new Error(res.error || 'Failed to fetch current user');
      return res.data.user || res.data;
    },
    {
      revalidateIfStale: false,
      revalidateOnFocus: false,
      revalidateOnReconnect: false
    }
  );

  const user = data || null;
  return {
    user,
    clientId: user?.client_id ?? null,
    clientName: user?.client_name ?? null,
    currentUserLoading: isLoading,
    currentUserError: error,
    currentUserValidating: isValidating
  };
}

/**
 * ✅ CHECK AUTH STATUS - Fonction originale restaurée
 * @returns {Promise<boolean>} Authentication status
 */
export const checkAuthStatus = async () => {
  try {
    const result = await getCurrentUser();
    return result.success;
  } catch (error) {
    debugLog('❌ User not authenticated:', error.message);
    return false;
  }
};

/**
 * ✅ SAVE LAST ROUTE
 * @param {string} route - Route to save
 */
export const saveLastRoute = (route) => {
  if (typeof window === 'undefined') return;
  
  debugLog('💾 Saving last route:', route);
  localStorage.setItem('lastRoute', route);
};

/**
 * ✅ GET AND CLEAR LAST ROUTE
 * @returns {string|null} Last saved route
 */
export const getAndClearLastRoute = () => {
  if (typeof window === 'undefined') return null;
  
  const lastRoute = localStorage.getItem('lastRoute');
  localStorage.removeItem('lastRoute');
  
  debugLog('📂 Retrieved and cleared last route:', lastRoute);
  return lastRoute;
};

// ==============================|| UTILITIES ||============================== //

/**
 * ✅ RESET AUTH STATE - SIMPLIFIÉ
 */
export const resetAuthState = () => {
  // Nettoyer autres données auth si nécessaire
  if (typeof window !== 'undefined') {
    localStorage.removeItem('lastRoute');
  }
  
  debugLog('🧹 Auth state reset');
};