// frontend/src/hooks/useErrorWithRetry.js

/**
 * ✅ Hook pour afficher snackbar progressif pendant retries SWR
 * 
 * Affiche automatiquement :
 * - Premier échec : "Failed to load. Retrying... (1/3)"
 * - Pendant retries : Met à jour le count "(2/3)", "(3/3)"
 * - Échec final : "Failed to load after multiple attempts"
 * 
 * Évite le spam grâce à la dedup intégrée dans utils/snackbar
 * 
 * @module hooks/useErrorWithRetry
 */

import { useEffect, useRef } from 'react';
import { displayErrorSnackbar } from 'utils/displayError';

/**
 * Hook pour gérer l'affichage des erreurs avec retry progressif
 * 
 * @param {Error} error - Erreur SWR (ou null si pas d'erreur)
 * @param {boolean} isValidating - État SWR isValidating (true pendant fetch/retry)
 * @param {Object} options - Options de configuration
 * @param {boolean} options.silent - Si true, n'affiche pas de snackbar (mode silencieux)
 * @param {number} options.maxRetries - Nombre max de retries (défaut: 3)
 * 
 * @example
 * // Usage basique
 * const { data, error, isValidating } = useSWR('/api/users');
 * useErrorWithRetry(error, isValidating);
 * 
 * @example
 * // Mode silencieux (pour tables avec ErrorDisplay inline)
 * useErrorWithRetry(error, isValidating, { silent: true });
 */
export function useErrorWithRetry(error, isValidating, options = {}) {
  const { 
    silent = false,
    maxRetries = 3 
  } = options;
  
  // Track retry count et si on a déjà affiché une erreur
  const retryCountRef = useRef(0);
  const hasShownErrorRef = useRef(false);
  const lastErrorMessageRef = useRef('');
  
  useEffect(() => {
    // Reset si pas d'erreur
    if (!error) {
      retryCountRef.current = 0;
      hasShownErrorRef.current = false;
      lastErrorMessageRef.current = '';
      return;
    }
    
    // Skip si mode silencieux
    if (silent) return;
    
    // Extraire status et message
    const status = error?.response?.status || error?.status || 0;
    const isNetworkError = status === 0 || !error.response;
    
    // Skip auth errors (géré par interceptor axios)
    if (status === 401 || status === 403) {
      return;
    }
    
    // Skip 429 (géré par SWR onError global avec Retry-After)
    if (status === 429) {
      return;
    }
    
    // Déterminer si on doit afficher un snackbar
    const shouldDisplay = 
      status >= 500 ||           // Server errors
      isNetworkError ||          // Network errors (backend down)
      status === 408;            // Timeouts
    
    if (!shouldDisplay) {
      return;
    }
    
    // ✅ CAS 1 : Pendant un retry (isValidating = true)
    if (isValidating) {
      // Incrémenter le retry count seulement si c'est une nouvelle tentative
      if (hasShownErrorRef.current) {
        retryCountRef.current++;
      }
      
      // Message progressif
      const currentRetry = Math.min(retryCountRef.current + 1, maxRetries);
      let message = `Failed to load. Retrying... (${currentRetry}/${maxRetries})`;
      
      // Personnaliser selon le type d'erreur
      if (isNetworkError) {
        message = `Unable to connect. Retrying... (${currentRetry}/${maxRetries})`;
      } else if (status >= 500) {
        message = `Server error. Retrying... (${currentRetry}/${maxRetries})`;
      }
      
      // Afficher le snackbar (dedup automatique évite le spam)
      // On force un nouveau message à chaque retry pour que le count s'affiche
      if (lastErrorMessageRef.current !== message) {
        displayErrorSnackbar({
          ...error,
          message
        }, { 
          suppressDedup: false  // Laisser dedup gérer
        });
        
        lastErrorMessageRef.current = message;
      }
      
      hasShownErrorRef.current = true;
    } 
    // ✅ CAS 2 : Échec final (isValidating = false, mais on a eu des erreurs avant)
    else if (hasShownErrorRef.current && !isValidating) {
      // Message d'échec final
      let finalMessage;
      
      if (isNetworkError) {
        finalMessage = 'Unable to connect to server. Please check your connection and try again.';
      } else if (status >= 500) {
        finalMessage = 'Server error persists after multiple attempts. Please try again later.';
      } else if (status === 408) {
        finalMessage = 'Request timed out after multiple attempts. Please try again.';
      } else {
        finalMessage = 'Failed to load data after multiple attempts. Please refresh the page.';
      }
      
      // Afficher seulement si différent du dernier message
      if (lastErrorMessageRef.current !== finalMessage) {
        displayErrorSnackbar({
          ...error,
          message: finalMessage
        });
        
        lastErrorMessageRef.current = finalMessage;
      }
    }
    // ✅ CAS 3 : Première erreur (pas encore de retry)
    else if (!hasShownErrorRef.current && !isValidating) {
      let message;
      
      if (isNetworkError) {
        message = 'Unable to connect to server. Please check your connection.';
      } else if (status >= 500) {
        message = 'Server error. Please try again.';
      } else if (status === 408) {
        message = 'Request timed out. Please try again.';
      } else {
        message = 'Failed to load data. Please try again.';
      }
      
      displayErrorSnackbar({
        ...error,
        message
      });
      
      lastErrorMessageRef.current = message;
      hasShownErrorRef.current = true;
    }
  }, [error, isValidating, silent, maxRetries]);
  
  // Retourner des infos utiles pour le composant (optionnel)
  return {
    hasError: !!error,
    isRetrying: isValidating && hasShownErrorRef.current,
    retryCount: retryCountRef.current
  };
}

export default useErrorWithRetry;