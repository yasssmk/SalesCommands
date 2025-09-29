// frontend/src/utils/axiosClient.js

import axios from 'axios';
import { authConfig, debugLog } from '../config/auth';
import { handleApiError } from '../utils/errorHandler';

// ==============================|| CENTRAL AXIOS CLIENT ||============================== //

/**
 * ✅ AXIOS CLIENT CENTRAL AVEC AUTO-REFRESH
 * 
 * - Cookies HTTP-only automatiques (withCredentials: true)  
 * - Auto-refresh sur 401 (1 seul retry, pas de boucle infinie)
 * - Utilise handleApiError existant pour les messages backend
 * - Simple et efficace pour MVP
 */

const axiosClient = axios.create({
  baseURL: authConfig.API_BASE_URL,
  timeout: authConfig.REQUEST_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Essentiel pour les cookies HTTP-only
});

// Flag pour éviter les boucles infinies de refresh - SUPPRIMÉ (plus nécessaire)
// let isRefreshing = false;

// ==============================|| REQUEST INTERCEPTOR ||============================== //

axiosClient.interceptors.request.use(
  (config) => {
    debugLog(`🚀 API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    debugLog('❌ Request interceptor error:', error);
    return Promise.reject(error);
  }
);

// ==============================|| RESPONSE INTERCEPTOR ||============================== //

axiosClient.interceptors.response.use(
  (response) => {
    debugLog(`✅ API Response: ${response.status} ${response.config.url}`);
    return response;
  },
  (error) => {
    const status = error?.response?.status;
    const url = error?.config?.url;
    debugLog(`❌ API Error: ${status ?? '—'} ${url ?? '—'}`);
    return Promise.reject(error);
  }
);

// ==============================|| HELPER FUNCTIONS ||============================== //

/**
 * ✅ WRAPPER POUR REQUÊTES AVEC GESTION D'ERREUR AUTOMATIQUE
 * @param {Function} requestFn - Fonction de requête axios
 * @returns {Promise<{success: boolean, data?: any, error?: string}>}
 */
export const apiRequest = async (requestFn) => {
  try {
    const response = await requestFn();
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    const errorMessage = handleApiError(error);
    debugLog('❌ API Request failed:', errorMessage);
    
    return {
      success: false,
      error: errorMessage,
      status: error.response?.status || 0,
      response: error.response || null
    };
  }
};

/**
 * ✅ RESET REFRESH STATE - SUPPRIMÉ (plus nécessaire avec interceptor simplifié)
 */
// export const resetRefreshState = () => {
//   isRefreshing = false;
//   debugLog('🔄 Refresh state reset');
// };

// ==============================|| EXPORTS ||============================== //

export default axiosClient;

// Méthodes de convenance avec gestion d'erreur intégrée
export const api = {
  get: (url, config = {}) => apiRequest(() => axiosClient.get(url, config)),
  post: (url, data = {}, config = {}) => apiRequest(() => axiosClient.post(url, data, config)),
  put: (url, data = {}, config = {}) => apiRequest(() => axiosClient.put(url, data, config)),
  patch: (url, data = {}, config = {}) => apiRequest(() => axiosClient.patch(url, data, config)),
  delete: (url, config = {}) => apiRequest(() => axiosClient.delete(url, config))
};