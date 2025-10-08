'use client';
import PropTypes from 'prop-types';

// SWR
import { SWRConfig } from 'swr';

// SWR fetcher global
import swrFetcher from '../utils/swrFetcher';

// Monitoring
import metricsCollector from '../utils/monitoring';

// project import
import ThemeCustomization from '../themes';

import Locales from 'components/Locales';
import ScrollTop from 'components/ScrollTop';
import RTLLayout from 'components/RTLLayout';
import Snackbar from 'components/@extended/Snackbar';
import Notistack from 'components/third-party/Notistack';

import { ConfigProvider } from '../contexts/ConfigContext';
import { AuthProvider } from '../hooks/useAuth';

import { openSnackbar } from '../api/snackbar';

// Load feature flags in development
if (process.env.NODE_ENV === 'development') {
  import('../config/features').then(module => {
    console.log('✅ Feature flags module loaded');
    // The module self-initializes and exposes helpers to window
  }).catch(err => {
    console.warn('⚠️ Could not load feature flags:', err.message);
  });
}


// ==============================|| GLOBAL PAUSE STATE ||============================== //

/**
 * ✅ État global de pause pour SWR
 * 
 * Permet de figer TOUTES les revalidations SWR pendant un cooldown 429.
 * Utilise un timestamp (pas un boolean) pour éviter les race conditions.
 * 
 * IMPORTANT : Cet état est en dehors du composant React pour :
 * - Être partagé entre tous les hooks SWR
 * - Persister entre les re-renders
 * - Éviter les re-renders inutiles
 */
let __swrPauseUntil = 0;
let __lastToastTime = 0;  // ✅  Dedup temporel des toasts
const TOAST_DEDUP_MS = 5000;  // Max 1 toast / 5s
const TOAST_KEY_429 = 'rate-limit-429';  // Clé unique Notistack

/**
 * Active la pause globale jusqu'à un timestamp donné
 * @param {number} timestampMs - Timestamp absolu (Date.now() + delay)
 */
const setPauseUntil = (timestampMs) => {
  __swrPauseUntil = timestampMs;
  
  if (process.env.NODE_ENV === 'development') {
    const delaySeconds = Math.ceil((timestampMs - Date.now()) / 1000);
    console.log(`🔒 [SWR Pause] All revalidations paused for ${delaySeconds}s`);
  }
};

/**
 * Vérifie si SWR est actuellement en pause
 * @returns {boolean} true si en pause
 */
const isPausedNow = () => {
  const isPaused = Date.now() < __swrPauseUntil;
  
  // Debug log uniquement quand une requête est bloquée
  if (isPaused && process.env.NODE_ENV === 'development') {
    const remainingSeconds = Math.ceil((__swrPauseUntil - Date.now()) / 1000);
    console.debug(`⏸️  [SWR Pause Active] ${remainingSeconds}s remaining`);
  }
  
  return isPaused;
};

// ==============================|| RETRY LOGIC HELPER ||============================== //

/**
 * Détermine si une erreur doit être retry
 * @param {Error} error - L'erreur capturée
 * @returns {boolean} true si on doit retry
 */
const shouldRetryRequest = (error) => {
  // Pas d'erreur = pas de retry
  if (!error) return false;
  
  // Extraire le status code
  const status = error.response?.status || error.status || 0;
  
  // RÈGLES DE RETRY :
  // ✅ Retry sur erreurs réseau (pas de response)
  if (!error.response && error.message?.includes('Network')) {
    return true;
  }
  
  // ✅ Retry sur erreurs serveur (5xx)
  if (status >= 500 && status < 600) {
    return true;
  }

  // Rate limiting (429) → retry (will use Retry-After)
  if (status === 408 || status === 429) return true;
  
  // ❌ NE PAS retry sur erreurs client (4xx)
  if (status >= 400 && status < 500) {
    return false;
  }
  
  // ❌ NE PAS retry si explicitement marqué
  if (error.doNotRetry) {
    return false;
  }
  
  // Par défaut, pas de retry
  return false;
};


