// frontend/src/hooks/useRetryCountdown.js

/**
 * ✅ Hook countdown pour erreurs 429
 * 
 * Affiche un décompte dynamique qui décrémente chaque seconde
 * pendant le délai Retry-After d'une erreur 429.
 * 
 * PROTECTION ANTI-FUITES :
 * - Cleanup automatique des intervals au unmount
 * - Protection contre les mises à jour post-unmount
 * - Gestion robuste des cas limites
 * 
 * @module hooks/useRetryCountdown
 */

import { useState, useEffect, useRef } from 'react';

/**
 * Hook pour afficher un countdown dynamique lors d'un 429
 * 
 * @param {Error} error - Erreur Axios (doit contenir error.status et error.retryAfterMs)
 * @returns {number|null} Secondes restantes (null si pas de 429 ou countdown terminé)
 * 
 * @example
 * const secondsLeft = useRetryCountdown(error);
 * 
 * {secondsLeft !== null && (
 *   <Typography>
 *     Retry in <strong>{secondsLeft}s</strong>
 *   </Typography>
 * )}
 */
export const useRetryCountdown = (error) => {
  const [secondsLeft, setSecondsLeft] = useState(null);
  const intervalRef = useRef(null);
  const isMountedRef = useRef(true);
  
  // ✅ Cleanup au unmount
  useEffect(() => {
    return () => {
      isMountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, []);
  
  // ✅ Démarrer le countdown quand error.retryAfterMs change
  useEffect(() => {
    // Cleanup de l'interval précédent
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    
    // Démarrer le countdown si 429 avec Retry-After
    if (error?.status === 429 && error?.retryAfterMs && isMountedRef.current) {
      const totalSeconds = Math.ceil(error.retryAfterMs / 1000);
      setSecondsLeft(totalSeconds);
      
      // Interval qui décrémente chaque seconde
      intervalRef.current = setInterval(() => {
        if (!isMountedRef.current) {
          clearInterval(intervalRef.current);
          return;
        }
        
        setSecondsLeft(prev => {
          // Countdown terminé
          if (prev <= 1) {
            if (intervalRef.current) {
              clearInterval(intervalRef.current);
              intervalRef.current = null;
            }
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } else {
      // Pas de 429 ou pas de retryAfterMs → Reset
      setSecondsLeft(null);
    }
    
    // Cleanup au changement d'error
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [error?.status, error?.retryAfterMs]);
  
  return secondsLeft;
};

export default useRetryCountdown;