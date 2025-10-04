// frontend/src/api/admin/users.js

import useSWR, { mutate } from 'swr';
import { useMemo, useEffect } from 'react';
import { useAuth } from 'hooks/useAuth';

// utils
import axiosClient, { api } from 'utils/axiosClient';
import { tenantKey, revalidateByPrefix, revalidateMultiple } from 'api/_swr';
import { isValidUUID, sanitizeObject } from 'utils/validators';

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  users: '/client/users/',
  organizations: '/client/organizations/',
  teams: '/client/teams/',
  roles: '/client/roles/',
  clientAccountSeats: (clientId) => `/client/client-accounts/${clientId}/seats/`,
  clientAccountStats: (clientId) => `/client/client-accounts/${clientId}/stats/`
};

// ==============================|| HELPER - BUILD URL WITH PARAMS ||============================== //

/**
 * Construit une URL avec query params pour la pagination serveur
 * @param {string} baseUrl - URL de base
 * @param {Object} params - Paramètres optionnels {page, pageSize, search}
 * @returns {string} URL avec query string
 */
const buildUrlWithParams = (baseUrl, params = {}) => {
  const { page, pageSize, search } = params;
  const queryParams = new URLSearchParams();
  
  // Ajouter les paramètres s'ils sont définis
  if (page !== undefined && page !== null) {
    queryParams.append('page', page);
  }
  
  if (pageSize !== undefined && pageSize !== null) {
    queryParams.append('page_size', pageSize);
  }
  
  if (search !== undefined && search !== null && search !== '') {
    queryParams.append('search', search);
  }
  
  const queryString = queryParams.toString();
  return queryString ? `${baseUrl}?${queryString}` : baseUrl;
};



// ==============================|| HOOKS SWR STANDARDISÉS ||============================== //

/**
 * ✅ GET USERS LIST - Avec pagination serveur Django REST
 * 
 * @param {Object} options - Options de pagination
 * @param {number} options.page - Numéro de page (1-indexed, défaut: 1)
 * @param {number} options.pageSize - Taille de page (défaut: 10)
 * @param {string} options.search - Terme de recherche
 * 
 * @returns {Object} {users, usersCount, usersLoading, usersError, usersValidating, usersEmpty}
 * 
 * @example
 * // Sans paramètres (page 1, taille 10)
 * const { users, usersCount } = useGetUsers();
 * 
 * @example
 * // Avec pagination
 * const { users, usersCount } = useGetUsers({ page: 2, pageSize: 25 });
 * 
 * @example
 * // Avec recherche
 * const { users, usersCount } = useGetUsers({ search: 'john', page: 1, pageSize: 10 });
 */