// /**
//  * Smart retry delay with Retry-After support
//  * 
//  * Priority:
//  * 1. Use server's Retry-After if present (429 responses)
//  * 2. Fall back to exponential backoff for other retryable errors
//  * 
//  * @param {Error} error - The error object
//  * @param {number} retryCount - Current retry attempt (0-indexed)
//  * @returns {number} Delay in milliseconds before next retry
//  */
// const getRetryDelay = (error, retryCount) => {
//   console.log('🔍 [getRetryDelay] Called!', {
//     hasError: !!error,
//     retryAfterMs: error?.retryAfterMs,
//     type: typeof error?.retryAfterMs,
//     keys: error ? Object.keys(error).filter(k => k !== 'stack') : []
//   });

//   // Check if server provided Retry-After (from axios interceptor)
//   if (error?.retryAfterMs && error.retryAfterMs > 0) {
//     if (process.env.NODE_ENV === 'development') {
//       console.log(
//         `🔄 [SWR Retry] Using server Retry-After: ${(error.retryAfterMs / 1000).toFixed(1)}s`
//       );
//     }
//     return error.retryAfterMs;
//   }
  
//   // ✅ Fallback: Exponential backoff for other errors
//   // Formula: 1s * (2 ^ retryCount) with max 30s
//   // retryCount 0 → 1s, 1 → 2s, 2 → 4s, 3 → 8s, etc.
//   const baseDelay = 1000;
//   const exponentialDelay = baseDelay * Math.pow(2, retryCount);
//   const cappedDelay = Math.min(exponentialDelay, 30000); // Max 30s
  
//   if (process.env.NODE_ENV === 'development') {
//     console.log(
//       `🔄 [SWR Retry] Exponential backoff: ${(cappedDelay / 1000).toFixed(1)}s (attempt ${retryCount + 1})`
//     );
//   }
  
//   return cappedDelay;
// };


// ==============================|| SWR CONFIG WITH MONITORING ||============================== //

/**
 * Configuration globale SWR enrichie
 * - Monitoring des latences
 * - Retry intelligent (réseau/5xx seulement)
 * - ✅ PHASE 1: Retry-After support for 429 responses
 * - Télémétrie enrichie
 */
