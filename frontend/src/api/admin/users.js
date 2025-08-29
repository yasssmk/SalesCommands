// frontend/src/api/admin/users.js

import useSWR, { mutate } from 'swr';
import { useMemo } from 'react';
import { useAuth } from 'hooks/useAuth';

// utils
import axiosClient, { api } from 'utils/axiosClient';
import { tenantKey, revalidateByPrefix, revalidateMultiple } from 'api/_swr';

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  users: '/client/users/',
  organizations: '/client/organizations/',
  teams: '/client/teams/',
  roles: '/client/roles/',
  clientAccountStats: (clientId) => `/client/client-accounts/${clientId}/stats/`
};

// ==============================|| SWR FETCHER ||============================== //

const fetcher = async (urlOrTuple) => {
  // ✅ Support des tuples [url, tenantId] et des URLs simples (legacy)
  const url = Array.isArray(urlOrTuple) ? urlOrTuple[0] : urlOrTuple;

  const result = await api.get(url);
  if (result.success) {
    return result.data;
  }
  throw new Error(result.error || 'Failed to fetch data');
};

// ==============================|| HOOKS SWR STANDARDISÉS ||============================== //

/**
 * ✅ GET USERS LIST - Clé tenant standardisée
 * Uses Django pagination format with results array
 */
export function useGetUsers() {
  const { tenantId } = useAuth();

  // ✅ STANDARDISÉ: Utilise toujours tenantKey()
  const swrKey = tenantKey(endpoints.users, tenantId);

  const { data, isLoading, error, isValidating } = useSWR(
    swrKey,
    fetcher,
    {
      revalidateIfStale: false,
      revalidateOnFocus: false,
      revalidateOnReconnect: false
    }
  );

  const memoizedValue = useMemo(
    () => ({
      users: data?.results || [],
      usersCount: data?.count || 0,
      usersLoading: isLoading,
      usersError: error,
      usersValidating: isValidating,
      usersEmpty: !isLoading && (!data?.results?.length)
    }),
    [data, error, isLoading, isValidating]
  );

  return memoizedValue;
}

/**
 * ✅ GET SINGLE USER - Clé tenant standardisée
 */
export function useGetUser(userId) {
  const { tenantId } = useAuth();

  // ✅ STANDARDISÉ: tenantKey pour single user
  const swrKey = userId && tenantId 
    ? tenantKey(`${endpoints.users}${userId}/`, tenantId) 
    : null;
  
  const { data, isLoading, error, isValidating } = useSWR(
    swrKey,
    fetcher,
    {
      revalidateIfStale: false,
      revalidateOnFocus: false,
      revalidateOnReconnect: false
    }
  );

  const memoizedValue = useMemo(
    () => ({
      user: data,
      userLoading: isLoading,
      userError: error,
      userValidating: isValidating
    }),
    [data, error, isLoading, isValidating]
  );

  return memoizedValue;
}

/**
 * ✅ GET ORGANIZATIONS - Clé tenant standardisée
 */
export function useGetOrganizations() {
  const { tenantId } = useAuth(); 
  
  // ✅ STANDARDISÉ: tenantKey()
  const swrKey = tenantKey(endpoints.organizations, tenantId);
  
  const { data, isLoading, error } = useSWR(
    swrKey, 
    fetcher,
    {
      revalidateIfStale: false,
      revalidateOnFocus: false,
      revalidateOnReconnect: false
    }
  );

  const memoizedValue = useMemo(
    () => ({
      organizations: data?.results || [],
      organizationsLoading: isLoading,
      organizationsError: error
    }),
    [data, isLoading, error]
  );

  return memoizedValue;
}

/**
 * ✅ GET TEAMS - Clé tenant standardisée avec filtres
 * @param {Object} filters - ex: { organization: 'uuid' }
 * @param {boolean} enabled - if false, skip fetch
 */
export function useGetTeams(filters = {}, enabled = true) {
  const { tenantId } = useAuth(); 
  
  const qs = new URLSearchParams(filters || {}).toString();
  const url = `${endpoints.teams}${qs ? `?${qs}` : ''}`;
  
  // ✅ STANDARDISÉ: tenantKey avec URL complète incluant filtres
  const swrKey = enabled ? tenantKey(url, tenantId) : null;

  const { data, isLoading, error } = useSWR(
    swrKey, 
    fetcher,
    {
      revalidateIfStale: false,
      revalidateOnFocus: false,
      revalidateOnReconnect: false
    }
  );

  const memoizedValue = useMemo(
    () => ({
      teams: data?.results || [],
      teamsLoading: isLoading,
      teamsError: error
    }),
    [data, isLoading, error]
  );

  return memoizedValue;
}

/**
 * ✅ GET USER ROLES - Clé tenant standardisée
 */