export function useGetUsers(options = {}) {
  const { tenantId } = useAuth();
  const { page = 1, pageSize = 10, search = '' } = options;

  const urlWithParams = useMemo(() => {
    return buildUrlWithParams(endpoints.users, { 
      page, 
      pageSize, 
      search 
    });
  }, [page, pageSize, search]);

  // ✅ STANDARDISÉ: Utilise toujours tenantKey()
  const swrKey = tenantKey(urlWithParams, tenantId);
  const { data, isLoading, error, isValidating } = useSWR(swrKey);

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
 * ✅ GET SINGLE USER - Pour UN utilisateur spécifique
 * @param {string} userId - ID de l'utilisateur à récupérer
 * 
 * ⚠️ IMPORTANT: Pour le current user, utiliser useCurrentUser() à la place
 */
export function useGetUser(userId) {
  const { tenantId, user: currentUser } = useAuth();
  
  // ✅ GUARD INTELLIGENT: Détection automatique du current user
  const isRequestingCurrentUser = !userId || userId === 'current' || userId === 'me';
  const shouldUseCurrentUser = isRequestingCurrentUser || userId === currentUser?.id;
  
  // Si c'est le current user demandé, on utilise les données du contexte Auth
  // Évite un appel API supplémentaire car on a déjà les données
  if (shouldUseCurrentUser) {
    if (process.env.NODE_ENV === 'development') {
      console.info('ℹ️ useGetUser redirected to current user from Auth context');
    }
    
    return {
      user: currentUser,
      userLoading: false,  // Déjà chargé via AuthProvider
      userError: null,
      userValidating: false
    };
  }

  // ✅ STANDARDISÉ: tenantKey pour single user
  const swrKey = userId && tenantId 
    ? tenantKey(`${endpoints.users}${userId}/`, tenantId) 
    : null;

  const { data, isLoading, error, isValidating } = useSWR(swrKey);

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
  
  // const { data, isLoading, error } = useSWR(
  //   swrKey, 
  //   fetcher,
  //   {
  //     revalidateIfStale: false,
  //     revalidateOnFocus: false,
  //     revalidateOnReconnect: false
  //   }
  // );

  const { data, isLoading, error } = useSWR(swrKey);

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

  // const { data, isLoading, error } = useSWR(
  //   swrKey, 
  //   fetcher,
  //   {
  //     revalidateIfStale: false,
  //     revalidateOnFocus: false,
  //     revalidateOnReconnect: false
  //   }
  // );
  const { data, isLoading, error } = useSWR(swrKey);

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
  
  // const { data, isLoading, error } = useSWR(
  //   swrKey, 
  //   fetcher,
  //   {
  //     revalidateIfStale: false,
  //     revalidateOnFocus: false,
  //     revalidateOnReconnect: false
  //   }
  // );

  const { data, isLoading, error } = useSWR(swrKey);

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
  const { tenantId } = useAuth(); 
  
  // ✅ NOUVEAU: Utilise l'endpoint /seats/ au lieu de /stats/
  const swrKey = clientId && tenantId? 
    tenantKey(endpoints.clientAccountSeats(clientId), tenantId) : null;

  const { data, isLoading, error, isValidating } = useSWR(swrKey);
  
  // Debug pour vérifier la structure
  // if (process.env.NODE_ENV === 'development' && data) {
  //   console.log('[useGetClientSeats] Response:', data);
  // }

  // ✅ Structure correcte: data.data contient directement seats, seats_used, seats_left
  const seatData = data?.data || {};
  
  const seats = Number(seatData.seats ?? 0);
  const seatsUsed = Number(seatData.seats_used ?? 0);
  const seatsLeft = Number(seatData.seats_left ?? 0);

  const memoizedValue = useMemo(
    () => ({
      seats,
      seatsUsed,
      seatsLeft,
      seatsLoading: isLoading,
      seatsError: error,
      seatsValidating: isValidating,
      // Métadonnées de performance
      timing: data?._meta?.timing_ms,
      raw: data  // Pour debug si besoin
    }),
    [seats, seatsUsed, seatsLeft, isLoading, error, isValidating, data]
  );

  return memoizedValue;
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
  
  // const { data, isLoading, error, isValidating } = useSWR(
  //   swrKey,
  //   fetcher,
  //   {
  //     revalidateIfStale: false,
  //     revalidateOnFocus: false,
  //     revalidateOnReconnect: false
  //   }
  // );

  const { data, isLoading, error, isValidating } = useSWR(swrKey);

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
  
  // const { data, isLoading, error, isValidating } = useSWR(
  //   swrKey,
  //   fetcher,
  //   {
  //     revalidateIfStale: false,
  //     revalidateOnFocus: false,
  //     revalidateOnReconnect: false
  //   }
  // );

  const { data, isLoading, error, isValidating } = useSWR(swrKey);

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
 * ✅ CREATE USER - Revalidation standardisée + validation client
 * 
 * ✅ PHASE 5.3.2: Added UUID validation and string sanitization
 * 
 * @param {Object} userData - User data to create
 * @returns {Promise<Object>} {success: boolean, user?: Object, error?: string}
 */
export const insertUser = async (userData) => {
  // ✅ PHASE 5.3.2: Validate UUID fields before API call
  const uuidFields = ['role', 'organization', 'team'];
  for (const field of uuidFields) {
    const value = userData[field];
    
    // Skip validation if field is null/undefined/empty (nullable fields)
    if (!value || value === '') continue;
    
    // Validate UUID format
    if (!isValidUUID(value)) {
      return {
        success: false,
        error: `Invalid ${field} ID format. Please select a valid ${field}.`
      };
    }
  }
  
  // ✅ PHASE 5.3.2: Sanitize string fields (trim whitespace)
  const sanitized = sanitizeObject(userData, ['email', 'first_name', 'last_name']);
  
  const result = await api.post(endpoints.users, sanitized);
  
  console.log(result);
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
 * ✅ UPDATE USER (PATCH) - Revalidation standardisée + validation client
 * 
 * ✅ PHASE 5.3.2: Added UUID validation for userId and related fields
 * 
 * @param {string} userId - User ID to update
 * @param {Object} userData - User data to update
 * @returns {Promise<Object>} {success: boolean, user?: Object, error?: string}
 */
export const updateUser = async (userId, userData) => {
  // ✅ PHASE 5.3.2: Validate userId is a valid UUID
  if (!userId || !isValidUUID(userId)) {
    return {
      success: false,
      error: 'Invalid user ID format. Cannot update user.'
    };
  }
  
  // ✅ PHASE 5.3.2: Validate UUID fields in userData
  const uuidFields = ['role', 'organization', 'team'];
  for (const field of uuidFields) {
    const value = userData[field];
    
    // Skip validation if field is null/undefined/empty (nullable fields)
    if (!value || value === '') continue;
    
    // Validate UUID format
    if (!isValidUUID(value)) {
      return {
        success: false,
        error: `Invalid ${field} ID format. Please select a valid ${field}.`
      };
    }
  }
  
  // ✅ PHASE 5.3.2: Sanitize string fields (trim whitespace)
  const sanitized = sanitizeObject(userData, ['first_name', 'last_name']);
  
  const result = await api.patch(`${endpoints.users}${userId}/`, sanitized);

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
 * ✅ CHANGE USER PASSWORD - Revalidation standardisée + validation client
 * 
 * ✅ PHASE 5.3.2: Added UUID validation for userId
 * 
 * @param {string} userId - ID de l'utilisateur
 * @param {string} password - Nouveau mot de passe
 * @param {string} passwordConfirm - Confirmation du mot de passe
 * @returns {Promise<Object>} {success: boolean, user?: Object, error?: Object, error?: string}
 */
export const changePassword = async (userId, password, passwordConfirm) => {
  // ✅ PHASE 5.3.2: Validate userId is a valid UUID
  if (!userId || !isValidUUID(userId)) {
    return {
      success: false,
      error: 'Invalid user ID format. Cannot change password.'
    };
  }
  
  // ✅ Additional validation: password length (client-side quick check)
  if (!password || password.length < 8) {
    return {
      success: false,
      error: 'Password must be at least 8 characters long.'
    };
  }
  
  // ✅ Additional validation: passwords match
  if (password !== passwordConfirm) {
    return {
      success: false,
      error: 'Passwords do not match.'
    };
  }
  
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
 * ✅ DELETE USER - Revalidation standardisée + validation client
 * 
 * ✅ PHASE 5.3.2: Added UUID validation for userId
 * 
 * @param {string} userId - User ID to delete
 * @returns {Promise<Object>} {success: boolean, status?: number, error?: string}
 */
export const deleteUser = async (userId) => {
  // ✅ PHASE 5.3.2: Validate userId is a valid UUID
  if (!userId || !isValidUUID(userId)) {
    return {
      success: false,
      error: 'Invalid user ID format. Cannot delete user.',
      status: 400
    };
  }
  
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
 * ✅ TOGGLE USER STATUS - Revalidation standardisée + validation client
 * 
 * ✅ PHASE 5.3.2: Added UUID validation for userId
 * 
 * @param {string} userId - User ID to toggle status
 * @returns {Promise<Object>} {success: boolean, user?: Object, error?: string}
 */
export const toggleUserStatus = async (userId) => {
  // ✅ PHASE 5.3.2: Validate userId is a valid UUID
  if (!userId || !isValidUUID(userId)) {
    return {
      success: false,
      error: 'Invalid user ID format. Cannot toggle user status.'
    };
  }
  
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

// =============================|| BULK CRUD || ==================================== //

/**
 * Bulk create users
 * @param {Array} users - Array of user objects
 * @param {string} mode - 'partial' or 'strict'
 * @returns {Promise} Response with created users and errors
 */
export const createBulkUsers = async (users, mode = 'partial') => {
  try {
    // 🔎 debug non-PII
    console.log('[createBulkUsers] start', { count: users?.length ?? 0, mode });

    // Utilise NOTRE wrapper standardisé (cookies, corr-id, handleApiError, etc.)
    const result = await api.post('/client/users/bulk-create/', { users, mode });

    if (result.success) {
      console.log('[createBulkUsers] ok', { status: result.status ?? 201 });
      return result.data; // ← shape backend direct (summary/results/…)
    }

    // ✅ IMPORTANT: En cas d'erreur HTTP 400, le backend renvoie toujours des données structurées
    // result.data est maintenant préservé même en cas d'erreur grâce à notre fix dans apiRequest
    const status = result.status || 0;
    const message = result.error || 'Bulk create failed';
    console.error('[createBulkUsers] api.post error', { status, message });

    // Si le backend a renvoyé des données structurées avec les détails d'erreur
    if (result.data && typeof result.data === 'object') {
      // Vérifier si c'est une réponse structurée du backend (avec results/summary)
      if (result.data.results || result.data.summary) {
        console.log('[createBulkUsers] returning structured error from backend');
        // ✅ Fusionner avec success: false pour être cohérent
        return {
          ...result.data,
          success: false  // S'assurer que success est false
        };
      }
    }

    // Fallback: structure d'erreur générique si pas de données détaillées
    return {
      success: false,
      message: message,
      error: { status, message, response: result.response || null },
      summary: { total: users.length, success: 0, failed: users.length, skipped: 0 },
      results: {
        success: [],
        failed: users.map((u, i) => ({
          row: i + 1,
          email: u?.email || '(unknown)',
          errors: [message]
        })),
        skipped: []
      }
    };
  } catch (err) {
    // Exception JS (ex: variable inconnue, throw, etc.)
    console.error('[createBulkUsers] thrown', err);
    return {
      success: false,
      message: err?.message || 'Unknown error',
      error: { message: err?.message || String(err) },
      summary: { total: users?.length ?? 0, success: 0, failed: users?.length ?? 0, skipped: 0 },
      results: {
        success: [],
        failed: (users || []).map((u, i) => ({
          row: i + 1,
          email: u?.email || '(unknown)',
          errors: [err?.message || 'Unknown error']
        })),
        skipped: []
      }
    };
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
}