const swrGlobalConfig = {
  // Fetcher par défaut pour tous les hooks
  fetcher: swrFetcher,
  
  // === OPTIONS DE CACHE ===
  dedupingInterval: 2000,        // Évite les requêtes dupliquées pendant 2s
  keepPreviousData: true,         // Garde les données précédentes pendant le rechargement
  
  // === OPTIONS DE REVALIDATION ===
  revalidateIfStale: false,       // Pas de revalidation automatique si données périmées
  revalidateOnFocus: false,       // Pas de revalidation au focus de la fenêtre
  revalidateOnReconnect: true,    // ✅ CHANGÉ: Revalidation à la reconnexion réseau

  // Fige TOUTES les revalidations (auto + manuelles) pendant un cooldown 429
  isPaused: isPausedNow,
  
  // // === GESTION D'ERREURS INTELLIGENTE ===
  // shouldRetryOnError: shouldRetryRequest,  // ✅ Retry intelligent
  // errorRetryCount: 3,                      // ✅ Max 3 retry (au lieu de 1)

  // // ✅ Respecte Retry-After si présent, sinon backoff exponentiel (cap 30s)
  // onErrorRetry: (error, key, config, revalidate, { retryCount }) => {
  //   // 1) Si non-retryable → stop
  //   if (!shouldRetryRequest(error)) return;

  //   // 2) Respecter la limite globale de tentatives
  //   const max = config.errorRetryCount ?? 0;
  //   if (retryCount >= max) return;

  //   // 3) Délai côté serveur (429) transmis par axios/swrFetcher: error.retryAfterMs
  //   const serverDelay =
  //     typeof error?.retryAfterMs === 'number' && error.retryAfterMs > 0
  //       ? error.retryAfterMs
  //       : null;

  //   // 4) Sinon backoff exponentiel
  //   const base = 1000;
  //   const expo = Math.min(base * Math.pow(2, retryCount), 30000);
  //   const delay = serverDelay ?? expo;

  //   if (process.env.NODE_ENV === 'development') {
  //     // Log utile pour valider le comportement
  //     const endpoint = Array.isArray(key) ? key[0] : key;
  //     console.log('🔄 [SWR Retry]', {
  //       endpoint,
  //       retryCount,
  //       hasRetryAfter: !!serverDelay,
  //       delayMs: delay
  //     });
  //   }

  //   // 5) Planifie la revalidation (SWR gère retryCount automatiquement)
  //   setTimeout(() => revalidate({ retryCount }), delay);
  // },

  // === GESTION D'ERREURS INTELLIGENTE ===
  
  /**
   * 
   * Remplace errorRetryInterval pour un contrôle fin du timing.
   * Gère spécifiquement les 429 avec Retry-After.
   * 
   * @param {Error} error - Erreur capturée
   * @param {string} key - Clé SWR (URL)
   * @param {Object} config - Config SWR
   * @param {Function} revalidate - Fonction pour déclencher un retry
   * @param {Object} opts - Options { retryCount }
   */
  onErrorRetry: (error, key, config, revalidate, { retryCount }) => {
    // Extraire le status code
    const status = error?.response?.status || error?.status || 0;
    
    // ❌ Pas de retry sur 4xx (SAUF 429)
    if (status >= 400 && status < 500 && status !== 429) {
      if (process.env.NODE_ENV === 'development') {
        const endpoint = Array.isArray(key) ? key[0] : key;
        console.debug(`🚫 [SWR No Retry] ${status} on ${endpoint} (client error)`);
      }
      return; // Arrêt définitif
    }
    
    // ✅ CAS SPÉCIAL : 429 avec Retry-After
    if (status === 429 && error?.retryAfterMs) {
      const delayMs = error.retryAfterMs;
      
      if (process.env.NODE_ENV === 'development') {
        const endpoint = Array.isArray(key) ? key[0] : key;
        console.warn(`⏳ [SWR 429] ${endpoint} → Retry in ${Math.ceil(delayMs / 1000)}s`);
      }
      
      // ✅ Activer la pause globale
      setPauseUntil(Date.now() + delayMs);
      
      // ✅ Programmer le retry après le délai
      setTimeout(() => {
        if (process.env.NODE_ENV === 'development') {
          console.log(`🔄 [SWR Retry] Resuming after 429 cooldown`);
        }
        revalidate({ retryCount });
      }, delayMs);
      
      return; // Le retry est programmé
    }
    
    // ✅ FALLBACK : Exponential backoff (5xx, erreurs réseau, 429 sans Retry-After)
    const baseDelay = 1000;
    const maxDelay = 30000;
    const delay = Math.min(baseDelay * Math.pow(2, retryCount), maxDelay);
    const jitter = delay * 0.1 * Math.random();
    const finalDelay = delay + jitter;
    
    if (process.env.NODE_ENV === 'development') {
      const endpoint = Array.isArray(key) ? key[0] : key;
      console.debug(
        `🔄 [SWR Retry] ${endpoint} → Attempt ${retryCount + 1} in ${Math.ceil(finalDelay / 1000)}s`
      );
    }
    
    setTimeout(() => revalidate({ retryCount }), finalDelay);
  },
  
  /**
   * Détermine si une erreur est éligible au retry
   * Utilisé par SWR pour décider si onErrorRetry doit être appelé
   */
  shouldRetryOnError: (error) => {
    const status = error?.response?.status || error?.status || 0;
    
    // ✅ 429 est toujours retryable (géré par onErrorRetry)
    if (status === 429) return true;
    
    // ❌ Autres 4xx ne sont PAS retryables
    if (status >= 400 && status < 500) return false;
    
    // ✅ 5xx et erreurs réseau sont retryables
    return true;
  },
  
  errorRetryCount: 3, // Max 3 tentatives
  
  // === CALLBACKS ENRICHIS AVEC MONITORING ===
  
  /**
   * Callback global sur erreur
   * Enrichi avec contexte et monitoring
   */
  onError: (error, key, config) => {
    // Extraire le contexte
    const endpoint = Array.isArray(key) ? key[0] : key;
    const status = error?.response?.status || error?.status || 0;
    const isRetryable = shouldRetryRequest(error);
    
    // Contexte enrichi pour les logs
    const errorContext = {
      key: endpoint,
      status,
      message: error?.message || 'Unknown error',
      retryable: isRetryable,
      hasRetryAfter: !!error?.retryAfterMs,
      timestamp: new Date().toISOString()
    };
    
    // Log structuré en dev
    if (process.env.NODE_ENV === 'development') {
      const emoji = isRetryable ? '🔄' : '🚫';
      console.error(`${emoji} [SWR Error]`, errorContext);
    }
    
    // Envoyer une notification si erreur critique (optionnel)
    if (status === 401 || status === 403) {
      // Token expiré ou permissions insuffisantes
      // Le auth interceptor devrait déjà gérer ça
      console.warn('[SWR] Auth error detected:', status);
    }
    
    if (status === 429 && error?.retryAfterMs) {
      const now = Date.now();
      
      // Dedup temporel : Max 1 toast / 5s
      if (now - __lastToastTime > TOAST_DEDUP_MS) {
        __lastToastTime = now;
        
        const seconds = Math.ceil(error.retryAfterMs / 1000);
        
        // Toast avec clé unique pour éviter empilement
        openSnackbar({
          key: TOAST_KEY_429,  // Notistack utilisera cette clé pour dedup
          open: true,
          message: `Rate limit reached. please wait ~${seconds}s`,
          anchorOrigin: { vertical: 'top', horizontal: 'right' },
          variant: 'alert',
          alert: { color: 'warning' },
          close: true,  // Bouton de fermeture
          autoHideDuration: error.retryAfterMs  // Disparaît après le délai
        });
        
        if (process.env.NODE_ENV === 'development') {
          console.log(`🔔 [Toast 429] User notified: retry in ${seconds}s`);
        }
      } else {
        if (process.env.NODE_ENV === 'development') {
          console.debug(`🔕 [Toast 429] Skipped (dedup): last toast ${Math.ceil((now - __lastToastTime) / 1000)}s ago`);
        }
      }
    }
  },
  
  
  /**
   * Callback global sur succès
   * Pour monitoring et debug
   */
  onSuccess: (data, key, config) => {
    // Log minimal en mode debug uniquement
    if (process.env.NODE_ENV === 'development' && process.env.NEXT_PUBLIC_DEBUG_SWR === 'true') {
      const endpoint = Array.isArray(key) ? key[0] : key;
      const hasData = !!data;
      const dataSize = data ? JSON.stringify(data).length : 0;
      
      console.debug('[SWR Success]', {
        endpoint,
        hasData,
        dataSize: `${(dataSize / 1024).toFixed(1)}KB`,
        cached: config.isValidating && hasData 
      });
    }
  },
  
  /**
   * Callback lors du chargement (optionnel)
   * Utile pour tracking des métriques de cache hit/miss
   */
  onLoadingSlow: (key, config) => {
    // Déclenché si le loading prend trop de temps
    if (process.env.NODE_ENV === 'development') {
      const endpoint = Array.isArray(key) ? key[0] : key;
      console.warn('⏳ [SWR Slow Loading]', {
        endpoint,
        threshold: config.loadingTimeout || 3000
      });
    }
  },
  
  // === OPTIONS DE PERFORMANCE ===
  loadingTimeout: 3000,           // Déclenche onLoadingSlow après 3s
  suspense: false,                // Pas de suspense par défaut
  
};

