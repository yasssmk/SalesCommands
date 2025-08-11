// frontend/src/api/auth.js

import axios from 'axios';
import { authConfig, debugLog } from '../config/auth';
import { handleApiError } from '../utils/errorHandler';

// ==============================|| AUTH API CONFIGURATION ||============================== //

const authAxios = axios.create({
  baseURL: authConfig.API_BASE_URL,
  timeout: authConfig.REQUEST_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Pour les cookies HTTP-only
});

// ==============================|| AUTH API FUNCTIONS ||============================== //

/**
 * ✅ LOGIN USER
 * @param {string} email - User email
 * @param {string} password - User password
 * @returns {Promise<Object>} {success: boolean, user?: Object, error?: string}
 */
export const loginUser = async (email, password) => {
  try {
    debugLog('Login attempt for:', email);
    
    const response = await authAxios.post(authConfig.ENDPOINTS.LOGIN, {
      email,
      password
    });
    
    debugLog('Login successful for:', email);
    
    return {
      success: true,
      user: response.data.user || response.data,
    };
    
  } catch (error) {
    debugLog('Login failed:', error.message);
    const errorMessage = handleApiError(error);
    return { success: false, error: errorMessage };
  }
};

/**
 * ✅ LOGOUT USER
 * @returns {Promise<Object>} Response confirmation
 */
export const logoutUser = async () => {
  try {
    debugLog('Logging out user...');
    
    const response = await authAxios.post(authConfig.ENDPOINTS.LOGOUT);
    
    debugLog('Logout successful');
    return response.data;
    
  } catch (error) {
    debugLog('Logout failed:', error.message);
    const errorMessage = handleApiError(error);
    return { success: false, error: errorMessage };
  }
};

/**
 * ✅ GET CURRENT USER
 * @returns {Promise<Object>} {success: boolean, user?: Object, error?: string}
 */
export const getCurrentUser = async () => {
  try {
    debugLog('Getting current user...');
    
    const response = await authAxios.get(authConfig.ENDPOINTS.USER);
    
    debugLog('Current user retrieved successfully');
    return {
      success: true,
      user: response.data.user || response.data
    };
    
  } catch (error) {
    debugLog('Failed to get current user:', error.message);
    const errorMessage = handleApiError(error);
    return { success: false, error: errorMessage };
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
    debugLog('User not authenticated:', error.message);
    return false;
  }
};

/**
 * ✅ SAVE LAST ROUTE
 * @param {string} route - Route to save
 */
export const saveLastRoute = (route) => {
  if (typeof window === 'undefined') return;
  
  debugLog('Saving last route:', route);
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
  
  debugLog('Retrieved and cleared last route:', lastRoute);
  return lastRoute;
};