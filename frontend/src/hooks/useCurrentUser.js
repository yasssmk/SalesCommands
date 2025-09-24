'use client';

import { useAuth } from './useAuth';

/**
 * ✅ HOOK CENTRALISÉ POUR LE CURRENT USER
 * 
 * Expose les données du current user depuis le contexte Auth existant.
 * Évite les appels API dupliqués en utilisant le state déjà chargé par useAuth.
 * 
 * @returns {Object} Current user data from Auth context
 * - currentUser: User object or null
 * - currentUserLoading: Boolean loading state  
 * - currentUserError: Error message if any
 * - refreshCurrentUser: Function to manually refresh user data
 */
export function useCurrentUser() {
  const { user, isLoading, error, refreshUser } = useAuth();
  
  return {
    currentUser: user,
    currentUserLoading: isLoading,
    currentUserError: error,
    refreshCurrentUser: refreshUser
  };
}

export default useCurrentUser;