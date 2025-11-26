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
import { isRetryableError } from 'utils/retryLogic';
import { ConfigProvider } from '../contexts/ConfigContext';
import { AuthProvider } from '../hooks/useAuth';

import { displayErrorSnackbar } from '../utils/displayError';

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
// let __lastToastTime = 0;  // ✅  Dedup temporel des toasts
// const TOAST_DEDUP_MS = 5000;  // Max 1 toast / 5s
// const TOAST_KEY_429 = 'rate-limit-429';  // Clé unique Notistack

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
  return isRetryableError(error);
};



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
  revalidateIfStale: true,        // ✅ Revalide automatiquement si données périmées
  revalidateOnFocus: true,        // ✅ Revalide quand l'utilisateur revient sur l'onglet
  revalidateOnReconnect: true,    // ✅ Revalide après perte de connexion réseau

  // Fige TOUTES les revalidations (auto + manuelles) pendant un cooldown 429
  isPaused: isPausedNow,
  
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
  return isRetryableError(error);
},
  
  errorRetryCount: 2, // Max 2 tentatives
  
  // === CALLBACKS ENRICHIS AVEC MONITORING ===
  
  /**
 * Callback global sur erreur
 * Enrichi avec contexte et monitoring
 * 
 * ✅ PHASE 3: Uses unified error bridge for standardized display
 */
onError: (error, key, config) => {
  // Extraire le contexte
  const endpoint = Array.isArray(key) ? key[0] : key;
  const status = error?.response?.status || error?.status || 0;
  const isRetryable = isRetryableError(error);
  
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
  
  // Auth errors: just log (auth interceptor handles these)
  if (status === 401 || status === 403) {
    if (process.env.NODE_ENV === 'development') {
      console.warn('[SWR] Auth error detected:', status);
    }
    return;
  }
  
  // ✅ Rate limit handling (429)
  if (status === 429 && error?.retryAfterMs) {
    const now = Date.now();
    
    // Display standardized error notification
    // Deduplication is handled automatically by displayErrorSnackbar
    displayErrorSnackbar(error);
    
    // ⚠️ CRITICAL BUSINESS LOGIC: Pause ALL SWR revalidations
    setPauseUntil(now + error.retryAfterMs);
    
    // Dev logging for debugging
    if (process.env.NODE_ENV === 'development') {
      const seconds = Math.ceil(error.retryAfterMs / 1000);
      console.log(`🔔 [429 Rate Limit] User notified, SWR paused for ${seconds}s`);
    }
  }
  
  // Note: Other errors (5xx, network, etc.) are NOT displayed as snackbars here
  // They're shown contextually by individual components when needed
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