// ==============================|| MONITORING DASHBOARD (DEV) ||============================== //

/**
 * Hook de debug pour afficher les métriques en dev
 * À utiliser dans un composant de dev tools
 */
export const useMonitoringDashboard = () => {
  if (process.env.NODE_ENV !== 'development') {
    return null;
  }
  
  return {
    getStats: () => metricsCollector.getSummary(),
    reset: () => metricsCollector.reset(),
    export: () => metricsCollector.export()
  };
};

// ==============================|| APP - THEME, ROUTER, LOCAL ||============================== //

export default function ProviderWrapper({ children }) {
  // En dev, log le démarrage du monitoring
  if (process.env.NODE_ENV === 'development') {
    console.log('🚀 SWR Provider initialized with Retry-After support and smart retry');
  }
  
  return (
    <ConfigProvider>
      <ThemeCustomization>
        <AuthProvider>
          <SWRConfig value={swrGlobalConfig}>
            <RTLLayout>
              <Locales>
                <ScrollTop>
                  <Notistack>
                    <Snackbar />
                    {children}
                  </Notistack>
                </ScrollTop>
              </Locales>
            </RTLLayout>
          </SWRConfig>
        </AuthProvider>
      </ThemeCustomization>
    </ConfigProvider>
  );
}

ProviderWrapper.propTypes = { children: PropTypes.node };