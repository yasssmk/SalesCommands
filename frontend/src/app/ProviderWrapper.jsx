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
  
  // ✅ Retry sur timeout (408) ou Too Many Requests (429)
  if (status === 408 || status === 429) {
    return true;
  }
  
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

/**
 * Calcule le délai avant le prochain retry (exponential backoff)
 * @param {number} retryCount - Nombre de tentatives déjà effectuées
 * @returns {number} Délai en ms
 */
const getRetryDelay = (retryCount) => {
  // Exponential backoff avec jitter : 1s, 2s, 4s, 8s...
  const baseDelay = 1000;
  const maxDelay = 30000; // Max 30 secondes
  
  const delay = Math.min(baseDelay * Math.pow(2, retryCount), maxDelay);
  const jitter = delay * 0.1 * Math.random(); // 10% de jitter
  
  return delay + jitter;
};

// ==============================|| SWR CONFIG WITH MONITORING ||============================== //

/**
 * Configuration globale SWR enrichie
 * - Monitoring des latences
 * - Retry intelligent (réseau/5xx seulement)
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
  
  // === GESTION D'ERREURS INTELLIGENTE ===
  shouldRetryOnError: shouldRetryRequest,  // ✅ Retry intelligent
  errorRetryInterval: getRetryDelay,       // ✅ Backoff exponentiel
  errorRetryCount: 3,                      // ✅ Max 3 retry (au lieu de 1)
  
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
    
    // Note: Le monitoring des latences est déjà fait dans le fetcher
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
        cached: config.isValidating && hasData // Probablement du cache si on revalide avec données
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
  
  // === COMPARAISON CUSTOM (SI NÉCESSAIRE) ===
  // compare: (a, b) => a === b   // Comparaison par défaut
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
    console.log('🚀 SWR Provider initialized with monitoring and smart retry');
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