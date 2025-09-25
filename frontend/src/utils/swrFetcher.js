/**
 * SWR Global Fetcher
 * 
 * Fetcher centralisé pour tous les hooks SWR de l'application.
 * Compatible avec les clés simples (string) et tuples [url, tenantId].
 * 
 * @module utils/swrFetcher
 */

import { api } from 'utils/axiosClient';

/**
 * Fetcher global pour SWR - méthode GET
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
  
  // Cas 1: Un seul argument
  if (args.length === 1) {
    const key = args[0];
    
    // Si c'est une string qui commence par @, c'est une clé sérialisée par SWR
    if (typeof key === 'string' && key.startsWith('@')) {
      // SWR a stringifié notre tuple, on ne peut pas l'utiliser directement
      // Ce cas ne devrait pas arriver avec notre setup, mais on le gère
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
  
  // Validation de l'URL
  if (!url || typeof url !== 'string') {
    console.error('[SWR Fetcher] Invalid key structure:', args);
    throw new Error(`Invalid SWR key: URL must be a string, got ${typeof url}`);
  }

  // Log en mode debug
  if (process.env.NODE_ENV === 'development') {
    console.debug('[SWR Fetcher] Processing:', {
      url,
      keyInfo,
      argsLength: args.length
    });
  }

  try {
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
    
  } catch (error) {
    // Log des erreurs en développement
    if (process.env.NODE_ENV === 'development') {
      console.error('[SWR Fetcher] Error:', {
        url,
        error: error.message,
        status: error.response?.status,
        originalArgs: args
      });
    }

    // Re-throw l'erreur pour que SWR puisse :
    // - Utiliser onError si configuré
    // - Appliquer shouldRetryOnError selon la config
    // - Afficher l'erreur dans le composant via error state
    throw error;
  }
};

/**
 * Fetcher pour requêtes POST (utilisé par useSWRMutation)
 * 
 * @param {string | [string, string]} keyOrTuple - URL string ou tuple [url, tenantId]
 * @param {Object} options - Options de la mutation
 * @param {any} options.arg - Données à envoyer en POST
 * @returns {Promise<any>} - Données de réponse
 * 
 * @example
 * const { trigger } = useSWRMutation(
 *   ['/client/users/', tenantId],
 *   swrPostFetcher
 * );
 * trigger({ name: 'John', email: 'john@example.com' });
 */
export const swrPostFetcher = async (keyOrTuple, { arg }) => {
  const url = Array.isArray(keyOrTuple) ? keyOrTuple[0] : keyOrTuple;
  
  if (!url || typeof url !== 'string') {
    throw new Error('Invalid SWR key: URL must be a string');
  }

  try {
    const result = await api.post(url, arg);
    
    if (result.success) {
      return result.data;
    }
    
    throw new Error(result.error || 'Failed to post data');
    
  } catch (error) {
    if (process.env.NODE_ENV === 'development') {
      console.error('[SWR PostFetcher] Error:', {
        url,
        error: error.message,
        payload: arg
      });
    }
    throw error;
  }
};

/**
 * Fetcher pour requêtes PUT/PATCH (utilisé par useSWRMutation)
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

  try {
    const result = method === 'PUT' 
      ? await api.put(url, arg)
      : await api.patch(url, arg);
    
    if (result.success) {
      return result.data;
    }
    
    throw new Error(result.error || `Failed to ${method} data`);
    
  } catch (error) {
    if (process.env.NODE_ENV === 'development') {
      console.error(`[SWR ${method}Fetcher] Error:`, {
        url,
        error: error.message,
        payload: arg
      });
    }
    throw error;
  }
};

/**
 * Fetcher pour requêtes DELETE (utilisé par useSWRMutation)
 * 
 * @param {string | [string, string]} keyOrTuple - URL string ou tuple [url, tenantId]
 * @returns {Promise<any>} - Confirmation de suppression
 */
export const swrDeleteFetcher = async (keyOrTuple) => {
  const url = Array.isArray(keyOrTuple) ? keyOrTuple[0] : keyOrTuple;
  
  if (!url || typeof url !== 'string') {
    throw new Error('Invalid SWR key: URL must be a string');
  }

  try {
    const result = await api.delete(url);
    
    if (result.success) {
      return result.data || { success: true };
    }
    
    throw new Error(result.error || 'Failed to delete');
    
  } catch (error) {
    if (process.env.NODE_ENV === 'development') {
      console.error('[SWR DeleteFetcher] Error:', {
        url,
        error: error.message
      });
    }
    throw error;
  }
};

// Export par défaut du fetcher GET (le plus utilisé)
export default swrFetcher;