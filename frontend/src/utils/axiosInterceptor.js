// frontend/src/utils/axiosInterceptor.js

import axios from 'axios';
import { authConfig, debugLog } from '../config/auth';

// ==============================|| AXIOS GLOBAL CONFIGURATION ||============================== //

// Configuration de base pour toutes les requêtes
axios.defaults.baseURL = authConfig.API_BASE_URL;
axios.defaults.timeout = authConfig.REQUEST_TIMEOUT;
axios.defaults.withCredentials = true; // IMPORTANT: Pour les cookies HTTP-only

// Headers par défaut
axios.defaults.headers.common['Content-Type'] = 'application/json';
axios.defaults.headers.common['Accept'] = 'application/json';

// ==============================|| REQUEST INTERCEPTOR ||============================== //

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  
  failedQueue = [];
};

// Intercepteur pour les requêtes sortantes
axios.interceptors.request.use(
  (config) => {
    // Log des requêtes en développement
    debugLog('Request:', {
      method: config.method?.toUpperCase(),
      url: config.url,
      headers: config.headers,
    });

    // Ajouter des headers spécifiques si nécessaire
    if (typeof window !== 'undefined') {
      // Ajouter le token CSRF si disponible
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
      if (csrfToken) {
        config.headers['X-CSRFToken'] = csrfToken;
      }
    }

    return config;
  },
  (error) => {
    debugLog('Request Error:', error);
    return Promise.reject(error);
  }
);

// ==============================|| RESPONSE INTERCEPTOR ||============================== //

// Intercepteur pour les réponses
axios.interceptors.response.use(
  (response) => {
    // Log des réponses en développement
    debugLog('Response:', {
      status: response.status,
      url: response.config.url,
      data: response.data,
    });

    return response;
  },
  async (error) => {
    debugLog('Response Error:', error);

    const originalRequest = error.config;

    // Gestion des erreurs 401 (Token expiré)
    if (error.response?.status === 401 && !originalRequest._retry) {
      debugLog('Token expiré, tentative de refresh...');

      if (isRefreshing) {
        // Si un refresh est déjà en cours, ajouter à la queue
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(() => {
          return axios(originalRequest);
        }).catch(err => {
          return Promise.reject(err);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Tenter de rafraîchir le token
        await axios.post(authConfig.ENDPOINTS.REFRESH);
        
        debugLog('Token refresh réussi');
        processQueue(null);
        isRefreshing = false;

        // Rejouer la requête originale
        return axios(originalRequest);
      } catch (refreshError) {
        debugLog('Refresh token failed:', refreshError);
        
        processQueue(refreshError, null);
        isRefreshing = false;

        // Rediriger vers la page de connexion
        if (typeof window !== 'undefined') {
          // Éviter la redirection en boucle si on est déjà sur la page de login
          const currentPath = window.location.pathname;
          if (currentPath !== authConfig.PAGES.LOGIN) {
            // Sauvegarder la route actuelle
            localStorage.setItem(authConfig.STORAGE_KEYS.LAST_ROUTE, currentPath);
            window.location.href = authConfig.PAGES.LOGIN;
          }
        }

        return Promise.reject(refreshError);
      }
    }

    // Gestion des autres erreurs
    return Promise.reject(enhanceError(error));
  }
);

// ==============================|| ERROR ENHANCEMENT ||============================== //

/**
 * Améliorer les messages d'erreur pour une meilleure UX
 */
const enhanceError = (error) => {
  if (!error.response) {
    // Erreur réseau
    error.userMessage = authConfig.ERROR_MESSAGES.NETWORK_ERROR;
    return error;
  }

  const { status, data } = error.response;

  switch (status) {
    case 400:
      error.userMessage = data?.message || 'Données invalides';
      break;
    case 401:
      error.userMessage = authConfig.ERROR_MESSAGES.UNAUTHORIZED;
      break;
    case 403:
      error.userMessage = 'Accès interdit. Vous n\'avez pas les permissions nécessaires.';
      break;
    case 404:
      error.userMessage = 'Ressource introuvable';
      break;
    case 422:
      error.userMessage = data?.message || 'Erreur de validation';
      break;
    case 429:
      error.userMessage = 'Trop de requêtes. Veuillez réessayer plus tard.';
      break;
    case 500:
      error.userMessage = authConfig.ERROR_MESSAGES.SERVER_ERROR;
      break;
    case 502:
    case 503:
    case 504:
      error.userMessage = 'Service temporairement indisponible. Veuillez réessayer.';
      break;
    default:
      error.userMessage = data?.message || 'Une erreur inattendue s\'est produite';
  }

  return error;
};

// ==============================|| UTILITY FUNCTIONS ||============================== //

/**
 * Créer une instance Axios avec configuration personnalisée
 */
export const createAxiosInstance = (baseURL, options = {}) => {
  const instance = axios.create({
    baseURL: baseURL || authConfig.API_BASE_URL,
    timeout: options.timeout || authConfig.REQUEST_TIMEOUT,
    withCredentials: true,
    ...options,
  });

  // Les intercepteurs sont automatiquement hérités
  return instance;
};

/**
 * Wrapper pour les requêtes avec retry automatique
 */
export const requestWithRetry = async (requestFn, maxRetries = authConfig.MAX_RETRY_ATTEMPTS) => {
  let lastError;
  
  for (let i = 0; i <= maxRetries; i++) {
    try {
      return await requestFn();
    } catch (error) {
      lastError = error;
      
      // Ne pas retry sur certaines erreurs
      if (error.response?.status === 401 || error.response?.status === 403) {
        throw error;
      }
      
      // Si c'est la dernière tentative
      if (i === maxRetries) {
        break;
      }
      
      // Attendre avant de retry
      const delay = authConfig.RETRY_DELAY * Math.pow(2, i); // Backoff exponentiel
      await new Promise(resolve => setTimeout(resolve, delay));
      
      debugLog(`Retry attempt ${i + 1}/${maxRetries} for request`);
    }
  }
  
  throw lastError;
};

/**
 * Helper pour les requêtes avec loading state
 */
export const requestWithLoading = async (requestFn, setLoading) => {
  try {
    setLoading(true);
    return await requestFn();
  } finally {
    setLoading(false);
  }
};

// ==============================|| HEALTH CHECK ||============================== //

/**
 * Vérifier la santé de l'API
 */
export const checkAPIHealth = async () => {
  try {
    const response = await axios.get('/health/', { timeout: 5000 });
    return response.status === 200;
  } catch (error) {
    debugLog('API Health check failed:', error);
    return false;
  }
};

// ==============================|| EXPORTS ||============================== //

export default axios;

// Export des utilitaires pour une utilisation dans d'autres composants
export {
  enhanceError,
  processQueue,
};