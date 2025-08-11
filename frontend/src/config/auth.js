// frontend/src/config/auth.js

// ==============================|| AUTH CONFIGURATION ||============================== //

export const authConfig = {
  // Durée de vie des tokens (en millisecondes)
  TOKEN_REFRESH_INTERVAL: 6 * 60 * 60 * 1000, // 6 heures
  TOKEN_REFRESH_THRESHOLD: 5 * 60 * 1000, // 5 minutes avant expiration
  
  // Endpoints backend Django
  API_BASE_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  
  ENDPOINTS: {
    LOGIN: '/end_users/login/',
    LOGOUT: '/end_users/logout/',
    REFRESH: '/end_users/refresh-token/',
    ME: '/api/auth/me/', // à ajuster selon votre backend
  },
  
  // Pages de redirection
  PAGES: {
    LOGIN: '/login',
    DASHBOARD: '/dashboard', // ou '/dashboardHome' selon votre structure
    HOME: '/',
  },

    // Messages d'erreur personnalisés
  ERROR_MESSAGES: {
    NETWORK_ERROR: 'Erreur de connexion. Vérifiez votre connexion internet.',
    INVALID_CREDENTIALS: 'Email ou mot de passe incorrect.',
    SESSION_EXPIRED: 'Votre session a expiré. Veuillez vous reconnecter.',
    SERVER_ERROR: 'Erreur serveur. Veuillez réessayer plus tard.',
    UNAUTHORIZED: 'Vous n\'êtes pas autorisé à accéder à cette ressource.',
  },
  
  // Options des cookies (côté serveur, mais pour référence)
  COOKIE_OPTIONS: {
    REFRESH_TOKEN_NAME: 'refresh_token',
    ACCESS_TOKEN_NAME: 'access_token',
    SAME_SITE: 'Lax',
    SECURE: process.env.NODE_ENV === 'production',
    HTTP_ONLY: true,
  },
  
  // Configuration de retry et timeouts
  REQUEST_TIMEOUT: 10000, // 10 secondes
  MAX_RETRY_ATTEMPTS: 3,
  RETRY_DELAY: 1000, // 1 seconde
  
  
  // Configuration du localStorage pour les données non-sensibles
  STORAGE_KEYS: {
    USER_PREFERENCES: 'user_preferences',
    LAST_ROUTE: 'last_route',
    THEME: 'theme_preference',
  },
};

// Helper pour vérifier si on est en environnement de développement
export const isDevelopment = process.env.NODE_ENV === 'development';

// Helper pour les logs de debug en développement uniquement
export const debugLog = (...args) => {
  if (isDevelopment) {
    console.log('[AUTH DEBUG]:', ...args);
  }
};

export default authConfig;