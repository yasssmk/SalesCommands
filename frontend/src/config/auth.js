// frontend/src/config/auth.js

// ==============================|| AUTH CONFIGURATION ||============================== //

const DEFAULT_API_BASE_URL = 'http://localhost:8000';
export const isDevelopment = process.env.NODE_ENV === 'development';

// ⚠️ En dev, on force localhost pour que les cookies HttpOnly (SameSite=Lax) fonctionnent.
//    Ports différents OK, mais le HOST doit rester "localhost".
function resolveApiBaseUrl() {
  const envUrl = process.env.NEXT_PUBLIC_API_URL;

  if (!isDevelopment) {
    // En prod: on fait confiance à la variable d'env si fournie
    return envUrl || DEFAULT_API_BASE_URL;
  }

  try {
    const url = new URL(envUrl || DEFAULT_API_BASE_URL);
    if (url.hostname !== 'localhost') {
      // eslint-disable-next-line no-console
      console.warn(
        '[AUTH WARN]: In development, API_BASE_URL should use "localhost" to allow cookies.',
        'Overriding',
        envUrl,
        '→',
        DEFAULT_API_BASE_URL
      );
      return DEFAULT_API_BASE_URL;
    }
    return url.origin;
  } catch {
    return DEFAULT_API_BASE_URL;
  }
}

export const authConfig = {
  // Durée de vie des tokens (en millisecondes)
  TOKEN_REFRESH_INTERVAL: 6 * 60 * 60 * 1000, // 6 heures
  // TOKEN_REFRESH_INTERVAL: 2 * 60 * 1000, // 2 minutes pour test 
  TOKEN_REFRESH_THRESHOLD: 5 * 60 * 1000,     // 5 minutes avant expiration

  // Endpoints backend Django
  API_BASE_URL: resolveApiBaseUrl(),

  ENDPOINTS: {
    LOGIN: '/client/login/',
    LOGOUT: '/client/logout/',
    REFRESH: '/client/refresh-token/',
    USER: '/client/user/'
  },

  // Pages de redirection
  PAGES: {
    LOGIN: '/login',
    DASHBOARD: '/',
    HOME: '/'
  },

  // Messages d'erreur personnalisés
  ERROR_MESSAGES: {
    NETWORK_ERROR: 'Network error. Please check your connection and try again.',
    SERVER_ERROR: 'Server Error',
    UNKNOWN_ERROR: 'Something went wrong. Please try again.'
  },

  // Options des cookies (côté serveur, référence)
  COOKIE_OPTIONS: {
    REFRESH_TOKEN_NAME: 'refresh_token',
    ACCESS_TOKEN_NAME: 'access_token',
    SAME_SITE: 'Lax',
    SECURE: process.env.NODE_ENV === 'production',
    HTTP_ONLY: true
  },

  // Configuration de retry et timeouts
  REQUEST_TIMEOUT: 10000, // 10 secondes
  MAX_RETRY_ATTEMPTS: 3,
  RETRY_DELAY: 1000, // 1 seconde

  // Configuration du localStorage pour données non sensibles
  STORAGE_KEYS: {
    USER_PREFERENCES: 'user_preferences',
    LAST_ROUTE: 'last_route',
    THEME: 'theme_preference'
  }
};

// Helper logs dev
export const debugLog = (...args) => {
  if (isDevelopment) {
    // eslint-disable-next-line no-console
    console.log('[AUTH DEBUG]:', ...args);
  }
};

export default authConfig;


// // ==============================|| AUTH CONFIGURATION ||============================== //

// export const authConfig = {
//   // Durée de vie des tokens (en millisecondes)
//   TOKEN_REFRESH_INTERVAL: 6 * 60 * 60 * 1000, // 6 heures
//   TOKEN_REFRESH_THRESHOLD: 5 * 60 * 1000, // 5 minutes avant expiration

//   // TOKEN_REFRESH_INTERVAL: 2 * 60 * 1000, // 2 minutes pour test
//   // TOKEN_REFRESH_THRESHOLD: 5 * 60 * 1000, // 5 minutes avant expiration
  
//   // Endpoints backend Django
//   API_BASE_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  
//   ENDPOINTS: {
//     LOGIN: '/client/login/',
//     LOGOUT: '/client/logout/',
//     REFRESH: '/client/refresh-token/',
//     USER: '/client/user/',
//   },
  
//   // Pages de redirection
//   PAGES: {
//     LOGIN: '/login',
//     DASHBOARD: '/', // ou '/dashboardHome' selon votre structure
//     HOME: '/',
//   },

//   // Messages d'erreur personnalisés
//    ERROR_MESSAGES: {
//     NETWORK_ERROR: 'Network error. Please check your connection and try again.',
//     SERVER_ERROR: 'Server Error',
//     UNKNOWN_ERROR: 'Something went wrong. Please try again.'
//   },
  
//   // Options des cookies (côté serveur, mais pour référence)
//   COOKIE_OPTIONS: {
//     REFRESH_TOKEN_NAME: 'refresh_token',
//     ACCESS_TOKEN_NAME: 'access_token',
//     SAME_SITE: 'Lax',
//     SECURE: process.env.NODE_ENV === 'production',
//     HTTP_ONLY: true,
//   },
  
//   // Configuration de retry et timeouts
//   REQUEST_TIMEOUT: 10000, // 10 secondes
//   MAX_RETRY_ATTEMPTS: 3,
//   RETRY_DELAY: 1000, // 1 seconde
  
  
//   // Configuration du localStorage pour les données non-sensibles
//   STORAGE_KEYS: {
//     USER_PREFERENCES: 'user_preferences',
//     LAST_ROUTE: 'last_route',
//     THEME: 'theme_preference',
//   },
// };

// // Helper pour vérifier si on est en environnement de développement
// export const isDevelopment = process.env.NODE_ENV === 'development';

// // Helper pour les logs de debug en développement uniquement
// export const debugLog = (...args) => {
//   if (isDevelopment) {
//     console.log('[AUTH DEBUG]:', ...args);
//   }
// };

// export default authConfig;