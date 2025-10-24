// frontend/src/api/_swr.js

import { mutate } from 'swr';
import { pollOperationStatus } from 'utils/pollOperationStatus';

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

// ==============================|| POLLING PROGRESSIF APRÈS BULK TIMEOUT ||============================== //

/**
 * ✅ DÉCIDE SI ON DOIT UTILISER LE POLLING PROGRESSIF
 * 
 * Détermine automatiquement si une opération bulk nécessite un polling progressif
 * ou une revalidation immédiate, en fonction du type d'erreur/statut.
 * 
 * **Cas où le polling EST utile** :
 * - 408 Request Timeout : Backend continue à traiter après abandon client
 * - 504 Gateway Timeout : Backend peut encore traiter en arrière-plan
 * - 202 Accepted : Opération asynchrone confirmée (rare en bulk delete)
 * 
 * **Cas où le polling N'EST PAS utile** :
 * - 400/403/404/422 : Erreurs validation/permissions, rien n'a changé en DB
 * - 429 : Rate limit (déjà géré par système global de pause SWR)
 * - 2xx sauf 202 : Succès immédiat, pas besoin d'attendre
 * 
 * @param {Object} result - Résultat de l'API call
 * @param {boolean} result.isTimeout - Flag timeout côté client (axios)
 * @param {number} result.status - Status HTTP de la réponse
 * @param {boolean} result.success - Indique si l'opération a réussi
 * @returns {boolean} true si polling progressif recommandé, false sinon
 * 
 * @example
 * // Après un bulk delete
 * const result = await api.delete('/client/users/bulk-delete/', {...});
 * if (shouldUseProgressiveRefetch(result)) {
 *   await refetchAfterBulkTimeout([...]);
 * } else {
 *   revalidateMultiple([...]);
 * }
 */
export const shouldUseProgressiveRefetch = (result) => {
  if (!result) return false;

  // Cas 1 : Timeout client (le plus courant)
  // Backend continue à traiter même si le client a abandonné
  if (result.isTimeout === true) {
    console.log('[shouldUseProgressiveRefetch] Timeout detected → progressive refetch');
    return true;
  }

  // ✅ PHASE 1: Cas 2 : Bad Gateway (502)
  // Proxy error, backend peut encore traiter la requête
  if (result.status === 502) {
    console.log('[shouldUseProgressiveRefetch] 502 Bad Gateway → progressive refetch');
    return true;
  }

  // Cas 3 : Gateway timeout (504)
  // Proxy/Gateway a timeout mais backend continue probablement
  if (result.status === 504) {
    console.log('[shouldUseProgressiveRefetch] 504 Gateway Timeout → progressive refetch');
    return true;
  }

  // Cas 4 : Accepted (202)
  // Backend a accepté l'opération mais traite en async
  if (result.status === 202) {
    console.log('[shouldUseProgressiveRefetch] 202 Accepted → progressive refetch');
    return true;
  }

  // Cas 5 (optionnel) : 500 avec succès partiel
  // Décommenté si besoin : backend a échoué mais a traité une partie
  // if (result.status === 500 && result.data?.summary?.deleted > 0) {
  //   console.log('[shouldUseProgressiveRefetch] 500 with partial success → progressive refetch');
  //   return true;
  // }

  // Tous les autres cas : revalidation immédiate suffit
  console.log('[shouldUseProgressiveRefetch] Standard response → immediate refetch');
  return false;
  ;
}

/**
 * ✅ HELPER CENTRALISÉ - REVALIDATION INTELLIGENTE APRÈS BULK OPERATION
 * 
 * Gère automatiquement la stratégie de revalidation après une opération bulk :
 * - Polling progressif si timeout/504/202 (backend continue à traiter)
 * - Revalidation immédiate sinon (succès ou erreur standard)
 * 
 * **Problème résolu** :
 * - Client timeout 20s → refetch immédiat
 * - Backend continue à traiter → retourne données stales
 * - SWR cache ces données stales → UI affiche users supprimés
 * 
 * **Solution** :
 * - Détection automatique via shouldUseProgressiveRefetch()
 * - Polling progressif (5s × 3 tentatives) si nécessaire
 * - Revalidation immédiate sinon
 * 
 * **Usage standardisé** :
 * Utilisé dans TOUTES les fonctions bulk : delete, softDelete, update, create
 * Réutilisable pour users, accounts, teams, organizations, etc.
 * 
 * @param {Object} result - Résultat de l'API call (avec status, isTimeout, success, etc.)
 * @param {string[]} prefixes - Liste des prefixes à revalider (ex: ['/client/users/', '/client/client-accounts/'])
 * @param {Function} onSyncProgress - Optional callback pour notifier l'UI: (attempt, maxAttempts) => void
 * @param {Function} onSyncComplete - Optional callback appelé quand TOUT le polling est terminé: () => void
 * @returns {Promise<void>}
 * 
 * @example
 * // Dans TOUTES les fonctions bulk (delete, update, create, etc.)
 * export const bulkXxxUsers = async (params, mode, onSyncProgress = null, onSyncComplete = null) => {
 *   let result = null;
 *   try {
 *     result = await api.xxx(...);
 *     return result.data;
 *   } catch (err) {
 *     return { success: false, ... };
 *   } finally {
 *     await handleBulkRevalidation(
 *       result,
 *       [endpoints.users, '/client/client-accounts/'],
 *       onSyncProgress,  // Appelé à chaque tentative
 *       onSyncComplete   // Appelé une fois à la fin
 *     );
 *   }
 * };
 */
