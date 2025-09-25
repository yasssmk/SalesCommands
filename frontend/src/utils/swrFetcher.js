/**
 * SWR Global Fetcher avec Monitoring
 * 
 * Fetcher centralisé pour tous les hooks SWR de l'application
 * avec monitoring des latences par endpoint.
 * 
 * @module utils/swrFetcher
 */

import { api } from 'utils/axiosClient';
import metricsCollector from 'utils/monitoring';

// ==============================|| PERFORMANCE HELPERS ||============================== //

/**
 * Wrapper pour mesurer la performance d'une requête
 * @param {Function} asyncFn - Fonction async à mesurer
 * @param {string} endpoint - URL de l'endpoint
 * @returns {Promise} Résultat avec monitoring
 */
const withPerformanceTracking = async (asyncFn, endpoint) => {
  const startTime = performance.now();
  let success = true;
  let statusCode = null;
  let error = null;
  
  try {
    const result = await asyncFn();
    
    // Extraire le status code si disponible
    statusCode = result?.__meta?.status || 200;
    
    return result;
  } catch (err) {
    success = false;
    error = err;
    statusCode = err.response?.status || 0;
    throw err;
  } finally {
    const duration = performance.now() - startTime;
    
    // Enregistrer la métrique
    if (success) {
      metricsCollector.recordEndpointLatency(endpoint, duration, {
        success: true,
        statusCode,
        cached: false
      });
    } else {
      metricsCollector.recordEndpointError(endpoint, error, {
        duration,
        statusCode
      });
    }
    
    // === LOGS AMÉLIORÉS AVEC COULEURS ET EMOJIS ===
    if (process.env.NODE_ENV === 'development') {
      // Nettoyer l'endpoint pour l'affichage
      const cleanUrl = endpoint
        .replace(/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/gi, '{uuid}')
        .replace(/\/\d+\//g, '/{id}/')
        .replace(/\/\d+$/g, '/{id}');
      
      // Déterminer la couleur selon la latence
      let style = '';
      let emoji = '';
      
      if (!success) {
        emoji = '❌';
        style = 'color: #ff4444; font-weight: bold';
      } else if (duration < 200) {
        emoji = '⚡';
        style = 'color: #00cc00; font-weight: normal';
      } else if (duration < 500) {
        emoji = '✅';
        style = 'color: #88cc00; font-weight: normal';
      } else if (duration < 1000) {
        emoji = '⚠️';
        style = 'color: #ff9900; font-weight: bold';
      } else {
        emoji = '🐌';
        style = 'color: #ff4444; font-weight: bold';
      }
      
      // Format du message
      const method = success ? 'GET' : 'ERR';
      const time = duration < 1000 
        ? `${duration.toFixed(0)}ms` 
        : `${(duration/1000).toFixed(2)}s`;
      
      // Log avec style
      console.log(
        `%c${emoji} [${method}] ${cleanUrl} → ${time} (${statusCode || '?'})`,
        style
      );
      
      // Si requête très lente, log supplémentaire
      if (duration > 2000 && success) {
        console.warn(
          `%c⏰ VERY SLOW REQUEST: ${cleanUrl} took ${(duration/1000).toFixed(2)} seconds!`,
          'color: #ff0000; font-size: 12px; font-weight: bold; background: #ffeeee; padding: 2px 6px; border-radius: 3px'
        );
      }
      
      // Si erreur, log détaillé
      if (!success && error) {
        console.group(`%c❌ Error Details for ${cleanUrl}`, 'color: #cc0000');
        console.error('Status:', statusCode);
        console.error('Message:', error.message);
        if (error.response?.data) {
          console.error('Response:', error.response.data);
        }
        console.groupEnd();
      }
    }
  }
};

// ==============================|| MAIN FETCHER ||============================== //

/**
 * Fetcher global pour SWR avec monitoring - méthode GET
 * 
 * IMPORTANT: SWR peut passer soit :
 * 1. La clé originale (string ou array)
 * 2. Une version stringifiée pour les clés complexes (commence par @)
 * 3. Les éléments du tuple comme arguments séparés
 * 
 * @param {...any} args - Arguments passés par SWR
 * @returns {Promise<any>} - Données de l'API
 * @throws {Error} - Erreur si la requête échoue
 */
const swrFetcher = async (...args) => {
  let url;
  let keyInfo = { raw: args };
  
  // === PARSING DE LA CLÉ SWR ===
  
  // Cas 1: Un seul argument
  if (args.length === 1) {
    const key = args[0];
    
    // Si c'est une string qui commence par @, c'est une clé sérialisée par SWR
    if (typeof key === 'string' && key.startsWith('@')) {
      // SWR a stringifié notre tuple, on ne peut pas l'utiliser directement
      console.error('[SWR Fetcher] Received serialized key:', key);
      throw new Error('Fetcher received serialized key - check SWR configuration');
    }
    // Si c'est un tableau [url, tenantId]
    else if (Array.isArray(key)) {
      url = key[0];
      keyInfo.type = 'tuple';
      keyInfo.tenantId = key[1];
    }
    // Si c'est une string simple
    else if (typeof key === 'string') {
      url = key;
      keyInfo.type = 'string';
    }
  }
  // Cas 2: Plusieurs arguments (SWR a décomposé le tuple)
  else if (args.length >= 2) {
    // Premier argument est l'URL
    url = args[0];
    keyInfo.type = 'spread';
    keyInfo.tenantId = args[1];
  }
  
  // === VALIDATION ===
  
  if (!url || typeof url !== 'string') {
    console.error('[SWR Fetcher] Invalid key structure:', args);
    throw new Error(`Invalid SWR key: URL must be a string, got ${typeof url}`);
  }

  // === LOG DE DEBUG (OPTIONNEL - peut être supprimé) ===
  if (process.env.NODE_ENV === 'development' && process.env.NEXT_PUBLIC_DEBUG_SWR === 'true') {
    console.debug('[SWR Fetcher] Processing:', {
      url,
      keyInfo,
      argsLength: args.length
    });
  }

  // === FETCH AVEC MONITORING ===
  
  try {
    const data = await withPerformanceTracking(
      async () => {
        // Utilisation du wrapper api qui gère déjà :
        // - Les cookies HTTP-only pour l'authentification JWT
        // - Les headers tenant (X-Client-ID, etc.)
        // - La gestion d'erreurs standardisée
        // - Les interceptors axios pour refresh token
        const result = await api.get(url);
        
        // Le wrapper api retourne {success, data, error}
        if (result.success) {
          return result.data;
        }
        
        // Si pas de succès, lancer l'erreur pour que SWR la gère
        throw new Error(result.error || 'Failed to fetch data');
      },
      url // Pass URL for monitoring
    );
    
    return data;
    
  } catch (error) {
    // Re-throw l'erreur pour que SWR puisse :
    // - Utiliser onError si configuré
    // - Appliquer shouldRetryOnError selon la config
    // - Afficher l'erreur dans le composant via error state
    throw error;
  }
};

// ==============================|| MUTATION FETCHERS AVEC MONITORING ||============================== //

/**
 * Fetcher pour requêtes POST avec monitoring
 * 
 * @param {string | [string, string]} keyOrTuple - URL string ou tuple [url, tenantId]
 * @param {Object} options - Options de la mutation
 * @param {any} options.arg - Données à envoyer en POST
 * @returns {Promise<any>} - Données de réponse
 */
export const swrPostFetcher = async (keyOrTuple, { arg }) => {
  const url = Array.isArray(keyOrTuple) ? keyOrTuple[0] : keyOrTuple;
  
  if (!url || typeof url !== 'string') {
    throw new Error('Invalid SWR key: URL must be a string');
  }

  return withPerformanceTracking(
    async () => {
      const result = await api.post(url, arg);
      
      if (result.success) {
        return result.data;
      }
      
      throw new Error(result.error || 'Failed to post data');
    },
    url
  );
};

/**
 * Fetcher pour requêtes PUT/PATCH avec monitoring
 * 
 * @param {string | [string, string]} keyOrTuple - URL string ou tuple [url, tenantId]
 * @param {Object} options - Options de la mutation
 * @param {any} options.arg - Données à envoyer
 * @param {string} options.method - Méthode HTTP (PUT ou PATCH)
 * @returns {Promise<any>} - Données de réponse
 */
export const swrMutateFetcher = async (keyOrTuple, { arg, method = 'PATCH' }) => {
  const url = Array.isArray(keyOrTuple) ? keyOrTuple[0] : keyOrTuple;
  
  if (!url || typeof url !== 'string') {
    throw new Error('Invalid SWR key: URL must be a string');
  }

  return withPerformanceTracking(
    async () => {
      const result = method === 'PUT' 
        ? await api.put(url, arg)
        : await api.patch(url, arg);
      
      if (result.success) {
        return result.data;
      }
      
      throw new Error(result.error || `Failed to ${method} data`);
    },
    url
  );
};

/**
 * Fetcher pour requêtes DELETE avec monitoring
 * 
 * @param {string | [string, string]} keyOrTuple - URL string ou tuple [url, tenantId]
 * @returns {Promise<any>} - Confirmation de suppression
 */
export const swrDeleteFetcher = async (keyOrTuple) => {
  const url = Array.isArray(keyOrTuple) ? keyOrTuple[0] : keyOrTuple;
  
  if (!url || typeof url !== 'string') {
    throw new Error('Invalid SWR key: URL must be a string');
  }

  return withPerformanceTracking(
    async () => {
      const result = await api.delete(url);
      
      if (result.success) {
        return result.data || { success: true };
      }
      
      throw new Error(result.error || 'Failed to delete');
    },
    url
  );
};

// ==============================|| CACHE ANALYSIS HELPER ||============================== //

/**
 * Helper pour analyser le cache SWR (dev only)
 * @param {Function} useSWRConfig - Hook SWR config
 */
export const analyzeSWRCache = (useSWRConfig) => {
  if (process.env.NODE_ENV !== 'development') return;
  
  const { cache } = useSWRConfig();
  const cacheKeys = Array.from(cache.keys());
  
  console.group('📦 SWR Cache Analysis');
  console.log('Total cached keys:', cacheKeys.length);
  
  // Grouper par endpoint
  const byEndpoint = {};
  cacheKeys.forEach(key => {
    const clean = key.replace(/\?.*/, '').replace(/\/\d+/g, '/{id}');
    byEndpoint[clean] = (byEndpoint[clean] || 0) + 1;
  });
  
  console.table(byEndpoint);
  console.groupEnd();
  
  return { total: cacheKeys.length, byEndpoint };
};

// Export par défaut du fetcher GET (le plus utilisé)
export default swrFetcher;