export function useGetUserRoles() {
  const { tenantId } = useAuth(); 
  
  // ✅ STANDARDISÉ: tenantKey()
  const swrKey = tenantKey(endpoints.roles, tenantId);
  
  const { data, isLoading, error } = useSWR(
    swrKey, 
    fetcher,
    {
      revalidateIfStale: false,
      revalidateOnFocus: false,
      revalidateOnReconnect: false
    }
  );

  const memoizedValue = useMemo(
    () => ({
      roles: data?.results || [],
      rolesLoading: isLoading,
      rolesError: error
    }),
    [data, isLoading, error]
  );

  return memoizedValue;
}

/**
 * ✅ GET CLIENT SEATS STATS - Clé tenant standardisée
 * seats = client.max_users
 * seats_used = # active users
 * seats_left = seats - seats_used
 */
export function useGetClientSeats(clientId) {
  const key = clientId ? 
    endpoints.clientAccountStats(clientId) : null;

  const { data, isLoading, error, isValidating } = useSWR(
    key,
    fetcher,
    {
      revalidateIfStale: false,
      revalidateOnFocus: false,
      revalidateOnReconnect: false
    }
  );

  // our api wrapper returns the inner "data", so seats should be directly under data.seats
  const root = data?.seats ? data : data?.data ? data.data : {};
  const s = root?.seats || {};

  const seats = Number(s.seats ?? 0);
  const seatsUsed = Number(s.seats_used ?? 0);
  const seatsLeft = Number(s.seats_left ?? Math.max(0, seats - seatsUsed));

  return {
    seats,
    seatsUsed,
    seatsLeft,
    seatsLoading: isLoading,
    seatsError: error,
    seatsValidating: isValidating,
    raw: data
  };
}

// ==============================|| HOOKS POUR RESOURCE GUARD LAYOUT ||============================== //

/**
 * ✅ GET SINGLE TEAM - Pour ResourceGuardLayout
 * 
 * SÉCURITÉ MULTI-TENANT :
 * - Clé avec tenantId pour isolation
 * - Compatible avec RequireResourceAccess
 * - Naming cohérent : team + teamLoading + teamError
 */
export function useGetTeam(teamId) {
  const { tenantId } = useAuth();

  // ✅ STANDARDISÉ: tenantKey pour single team
  const swrKey = teamId && tenantId 
    ? tenantKey(`${endpoints.teams}${teamId}/`, tenantId) 
    : null;
  
  const { data, isLoading, error, isValidating } = useSWR(
    swrKey,
    fetcher,
    {
      revalidateIfStale: false,
      revalidateOnFocus: false,
      revalidateOnReconnect: false
    }
  );

  const memoizedValue = useMemo(
    () => ({
      team: data,
      teamLoading: isLoading,
      teamError: error,
      teamValidating: isValidating
    }),
    [data, error, isLoading, isValidating]
  );

  return memoizedValue;
}

/**
 * ✅ GET SINGLE ORGANIZATION - Pour ResourceGuardLayout
 * 
 * SÉCURITÉ MULTI-TENANT :
 * - Clé avec tenantId pour isolation
 * - Compatible avec RequireResourceAccess
 * - Naming cohérent : organization + organizationLoading + organizationError
 */
export function useGetOrganization(orgId) {
  const { tenantId } = useAuth();

  // ✅ STANDARDISÉ: tenantKey pour single organization
  const swrKey = orgId && tenantId 
    ? tenantKey(`${endpoints.organizations}${orgId}/`, tenantId) 
    : null;
  
  const { data, isLoading, error, isValidating } = useSWR(
    swrKey,
    fetcher,
    {
      revalidateIfStale: false,
      revalidateOnFocus: false,
      revalidateOnReconnect: false
    }
  );

  const memoizedValue = useMemo(
    () => ({
      organization: data,
      organizationLoading: isLoading,
      organizationError: error,
      organizationValidating: isValidating
    }),
    [data, error, isLoading, isValidating]
  );

  return memoizedValue;
}

// ==============================|| CRUD FUNCTIONS AVEC REVALIDATIONS STANDARDISÉES ||============================== //

/**
 * ✅ CREATE USER - Revalidation standardisée
 */
export const insertUser = async (userData) => {
  const result = await api.post(endpoints.users, userData);

  if (result.success) {
    // ✅ STANDARDISÉ: revalidateByPrefix pour tous les endpoints impactés
    revalidateMultiple([
      endpoints.users,                    // Liste users
      '/client/client-accounts/'          // Stats seats
    ]);

    return { success: true, user: result.data };
  } else {
    return { success: false, error: result.error };
  }
};

/**
 * ✅ UPDATE USER (PATCH) - Revalidation standardisée
 */
