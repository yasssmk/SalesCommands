// frontend/src/api/_swr.js

import { mutate } from 'swr';

// ==============================|| SWR HELPERS MULTI-TENANT ||============================== //

/**
 * ✅ GÉNÈRE UNE CLÉ SWR AVEC TENANT ID
 * 
 * Garantit l'isolation multi-tenant en incluant toujours le tenantId dans la clé.
 * Format standardisé : [url, tenantId]
 * 
 * @param {string} url - URL de l'endpoint API
 * @param {string|null} tenantId - ID du tenant courant
 * @returns {Array|null} Clé SWR tuple ou null si pas de tenantId
 */
export const tenantKey = (url, tenantId) => {
  if (!tenantId || !url) {
    return null; // SWR ne fera pas de requête
  }
  
  return [url, tenantId];
};

/**
 * ✅ MATCHER POUR REVALIDATIONS CIBLÉES
 * 
 * Matche à la fois les tuples [url, tenantId] et les strings simples.
 * Utilisé dans mutate() pour revalider toutes les clés qui commencent par le prefix.
 * 
 * @param {string} prefix - Prefix URL à matcher
 * @returns {Function} Fonction matcher pour SWR mutate()
 */
export const matchKey = (prefix) => {
  return (key) => {
    // Matcher les tuples [url, tenantId]
    if (Array.isArray(key) && key.length >= 1) {
      const url = key[0];
      return typeof url === 'string' && url.startsWith(prefix);
    }
    
    // Matcher les strings simples (legacy)
    if (typeof key === 'string') {
      return key.startsWith(prefix);
    }
    
    return false;
  };
};

/**
 * ✅ REVALIDATION CIBLÉE AVEC SUPPORT TUPLES + STRINGS
 * 
 * Revalide toutes les clés SWR qui commencent par le prefix donné,
 * que ce soient des tuples ou des strings.
 * 
 * @param {string} urlPrefix - Prefix URL à revalider
 * @param {Object} options - Options pour mutate()
 */
export const revalidateByPrefix = (urlPrefix, options = {}) => {
  return mutate(
    matchKey(urlPrefix),
    undefined,
    { revalidate: true, ...options }
  );
};

/**
 * ✅ REVALIDATION CIBLÉE MULTIPLE
 * 
 * Revalide plusieurs prefixes en une seule opération.
 * Utile après une mutation qui impacte plusieurs types de données.
 * 
 * @param {string[]} prefixes - Liste des prefixes à revalider
 * @param {Object} options - Options pour mutate()
 */
export const revalidateMultiple = (prefixes, options = {}) => {
  prefixes.forEach(prefix => {
    revalidateByPrefix(prefix, options);
  });
};

// ==============================|| EXEMPLES D'USAGE ||============================== //

/**
 * EXEMPLES D'UTILISATION :
 * 
 * // Dans un hook
 * const swrKey = tenantKey('/client/users/', tenantId);
 * const { data } = useSWR(swrKey, fetcher);
 * 
 * // Après une mutation
 * revalidateByPrefix('/client/users/');
 * 
 * // Revalidation multiple
 * revalidateMultiple([
 *   '/client/users/',
 *   '/client/client-accounts/'
 * ]);
 * 
 * // Matcher custom
 * mutate(matchKey('/client/users/'), undefined, { revalidate: true });
 */