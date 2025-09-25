// frontend/src/api/auth.js

import axiosClient, { api } from '../utils/axiosClient';
import { authConfig, debugLog } from '../config/auth';
import useSWR from 'swr';
import { tenantKey } from '../api/_swr';
import { useAuth } from '../hooks/useAuth';


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
    // Le backend retourne maintenant : {message: "...", user: {...}}
    const userData = result.data?.user;
    
    // Log pour debug
    if (userData) {
      debugLog('✅ Tokens refreshed successfully with user data:', {
        id: userData.id,
        email: userData.email,
        role: userData.role?.name
      });
    } else {
      debugLog('⚠️ Tokens refreshed but no user data in response (legacy backend?)');
    }
    
    return {
      success: true,
      user: userData || null  // Explicitement null si pas de données (au lieu de undefined)
    };
  } else {
    debugLog('❌ Token refresh failed:', result.error);
    // ✅ Déconnexion forcée / session expirée → on nettoie
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
 * ⚠️ USAGE INTERNE UNIQUEMENT PAR useAuth()
 * ⚠️ NE PAS UTILISER DIRECTEMENT - Utiliser useCurrentUser() hook à la place
 * 
 * @private
 */
export const getCurrentUser = async () => {
  debugLog('👤 Getting current user...');
  
  const result = await api.get(authConfig.ENDPOINTS.USER);
  
  if (result.success) {
    const userData = result.data.user || result.data;

    debugLog('✅ Current user retrieved:', {
      id: userData.id,
      email: userData.email,
      role: userData.role
    });

    return {
      success: true,
      user: userData
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

// NOTE: Pour accéder au current user, utiliser:
// - import { useCurrentUser } from 'hooks/useCurrentUser';
// - const { currentUser, currentUserLoading } = useCurrentUser();

// export function useGetCurrentUserClient() {
//   const { data, error, isLoading, isValidating } = useSWR(
//     'auth/current-user',
//     async () => {
//       const res = await api.get(authConfig.ENDPOINTS.USER); 
//       if (!res.success) throw new Error(res.error || 'Failed to fetch current user');
//       return res.data.user || res.data;
//     },
//     {
//       revalidateIfStale: false,
//       revalidateOnFocus: false,
//       revalidateOnReconnect: false
//     }
//   );

//   const user = data || null;
//   return {
//     user,
//     clientId: user?.client_id ?? null,
//     clientName: user?.client_name ?? null,
//     currentUserLoading: isLoading,
//     currentUserError: error,
//     currentUserValidating: isValidating
//   };
// }

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

// /**
//  * ✅ SAVE LAST ROUTE
//  * @param {string} route - Route to save
//  */
// export const saveLastRoute = (route) => {
//   if (typeof window === 'undefined') return;
  
//   debugLog('💾 Saving last route:', route);
//   localStorage.setItem('lastRoute', route);
// };

// /**
//  * ✅ GET AND CLEAR LAST ROUTE
//  * @returns {string|null} Last saved route
//  */
// export const getAndClearLastRoute = () => {
//   if (typeof window === 'undefined') return null;
  
//   const lastRoute = localStorage.getItem('lastRoute');
//   localStorage.removeItem('lastRoute');
  
//   debugLog('📂 Retrieved and cleared last route:', lastRoute);
//   return lastRoute;
// };

// ==============================|| UTILITIES ||============================== //

/**
 * ✅ RESET AUTH STATE - SIMPLIFIÉ
 */
export const resetAuthState = () => {
 if (typeof window === 'undefined') return;
  
    try {
      sessionStorage.clear();
    } catch (e) {
      debugLog('⚠️ Failed to clear sessionStorage:', e);
    }
    
    debugLog('🧹 Auth state reset complete (UI preferences preserved)');
};