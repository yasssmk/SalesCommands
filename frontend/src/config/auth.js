// frontend/src/config/auth.js

// ==============================|| AUTH CONFIGURATION ||============================== //

const DEFAULT_API_BASE_URL = "http://localhost:8000";
export const isDevelopment = process.env.NODE_ENV === "development";

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
    if (url.hostname !== "localhost") {
      // eslint-disable-next-line no-console
      console.warn(
        '[AUTH WARN]: In development, API_BASE_URL should use "localhost" to allow cookies.',
        "Overriding",
        envUrl,
        "→",
        DEFAULT_API_BASE_URL,
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
  // TOKEN_REFRESH_INTERVAL: 10 * 60 * 1000, // N minutes pour test
  TOKEN_REFRESH_THRESHOLD: 5 * 60 * 1000, // 5 minutes avant expiration

  // Endpoints backend Django
  API_BASE_URL: resolveApiBaseUrl(),

  ENDPOINTS: {
    LOGIN: "/client/login/",
    LOGOUT: "/client/logout/",
    REFRESH: "/client/refresh-token/",
    USER: "/client/user/",
  },

  // Pages de redirection
  PAGES: {
    LOGIN: "/login",
    DASHBOARD: "/",
    HOME: "/",
  },

  // Messages d'erreur personnalisés
  ERROR_MESSAGES: {
    NETWORK_ERROR: "Network error. Please check your connection and try again.",
    SERVER_ERROR: "Server Error",
    UNKNOWN_ERROR: "Something went wrong. Please try again.",
  },

  // Options des cookies (côté serveur, référence)
  COOKIE_OPTIONS: {
    REFRESH_TOKEN_NAME: "refresh_token",
    ACCESS_TOKEN_NAME: "access_token",
    SAME_SITE: "Lax",
    SECURE: process.env.NODE_ENV === "production",
    HTTP_ONLY: true,
  },

  // ==============================|| TIMEOUT PROFILES ||============================== //

  /**
   * ✅ NEW: Differentiated timeout profiles for various operation types
   *
   * Ensures proper timeout handling aligned with backend configuration:
   * - Frontend timeout < Backend timeout (avoid 504 Gateway Timeout)
   * - Backend target: Nginx 15s, Gunicorn 15s, DB statement_timeout 10s
   *
   * Usage examples:
   *   api.get(url, { profile: 'critical' })  // 8s timeout
   *   api.get(url, { profile: 'widget' })    // 4s timeout
   *   api.post(url, data)                    // 10s timeout (default for mutations)
   *   api.post(url, data, { profile: 'bulk' }) // 60s timeout
   */
  TIMEOUT_PROFILES: {
    CRITICAL: 8000, // 8s - Critical GET requests (main data: users, accounts, contacts)
    WIDGET: 4000, // 4s - Dashboard widgets, quick stats, non-critical data
    MUTATION: 10000, // 10s - POST/PUT/PATCH/DELETE operations (form submissions)
    BULK: 18000, // 18s - Bulk operations (import/export, bulk delete/update)
    AUTH: 5000, // 5s - Authentication operations (login, refresh token)
  },

  // ==============================|| LEGACY TIMEOUT SETTINGS ||============================== //

  /**
   * @deprecated Use TIMEOUT_PROFILES.MUTATION instead
   * Kept for backward compatibility with existing code
   */
  REQUEST_TIMEOUT: 10000, // 10 seconds (default for mutations)

  /**
   * @deprecated Use TIMEOUT_PROFILES.BULK instead
   * Previously defined but never used in the codebase
   */
  BULK_OPERATION_TIMEOUT: 18000, // Now implemented in TIMEOUT_PROFILES.BULK

  // ==============================|| RETRY CONFIGURATION ||============================== //

  MAX_RETRY_ATTEMPTS: 3,
  RETRY_DELAY: 1000, // 1 second

  // Configuration du localStorage pour données non sensibles
  STORAGE_KEYS: {
    USER_PREFERENCES: "user_preferences",
    LAST_ROUTE: "last_route",
    THEME: "theme_preference",
  },
};

// Helper logs dev
export const debugLog = (...args) => {
  if (isDevelopment) {
    // eslint-disable-next-line no-console
    console.log("[AUTH DEBUG]:", ...args);
  }
};

export default authConfig;