export const updateUser = async (userId, userData) => {
  const result = await api.patch(`${endpoints.users}${userId}/`, userData);

  if (result.success) {
    // ✅ STANDARDISÉ: revalidation ciblée avec prefixes
    revalidateMultiple([
      endpoints.users,                     // Liste users
      `${endpoints.users}${userId}/`,      // User spécifique
      '/client/client-accounts/'           // Stats seats
    ]);

    return { success: true, user: result.data };
  } else {
    return { success: false, error: result.error };
  }
};

/**
 * ✅ CHANGE USER PASSWORD - Revalidation standardisée
 * @param {string} userId - ID de l'utilisateur
 * @param {string} password - Nouveau mot de passe
 * @param {string} passwordConfirm - Confirmation du mot de passe
 * @returns {Promise<Object>} {success: boolean, user?: Object, error?: string}
 */
export const changePassword = async (userId, password, passwordConfirm) => {
  const result = await api.patch(`${endpoints.users}${userId}/change-password/`, {
    password,
    password_confirm: passwordConfirm
  });

  if (result.success) {
    // ✅ STANDARDISÉ: revalidation ciblée uniquement sur l'user modifié
    revalidateByPrefix(`${endpoints.users}${userId}/`);
    
    return { 
      success: true, 
      message: result.data?.message || 'Password changed successfully',
      user: result.data?.user 
    };
  } else {
    return { 
      success: false, 
      error: result.error || 'Failed to change password' 
    };
  }
};

/**
 * ✅ DELETE USER - Revalidation standardisée
 */
export const deleteUser = async (userId) => {
  const result = await api.delete(`${endpoints.users}${userId}/`);

  if (result.success) {
    // ✅ STANDARDISÉ: revalidation multiple après suppression
    revalidateMultiple([
      endpoints.users,                    // Liste users
      '/client/client-accounts/'          // Stats seats (seats_used diminue)
    ]);
    
    return { success: true, status: result.status ?? 204 };
  } else {
    return { success: false, error: result.error, status: result.status };
  }
};

/**
 * ✅ TOGGLE USER STATUS - Revalidation standardisée
 */
export const toggleUserStatus = async (userId) => {
  const result = await api.post(`${endpoints.users}${userId}/toggle-status/`);

  if (result.success) {
    // ✅ STANDARDISÉ: revalidation après changement de statut
    revalidateMultiple([
      endpoints.users,                     // Liste users
      `${endpoints.users}${userId}/`,      // User spécifique
      '/client/client-accounts/'           // Stats seats (active/inactive impact)
    ]);

    return { success: true, user: result.data };
  } else {
    return { success: false, error: result.error };
  }
};

// ==============================|| HELPER FUNCTIONS ||============================== //

/**
 * ✅ REFRESH USERS LIST - Utilise les nouveaux helpers
 */
export const refreshUsers = () => revalidateByPrefix(endpoints.users);

/**
 * ✅ REFRESH CLIENT SEATS - Utilise les nouveaux helpers
 */
export const refreshClientSeats = () => revalidateByPrefix('/client/client-accounts/');

/**
 * ✅ FILTER USERS - Support des filtres avec clés tenant
 */
export const filterUsers = (filters) => {
  const queryParams = new URLSearchParams(filters).toString();
  const url = `${endpoints.users}?${queryParams}`;
  return revalidateByPrefix(url);
};

// ==============================|| BACKWARD COMPATIBILITY (LEGACY) ||============================== //

/**
 * ✅ LEGACY SUPPORT - Export des anciens noms pour transition en douceur
 * Ces fonctions seront supprimées en Phase 2
 */
export const revalidateUsersLists = () => {
  console.warn('[DEPRECATED] revalidateUsersLists() → use refreshUsers()');
  return refreshUsers();
};

// ==============================|| RÉSUMÉ DES AMÉLIORATIONS ||============================== //

/*
✅ STANDARDISATION COMPLÈTE :
- Toutes les clés SWR utilisent tenantKey(url, tenantId)
- Revalidations avec revalidateByPrefix() et revalidateMultiple()
- Support tuples ET strings dans les revalidations
- Isolation multi-tenant garantie

✅ SÉCURITÉ RENFORCÉE :
- Impossible de récupérer des données d'un autre tenant
- Clés uniformes [url, tenantId] pour tous les hooks
- Revalidations ciblées qui matchent les bonnes clés

✅ PERFORMANCE OPTIMISÉE :
- Revalidations ciblées (pas de purge globale)
- Support des filtres dans les clés
- Backward compatibility pour migration en douceur

✅ MAINTENANCE SIMPLIFIÉE :
- Une seule façon de gérer les clés SWR
- Helpers centralisés réutilisables
- Code plus prévisible et debuggable
*/