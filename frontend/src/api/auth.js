// utils
import axios from 'axios';

// ==============================|| AUTH API CONFIGURATION ||============================== //

const authAxios = axios.create({ 
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  }
});

// ==============================|| AUTH API ENDPOINTS ||============================== //

export const authEndpoints = {
  login: '/client/login/',
  logout: '/api/auth/logout/',
  refresh: '/api/auth/refresh/',
  me: '/api/auth/me/',
  register: '/api/auth/register/',
  forgotPassword: '/api/auth/forgot-password/',
  resetPassword: '/api/auth/reset-password/',
};

// ==============================|| AUTH API FUNCTIONS ||============================== //

/**
 * Login user with email and password
 * @param {string} email - User email
 * @param {string} password - User password
 * @returns {Promise} Response with tokens and user data
 */
export const loginUser = async (email, password) => {
  try {
    const response = await authAxios.post(authEndpoints.login, {
      email: email.trim(),
      password,
    });


    return response.data;
  } catch (error) {
    // Gestion d'erreurs spécifiques selon les réponses Django
    if (error.response?.data?.message) {
      throw new Error(error.response.data.message);
    } else if (error.response?.data?.error) {
      throw new Error(error.response.data.error);
    } else if (error.response?.data?.non_field_errors) {
      throw new Error(error.response.data.non_field_errors[0]);
    } else if (error.response?.status === 401) {
      throw new Error('Email ou mot de passe incorrect');
    } else if (error.response?.status === 400) {
      throw new Error('Données de connexion invalides');
    } else if (error.response?.status >= 500) {
      throw new Error('Erreur serveur, veuillez réessayer plus tard');
    } else {
      throw new Error('Erreur de connexion au serveur');
    }
  }
};

/**
 * Logout user
 * @param {string} refreshToken - Refresh token
 * @returns {Promise} Logout response
 */
export const logoutUser = async (refreshToken = null) => {
  try {
    const token = localStorage.getItem('access_token');
    const config = {
      headers: {
        'Authorization': token ? `Bearer ${token}` : undefined
      }
    };

    const payload = refreshToken ? { refresh_token: refreshToken } : {};
    
    const response = await authAxios.post(authEndpoints.logout, payload, config);
    
    // Nettoyer le localStorage
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    
    return response.data;
  } catch (error) {
    // Même en cas d'erreur, on nettoie le localStorage
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    throw new Error(error.response?.data?.message || 'Erreur lors de la déconnexion');
  }
};

/**
 * Refresh access token
 * @param {string} refreshToken - Refresh token
 * @returns {Promise} New access token
 */
export const refreshAccessToken = async (refreshToken) => {
  try {
    const response = await authAxios.post(authEndpoints.refresh, {
      refresh_token: refreshToken,
    });

    return response.data;
  } catch (error) {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    throw new Error('Session expirée, veuillez vous reconnecter');
  }
};

/**
 * Get current user info
 * @returns {Promise} User data
 */
export const getCurrentUser = async () => {
  try {
    const token = localStorage.getItem('access_token');
    if (!token) {
      throw new Error('Aucun token trouvé');
    }

    const response = await authAxios.get(authEndpoints.me, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    return response.data;
  } catch (error) {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      throw new Error('Session expirée');
    }
    throw new Error(error.response?.data?.message || 'Erreur lors de la récupération des données utilisateur');
  }
};

/**
 * Register new user
 * @param {Object} userData - User registration data
 * @returns {Promise} Registration response
 */
export const registerUser = async (userData) => {
  try {
    const response = await authAxios.post(authEndpoints.register, userData);
    return response.data;
  } catch (error) {
    if (error.response?.data?.email) {
      throw new Error('Cette adresse email est déjà utilisée');
    } else if (error.response?.data?.password) {
      throw new Error(error.response.data.password[0]);
    } else if (error.response?.data?.message) {
      throw new Error(error.response.data.message);
    } else {
      throw new Error('Erreur lors de l\'inscription');
    }
  }
};

// ==============================|| AUTH HELPERS ||============================== //

/**
 * Check if user is authenticated
 * @returns {boolean} Authentication status
 */
export const isAuthenticated = () => {
  if (typeof window === 'undefined') return false;
  
  const token = localStorage.getItem('access_token');
  return !!token;
};

/**
 * Get stored access token
 * @returns {string|null} Access token
 */
export const getAccessToken = () => {
  if (typeof window === 'undefined') return null;
  
  return localStorage.getItem('access_token');
};

/**
 * Store authentication tokens
 * @param {string} accessToken - Access token
 * @param {string} refreshToken - Refresh token (optional)
 */
export const storeTokens = (accessToken, refreshToken = null) => {
  if (typeof window === 'undefined') return;
  
  localStorage.setItem('access_token', accessToken);
  if (refreshToken) {
    localStorage.setItem('refresh_token', refreshToken);
  }
};