export const handleBulkRevalidation = async (result, prefixes, onSyncProgress = null, onSyncComplete = null) => {
  if (!Array.isArray(prefixes) || prefixes.length === 0) {
    console.error('[handleBulkRevalidation] Invalid prefixes:', prefixes);
    return;
  }

  // ==============================
  // CAS 202 ACCEPTED - POLLING D'ÉTAT BACKEND
  // ==============================
  
  if (result?.data?.__is202) {
    console.log('[handleBulkRevalidation] 202 Accepted detected → using pollOperationStatus');
    
    // Import dynamique pour éviter circular dependency
    const { default: pollOperationStatus, extractKeyFromPollUrl } = await import('utils/pollOperationStatus');
    
    // Extraire la clé d'idempotence (priorité : metadata > poll_url parsing)
    let idempotencyKey = result.data.__idempotency_key;
    
    if (!idempotencyKey && result.data.__poll_url) {
      idempotencyKey = extractKeyFromPollUrl(result.data.__poll_url);
      if (process.env.NODE_ENV === 'development') {
        console.log(`[handleBulkRevalidation] Extracted key from poll_url: ${idempotencyKey?.slice(0, 8)}...`);
      }
    }
    
    if (!idempotencyKey) {
      console.error('[handleBulkRevalidation] 202 response missing both __idempotency_key and __poll_url');
      // Fallback sur revalidation immédiate
      revalidateMultiple(prefixes);
      if (onSyncComplete) onSyncComplete();
      return;
    }
    
    // Appeler le helper de polling
    const pollResult = await pollOperationStatus(idempotencyKey, {
      initialRetryAfter: result.data.__retry_after_ms || 0,
      onProgress: onSyncProgress
    });
    
    // Traiter le résultat du polling
    if (pollResult.status === 'succeeded') {
      console.log('[handleBulkRevalidation] Operation succeeded → revalidating data');
      revalidateMultiple(prefixes);
    } else if (pollResult.status === 'failed') {
      console.error('[handleBulkRevalidation] Operation failed:', pollResult.error);
      // Même en cas d'échec, on revalide pour afficher l'état réel
      revalidateMultiple(prefixes);
    } else if (pollResult.status === 'still_running') {
      console.warn('[handleBulkRevalidation] Operation still running after max attempts');
      // Polling max atteint mais opération continue → revalider quand même
      // L'UI peut afficher un message "still processing"
      revalidateMultiple(prefixes);
    }
    
    // Callback de fin de polling
    if (onSyncComplete && typeof onSyncComplete === 'function') {
      try {
        onSyncComplete();
      } catch (err) {
        console.error('[handleBulkRevalidation] onComplete callback error:', err);
      }
    }
    
    // Retour immédiat : le cas 202 est géré
    return;
  }

  // Décision intelligente basée sur le type d'erreur/statut
  if (shouldUseProgressiveRefetch(result)) {
    // Backend continue à traiter → Polling progressif
    console.log('[handleBulkRevalidation] Using progressive refetch strategy');
    
    await refetchAfterBulkTimeout(prefixes, {
      maxAttempts: 3,
      delay: 5000,
      onProgress: onSyncProgress,
      onComplete: onSyncComplete  // ⭐ NOUVEAU: Callback de fin de polling
    });
  } else {
    // Opération terminée → Revalidation immédiate
    console.log('[handleBulkRevalidation] Using immediate revalidation strategy');
    revalidateMultiple(prefixes);
    
    // ⭐ NOUVEAU: Appeler onComplete même en mode immédiat
    if (onSyncComplete && typeof onSyncComplete === 'function') {
      try {
        onSyncComplete();
      } catch (err) {
        console.error('[handleBulkRevalidation] onComplete callback error:', err);
      }
    }
  }
};

