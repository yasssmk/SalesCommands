// frontend/src/api/auth.js

import axiosClient, { api } from '../utils/axiosClient';
import { authConfig, debugLog } from '../config/auth';

// ==============================|| AUTH API FUNCTIONS ||============================== //

/**
 * ✅ LOGIN USER
 * @param {string} email - User email
 * @param {string} password - User password
 * @returns {Promise<Object>} {success: boolean, user?: Object, error?: string}
 */
export const loginUser = async (email, password) => {
  debugLog('🔐 Login attempt for:', email);
  
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
  console.log('🔄 REFRESH-TOKENS: Making POST request to /client/refresh-token/');
  
  const result = await api.post(authConfig.ENDPOINTS.REFRESH);
  
  if (result.success) {
    debugLog('✅ Tokens refreshed successfully');
    console.log('✅ REFRESH-TOKENS: POST /client/refresh-token/ successful');
    return {
      success: true,
      user: result.data.user || result.data
    };
  } else {
    debugLog('❌ Token refresh failed:', result.error);
    console.log('❌ REFRESH-TOKENS: POST /client/refresh-token/ failed:', result.error);
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
    
    debugLog('✅ Logout successful');
    return response.data;
    
  } catch (error) {
    debugLog('❌ Logout failed:', error.message);
    
    // Même si logout échoue côté serveur, on continue le logout côté client
    // Car l'utilisateur veut se déconnecter
    return { 
      success: true, 
      message: 'Logged out locally' 
    };
  }
};

/**
 * ✅ GET CURRENT USER
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
    return {
      success: false,
      error: result.error
    };
  }
};

/**
 * ✅ CHECK AUTH STATUS
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

// ==============================|| ROUTE MANAGEMENT ||============================== //

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
 * ✅ RESET AUTH STATE - SIMPLIFIÉ (plus de logique complexe)
 */
export const resetAuthState = () => {
  // Nettoyer autres données auth si nécessaire
  if (typeof window !== 'undefined') {
    localStorage.removeItem('lastRoute');
  }
  
  debugLog('🧹 Auth state reset');
};