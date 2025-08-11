// utils
import axios from 'axios';
import { authConfig, debugLog} from '../config/auth'


// ==============================|| AUTH API CONFIGURATION ||============================== //

const authAxios = axios.create({
  baseURL: authConfig.API_BASE_URL,
  timeout: authConfig.REQUEST_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // IMPORTANT: Pour envoyer les cookies HTTP-only
});

// ==============================|| INTERCEPTORS ||============================== //

// Intercepteur de réponse pour gérer les erreurs globales
authAxios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // Si erreur 401 et ce n'est pas déjà une tentative de refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      try {
        debugLog('Token expiré, tentative de refresh...');
        await refreshTokens();
        return authAxios(originalRequest);
      } catch (refreshError) {
        debugLog('Refresh failed, redirection vers login');
        // Le refresh a échoué, l'utilisateur doit se reconnecter
        window.location.href = authConfig.PAGES.LOGIN;
        return Promise.reject(refreshError);
      }
    }
    
    return Promise.reject(error);
  }
);

// ==============================|| AUTH API FUNCTIONS ||============================== //

/**
 * Login user with email and password
 * @param {string} email - User email
 * @param {string} password - User password
 * @returns {Promise<Object>} Response with tokens and user data
 */
export const loginUser = async (email, password) => {
  try {
    debugLog('Tentative de connexion pour:', email);
    
    const response = await authAxios.post(authConfig.ENDPOINTS.LOGIN, {
      email: email.trim(),
      password,
    });

    debugLog('Connexion réussie:', response.data);
    
    // Les tokens sont maintenant dans les cookies HTTP-only
    // On retourne uniquement les données utilisateur
    return {
      success: true,
      user: response.data.user,
      message: response.data.message,
    };
  } catch (error) {
    debugLog('Erreur de connexion:', error);
    
    // Gestion d'erreurs spécifiques selon les réponses Django
    let errorMessage = authConfig.ERROR_MESSAGES.SERVER_ERROR;
    
    if (error.response?.data?.message) {
      errorMessage = error.response.data.message;
    } else if (error.response?.data?.error) {
      errorMessage = error.response.data.error;
    } else if (error.response?.data?.non_field_errors) {
      errorMessage = error.response.data.non_field_errors[0];
    } else if (error.response?.status === 401) {
      errorMessage = authConfig.ERROR_MESSAGES.INVALID_CREDENTIALS;
    } else if (error.response?.status === 400) {
      errorMessage = 'Données de connexion invalides';
    } else if (error.response?.status >= 500) {
      errorMessage = authConfig.ERROR_MESSAGES.SERVER_ERROR;
    } else if (error.code === 'NETWORK_ERROR') {
      errorMessage = authConfig.ERROR_MESSAGES.NETWORK_ERROR;
    }
    
    return {
      success: false,
      error: errorMessage,
    };
  }
};

/**
 * Déconnexion utilisateur
 * @returns {Promise<Object>} Résultat de la déconnexion
 */
export const logoutUser = async () => {
  try {
    debugLog('Tentative de déconnexion...');
    
    const response = await authAxios.post(authConfig.ENDPOINTS.LOGOUT);
    
    debugLog('Déconnexion réussie');
    
    // Nettoyer les données locales non-sensibles
    clearLocalUserData();
    
    return {
      success: true,
      message: response.data.message || 'Déconnexion réussie',
    };
  } catch (error) {
    debugLog('Erreur lors de la déconnexion:', error);
    
    // Même en cas d'erreur, on nettoie localement
    clearLocalUserData();
    
    return {
      success: false,
      error: error.response?.data?.message || 'Erreur lors de la déconnexion',
    };
  }
};

/**
 * Rafraîchir les tokens d'accès
 * @returns {Promise<Object>} Nouveaux tokens
 */
export const refreshTokens = async () => {
  try {
    debugLog('Tentative de refresh des tokens...');
    
    const response = await authAxios.post(authConfig.ENDPOINTS.REFRESH);
    
    debugLog('Tokens rafraîchis avec succès');
    
    return {
      success: true,
      message: response.data.message || 'Tokens rafraîchis',
    };
  } catch (error) {
    debugLog('Erreur lors du refresh:', error);
    
    // En cas d'erreur, nettoyer les données locales
    clearLocalUserData();
    
    throw new Error(authConfig.ERROR_MESSAGES.SESSION_EXPIRED);
  }
};

/**
 * Obtenir les informations de l'utilisateur connecté
 * @returns {Promise<Object>} Données utilisateur
 */
export const getCurrentUser = async () => {
  try {
    debugLog('Récupération des données utilisateur...');
    
    const response = await authAxios.get(authConfig.ENDPOINTS.ME);
    
    debugLog('Données utilisateur récupérées:', response.data);
    
    return {
      success: true,
      user: response.data,
    };
  } catch (error) {
    debugLog('Erreur lors de la récupération utilisateur:', error);
    
    if (error.response?.status === 401) {
      throw new Error(authConfig.ERROR_MESSAGES.SESSION_EXPIRED);
    }
    
    throw new Error(
      error.response?.data?.message || 
      'Erreur lors de la récupération des données utilisateur'
    );
  }
};

/**
 * Vérifier si l'utilisateur est authentifié
 * @returns {Promise<boolean>} Statut d'authentification
 */
export const checkAuthStatus = async () => {
  try {
    await getCurrentUser();
    return true;
  } catch (error) {
    debugLog('Utilisateur non authentifié:', error.message);
    return false;
  }
};

// ==============================|| HELPER FUNCTIONS ||============================== //

/**
 * Nettoyer les données locales non-sensibles
 */
const clearLocalUserData = () => {
  if (typeof window === 'undefined') return;
  
  // On garde seulement les préférences utilisateur non-sensibles
  const preferences = localStorage.getItem(authConfig.STORAGE_KEYS.USER_PREFERENCES);
  const theme = localStorage.getItem(authConfig.STORAGE_KEYS.THEME);
  
  localStorage.clear();
  
  // Restaurer les préférences
  if (preferences) {
    localStorage.setItem(authConfig.STORAGE_KEYS.USER_PREFERENCES, preferences);
  }
  if (theme) {
    localStorage.setItem(authConfig.STORAGE_KEYS.THEME, theme);
  }
};

/**
 * Sauvegarder la route actuelle pour redirection post-login
 * @param {string} route - Route à sauvegarder
 */
export const saveLastRoute = (route) => {
  if (typeof window === 'undefined') return;
  
  localStorage.setItem(authConfig.STORAGE_KEYS.LAST_ROUTE, route);
};

/**
 * Récupérer et supprimer la dernière route sauvegardée
 * @returns {string|null} Dernière route
 */
export const getAndClearLastRoute = () => {
  if (typeof window === 'undefined') return null;
  
  const lastRoute = localStorage.getItem(authConfig.STORAGE_KEYS.LAST_ROUTE);
  localStorage.removeItem(authConfig.STORAGE_KEYS.LAST_ROUTE);
  
  return lastRoute;
};

// ==============================|| EXPORTS ||============================== //

export default {
  loginUser,
  logoutUser,
  refreshTokens,
  getCurrentUser,
  checkAuthStatus,
  saveLastRoute,
  getAndClearLastRoute,
};