/**
 * ✅ POLLING PROGRESSIF APRÈS BULK TIMEOUT
 * 
 * Refetch progressif après une opération bulk qui a timeout côté client,
 * pour laisser le temps au backend de finir le traitement.
 * 
 * ⚠️ NOTE : Utilisez handleBulkRevalidation() au lieu d'appeler cette fonction directement.
 * Cette fonction est appelée automatiquement par handleBulkRevalidation() si nécessaire.
 * 
 * @param {string[]} prefixes - Liste des prefixes à revalider (ex: ['/client/users/', '/client/client-accounts/'])
 * @param {Object} options - Options de configuration
 * @param {number} options.maxAttempts - Nombre de tentatives max (défaut: 3)
 * @param {number} options.delay - Délai entre chaque tentative en ms (défaut: 5000)
 * @param {Function} options.onProgress - Callback appelé à chaque tentative: (attempt, maxAttempts) => void
 * @param {Function} options.onComplete - Callback appelé à la fin du polling: () => void
 * @returns {Promise<boolean>} true si toutes les tentatives sont faites
 */
export const refetchAfterBulkTimeout = async (prefixes, options = {}) => {
  const {
    maxAttempts = 3,
    delay = 5000,
    onProgress = null,
    onComplete = null  // ⭐ NOUVEAU: Callback de fin de polling
  } = options;

  // Validation
  if (!Array.isArray(prefixes) || prefixes.length === 0) {
    console.error('[refetchAfterBulkTimeout] Invalid prefixes:', prefixes);
    return false;
  }

  console.log('[refetchAfterBulkTimeout] Starting polling', {
    prefixes,
    maxAttempts,
    delayMs: delay
  });

  // Boucle de polling
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    // 1. Attendre avant de refetch (laisser backend finir)
    console.log(`[refetchAfterBulkTimeout] Waiting ${delay}ms before attempt ${attempt}/${maxAttempts}...`);
    await new Promise(resolve => setTimeout(resolve, delay));

    // 2. Notifier la modal AVANT le refetch (pour afficher "attempt X")
    if (onProgress && typeof onProgress === 'function') {
      try {
        onProgress(attempt, maxAttempts);
      } catch (err) {
        console.error('[refetchAfterBulkTimeout] onProgress callback error:', err);
      }
    }

    // 3. Refetch les données
    console.log(`[refetchAfterBulkTimeout] Refetching attempt ${attempt}/${maxAttempts}...`);
    revalidateMultiple(prefixes);

    // 4. Attendre un court instant pour que SWR finisse le refetch
    // (500ms pour laisser le temps aux requêtes réseau de se terminer)
    await new Promise(resolve => setTimeout(resolve, 500));
  }

  console.log('[refetchAfterBulkTimeout] Polling completed successfully');
  
  // ⭐ NOUVEAU: Appeler onComplete APRÈS la fin de tous les refetch
  if (onComplete && typeof onComplete === 'function') {
    try {
      console.log('[refetchAfterBulkTimeout] Calling onComplete callback');
      onComplete();
    } catch (err) {
      console.error('[refetchAfterBulkTimeout] onComplete callback error:', err);
    }
  }
  
  return true;
};

// ==============================|| EXEMPLES D'USAGE ||============================== //

/**
 * EXEMPLES D'UTILISATION :
 * 
 * // 1. Dans un hook - Clé SWR avec tenant
 * const swrKey = tenantKey('/client/users/', tenantId);
 * const { data } = useSWR(swrKey, fetcher);
 * 
 * // 2. Revalidation simple après mutation
 * revalidateByPrefix('/client/users/');
 * 
 * // 3. Revalidation multiple
 * revalidateMultiple([
 *   '/client/users/',
 *   '/client/client-accounts/'
 * ]);
 * 
 * // 4. Matcher custom
 * mutate(matchKey('/client/users/'), undefined, { revalidate: true });
 * 
 * // 5. ⭐ NOUVEAU : Revalidation intelligente après bulk operation (RECOMMANDÉ)
 * export const bulkDeleteUsers = async (userIds, mode, onSyncProgress = null) => {
 *   let result = null;
 *   try {
 *     result = await api.delete('/client/users/bulk-delete/', {...});
 *     return result.data;
 *   } catch (err) {
 *     return { success: false, ... };
 *   } finally {
 *     // ⭐ Helper centralisé qui décide automatiquement
 *     await handleBulkRevalidation(
 *       result,
 *       ['/client/users/', '/client/client-accounts/'],
 *       onSyncProgress  // Callback pour notifier modal
 *     );
 *   }
 * };
 * 
 * // 6. Décision manuelle (cas avancés)
 * const result = await api.delete('/client/users/bulk-delete/', {...});
 * if (shouldUseProgressiveRefetch(result)) {
 *   await refetchAfterBulkTimeout([...], { onProgress: ... });
 * } else {
 *   revalidateMultiple([...]);
 * }
 */