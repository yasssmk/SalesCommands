// frontend/src/api/admin/users.js

import useSWR, { mutate } from 'swr';
import { useMemo, useEffect } from 'react';
import { useAuth } from 'hooks/useAuth';
import { authConfig } from 'config/auth';
import { debounce } from 'lodash';

// utils
import axiosClient, { api } from 'utils/axiosClient';
import { 
  tenantKey, 
  revalidateByPrefix, 
  revalidateMultiple,
  handleBulkRevalidation        
} from 'api/_swr';
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

// ==============================|| DEBOUNCED REVALIDATION (1.4) ||============================== //

/**
 * ✅ Debounced revalidation pour éviter rafales
 * 
 * Groupe les revalidations multiples en 300ms max pour éviter :
 * - Les rafales HTTP lors de bulk operations successives
 * - La surcharge serveur avec requests concurrentes
 * 
 * Exemple : 3 bulk ops en 200ms → 1 seule revalidation users finale
 */
const debouncedRevalidate = debounce((paths) => {
  revalidateMultiple(paths);
}, 300);


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
  
  // Sanitize string fields (trim whitespace)
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
    return { 
      success: false, 
      error: result.error,
      status: result.status || 0,
      response: result.response || null
    };
  }
};


/**
 * ✅ UPDATE USER (PATCH) - Revalidation standardisée + validation client
 * 
 * ✅ Added UUID validation for userId and related fields
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
  
  // ✅ Validate UUID fields in userData
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
  
  // ✅ Sanitize string fields (trim whitespace)
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
    return { 
      success: false, 
      error: result.error,
      status: result.status || 0,
      response: result.response || null
    };
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
      error: result.error || 'Failed to change password',
      status: result.status || 0,
      response: result.response || null
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

  if (!userId || !isValidUUID(userId)) {
    return {
      success: false,
      error: 'Invalid user ID format. Cannot delete user.',
      status: 400
    };
  }
  
  const result = await api.delete(`${endpoints.users}${userId}/`);

  if (result.success) {
    // ✅ revalidation multiple après suppression
    revalidateMultiple([
      endpoints.users,                    // Liste users
      '/client/client-accounts/'          // Stats seats (seats_used diminue)
    ]);
    
    return { success: true, status: result.status ?? 204 };
  } else {
    return { 
      success: false, 
      error: result.error, 
      status: result.status || 0,
      response: result.response || null
    };
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
    return { 
      success: false, 
      error: result.error,
      status: result.status || 0,
      response: result.response || null
    };
  }
};

// =============================|| BULK CRUD STANDARDISÉ || ==================================== //
/**
 * ✅ BULK CREATE USERS
 * 
 * Crée plusieurs utilisateurs en une seule requête
 * 
 * @param {Array} users - Array of user objects
 * @param {string} mode - 'partial' (continue on error) or 'strict' (all or nothing)
 * @param {Function} onSyncProgress - Optional callback: (attempt, maxAttempts) => void
 * @param {Function} onSyncComplete - Optional callback: () => void (called when sync is done)
 * @returns {Promise<Object>} {success: boolean, summary: Object, results: Object}
 */
export const createBulkUsers = async (users, mode = 'partial', onSyncProgress = null, onSyncComplete = null) => {
  let result = null;

  try {
    console.log('[createBulkUsers] start', { count: users?.length ?? 0, mode });

    // Utilise NOTRE wrapper standardisé (cookies, corr-id, handleApiError, etc.)
    result = await api.post('/client/users/bulk-create/', 
      { users, mode }, 
      { timeout: authConfig.BULK_OPERATION_TIMEOUT }
    );

    if (result.success) {
      console.log('[createBulkUsers] ok', { 
        status: result.status ?? 200,
        created: result.data?.summary?.success ?? 0
      });

      return result.data;
    }

    // Gestion d'erreur structurée
    const status = result.status || 0;
    const message = result.error || 'Bulk create failed';
    console.error('[createBulkUsers] api.post error', { status, message });

    if (result.data && typeof result.data === 'object') {
      if (result.data.results || result.data.summary) {
        console.log('[createBulkUsers] returning structured error from backend');
        return {
          ...result.data,
          success: false
        };
      }
    }

    return {
      success: false,
      message: message,
      error: { status, message, response: result.response || null },
      summary: { total: users?.length ?? 0, success: 0, failed: users?.length ?? 0, skipped: 0 },
      results: {
        success: [],
        failed: (users || []).map((u, i) => ({
          row: i + 1,
          email: u?.email || '(unknown)',
          errors: [message]
        })),
        skipped: []
      }
    };

  } catch (err) {
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
  } finally {
    // ⭐ Revalidation intelligente standardisée
    await handleBulkRevalidation(
      result,
      [endpoints.users, '/client/client-accounts/'],
      onSyncProgress,   // Callback intermédiaire
      onSyncComplete    // Callback de fin
    );
  }
};

/**
 * ✅ BULK UPDATE USERS
 * 
 * Met à jour plusieurs utilisateurs en une seule requête
 * 
 * @param {Array<string>} userIds - Array of user IDs to update
 * @param {Object} patchData - Data to apply to all selected users
 * @param {string} mode - 'partial' (continue on error) or 'strict' (all or nothing)
 * @param {Function} onSyncProgress - Optional callback: (attempt, maxAttempts) => void
 * @param {Function} onSyncComplete - Optional callback: () => void (called when sync is done)
 * @returns {Promise<Object>} {success: boolean, isTimeout?: boolean, summary: Object, results: Object}
 */
export const bulkUpdateUsers = async (userIds, patchData, mode = 'partial', onSyncProgress = null, onSyncComplete = null) => {
  let result = null;

  try {
    console.log('[bulkUpdateUsers] start', { 
      count: userIds?.length ?? 0, 
      mode,
      fields: Object.keys(patchData || {})
    });

    // ✅ Validation: Vérifier que userIds est un array non vide
    if (!Array.isArray(userIds) || userIds.length === 0) {
      return {
        success: false,
        message: 'No user IDs provided',
        summary: { requested: 0, updated: 0, failed: 0 },
        results: { success: [], failed: [] }
      };
    }

    // ✅ Validation: Vérifier que tous les IDs sont des UUIDs valides
    const invalidIds = userIds.filter(id => !isValidUUID(id));
    if (invalidIds.length > 0) {
      console.error('[bulkUpdateUsers] invalid UUIDs', { count: invalidIds.length });
      return {
        success: false,
        message: `${invalidIds.length} invalid user ID(s) detected`,
        summary: { requested: userIds.length, updated: 0, failed: userIds.length },
        results: {
          success: [],
          failed: invalidIds.map(id => ({
            id,
            errors: ['Invalid UUID format']
          }))
        }
      };
    }

    // ✅ Validation: Vérifier les UUID fields dans patchData
    const uuidFields = ['role', 'organization', 'team'];
    for (const field of uuidFields) {
      const value = patchData[field];
      
      if (!value || value === '') continue;
      
      if (!isValidUUID(value)) {
        return {
          success: false,
          message: `Invalid ${field} ID format in patch data`,
          summary: { requested: userIds.length, updated: 0, failed: userIds.length },
          results: {
            success: [],
            failed: userIds.map(id => ({
              id,
              errors: [`Invalid ${field} ID format`]
            }))
          }
        };
      }
    }

    // ✅ Sanitization: Nettoyer les champs string
    const sanitized = sanitizeObject(patchData, ['first_name', 'last_name']);

    // ✅ Appel API avec notre wrapper standardisé
    result = await api.patch('/client/users/bulk-update/', {
      ids: userIds,
      patch: sanitized,
      mode
    }, {
      timeout: authConfig.BULK_OPERATION_TIMEOUT
    });

    if (result.success) {
      console.log('[bulkUpdateUsers] ok', { 
        status: result.status ?? 200,
        updated: result.data?.summary?.updated ?? 0
      });

      return result.data;
    }

    // ✅ Gestion d'erreur structurée
    const status = result.status || 0;
    const message = result.error || 'Bulk update failed';
    console.error('[bulkUpdateUsers] api.patch error', { status, message });

    if (result.data && typeof result.data === 'object') {
      if (result.data.results || result.data.summary) {
        console.log('[bulkUpdateUsers] returning structured error from backend');
        return {
          ...result.data,
          success: false
        };
      }
    }

    return {
      success: false,
      message: message,
      error: { status, message, response: result.response || null },
      summary: { requested: userIds.length, updated: 0, failed: userIds.length },
      results: {
        success: [],
        failed: userIds.map(id => ({
          id,
          errors: [message]
        }))
      }
    };

  } catch (err) {
    console.error('[bulkUpdateUsers] thrown', err);
    
    // ⭐ NOUVEAU: Détecter si c'est un timeout
    const isTimeout = 
      err?.code === 'ECONNABORTED' || 
      err?.message?.toLowerCase()?.includes('timeout') ||
      err?.response?.status === 408 ||
      err?.response?.status === 504;
    
    if (isTimeout) {
      console.log('[bulkUpdateUsers] Timeout detected, sync will be triggered');
    }
    
    return {
      success: false,
      isTimeout: isTimeout,  // ⭐ Flag pour indiquer un timeout
      message: err?.message || 'Unknown error',
      error: { message: err?.message || String(err) },
      summary: { requested: userIds?.length ?? 0, updated: 0, failed: userIds?.length ?? 0 },
      results: {
        success: [],
        failed: (userIds || []).map(id => ({
          id,
          errors: [err?.message || 'Unknown error']
        }))
      }
    };
  } finally {
    // ⭐ Revalidation intelligente standardisée
    await handleBulkRevalidation(
      result,
      [endpoints.users, '/client/client-accounts/'],
      onSyncProgress,
      onSyncComplete
    );
  }
};

/**
 * ✅ BULK SOFT DELETE USERS (pour production future)
 * 
 * Archive plusieurs utilisateurs (is_active=false) sans suppression physique
 * ⚠️ Non utilisé en MVP, préparé pour production
 * 
 * @param {Array<string>} userIds - Array of user IDs to soft delete
 * @param {string} mode - 'partial' (continue on error) or 'strict' (all or nothing)
 * @param {Function} onSyncProgress - Optional callback: (attempt, maxAttempts) => void
 * @param {Function} onSyncComplete - Optional callback: () => void (called when sync is done)
 * @returns {Promise<Object>} {success: boolean, summary: Object, results: Object}
 */
export const bulkSoftDeleteUsers = async (userIds, mode = 'partial', onSyncProgress = null, onSyncComplete = null) => {
  let result = null;

  try {
    console.log('[bulkSoftDeleteUsers] start', { 
      count: userIds?.length ?? 0, 
      mode 
    });

    // ✅ Validation: Vérifier que userIds est un array non vide
    if (!Array.isArray(userIds) || userIds.length === 0) {
      return {
        success: false,
        message: 'No user IDs provided',
        summary: { requested: 0, archived: 0, failed: 0 },
        results: { success: [], failed: [] }
      };
    }

    // ✅ Validation: Vérifier que tous les IDs sont des UUIDs valides
    const invalidIds = userIds.filter(id => !isValidUUID(id));
    if (invalidIds.length > 0) {
      console.error('[bulkSoftDeleteUsers] invalid UUIDs', { count: invalidIds.length });
      return {
        success: false,
        message: `${invalidIds.length} invalid user ID(s) detected`,
        summary: { requested: userIds.length, archived: 0, failed: userIds.length },
        results: {
          success: [],
          failed: invalidIds.map(id => ({
            id,
            errors: ['Invalid UUID format']
          }))
        }
      };
    }

    // ✅ Appel API
    result = await api.delete('/client/users/bulk-soft-delete/', {
      data: { ids: userIds, mode },
      timeout: authConfig.BULK_OPERATION_TIMEOUT
    });

    if (result.success) {
      console.log('[bulkSoftDeleteUsers] ok', { 
        status: result.status ?? 200,
        archived: result.data?.summary?.archived ?? 0
      });

      return result.data;
    }

    // ✅ Gestion d'erreur structurée
    const status = result.status || 0;
    const message = result.error || 'Bulk soft delete failed';
    console.error('[bulkSoftDeleteUsers] api.delete error', { status, message });

    if (result.data && typeof result.data === 'object') {
      if (result.data.results || result.data.summary) {
        console.log('[bulkSoftDeleteUsers] returning structured error from backend');
        return {
          ...result.data,
          success: false
        };
      }
    }

    return {
      success: false,
      message: message,
      error: { status, message, response: result.response || null },
      summary: { requested: userIds.length, archived: 0, failed: userIds.length },
      results: {
        success: [],
        failed: userIds.map(id => ({
          id,
          errors: [message]
        }))
      }
    };

  } catch (err) {
    console.error('[bulkSoftDeleteUsers] thrown', err);
    return {
      success: false,
      message: err?.message || 'Unknown error',
      error: { message: err?.message || String(err) },
      summary: { requested: userIds?.length ?? 0, archived: 0, failed: userIds?.length ?? 0 },
      results: {
        success: [],
        failed: (userIds || []).map(id => ({
          id,
          errors: [err?.message || 'Unknown error']
        }))
      }
    };
  } finally {
    // ⭐ Revalidation intelligente standardisée
    await handleBulkRevalidation(
      result,
      [endpoints.users, '/client/client-accounts/'],
      onSyncProgress,   // Callback intermédiaire
      onSyncComplete    // Callback de fin
    );
  }
};

/**
 * ✅ BULK DELETE USERS
 * 
 * Supprime plusieurs utilisateurs en une seule requête
 * ⚠️ En MVP/dev: suppression PHYSIQUE (hard delete)
 * ⚠️ En prod: utiliser bulkSoftDeleteUsers à la place
 * 
 * @param {Array<string>} userIds - Array of user IDs to delete
 * @param {string} mode - 'partial' (continue on error) or 'strict' (all or nothing)
 * @param {Function} onSyncProgress - Optional callback: (attempt, maxAttempts) => void
 * @param {Function} onSyncComplete - Optional callback: () => void (called when sync is done)
 * @returns {Promise<Object>} {success: boolean, isTimeout?: boolean, summary: Object, results: Object}
 */
export const bulkDeleteUsers = async (userIds, mode = 'partial', onSyncProgress = null, onSyncComplete = null) => {
  let result = null;

  try {
    console.log('[bulkDeleteUsers] start', { 
      count: userIds?.length ?? 0, 
      mode 
    });

    // ✅ Validation: Vérifier que userIds est un array non vide
    if (!Array.isArray(userIds) || userIds.length === 0) {
      return {
        success: false,
        message: 'No user IDs provided',
        summary: { requested: 0, deleted: 0, failed: 0 },
        results: { success: [], failed: [] }
      };
    }

    // ✅ Validation: Vérifier que tous les IDs sont des UUIDs valides
    const invalidIds = userIds.filter(id => !isValidUUID(id));
    if (invalidIds.length > 0) {
      console.error('[bulkDeleteUsers] invalid UUIDs', { count: invalidIds.length });
      return {
        success: false,
        message: `${invalidIds.length} invalid user ID(s) detected`,
        summary: { requested: userIds.length, deleted: 0, failed: userIds.length },
        results: {
          success: [],
          failed: invalidIds.map(id => ({
            id,
            errors: ['Invalid UUID format']
          }))
        }
      };
    }

    // ✅ Appel API avec notre wrapper standardisé
    result = await api.delete('/client/users/bulk-delete/', {
      data: { ids: userIds, mode },
      timeout: 30000  
    });

    if (result.success) {
      console.log('[bulkDeleteUsers] ok', { 
        status: result.status ?? 200,
        deleted: result.data?.summary?.deleted ?? 0
      });

      return result.data;
    }

    // ✅ Gestion d'erreur structurée
    const status = result.status || 0;
    const message = result.error || 'Bulk delete failed';
    console.error('[bulkDeleteUsers] api.delete error', { status, message });

    if (result.data && typeof result.data === 'object') {
      if (result.data.results || result.data.summary) {
        console.log('[bulkDeleteUsers] returning structured error from backend');
        return {
          ...result.data,
          success: false
        };
      }
    }

    return {
      success: false,
      message: message,
      error: { status, message, response: result.response || null },
      summary: { requested: userIds.length, deleted: 0, failed: userIds.length },
      results: {
        success: [],
        failed: userIds.map(id => ({
          id,
          errors: [message]
        }))
      }
    };

  } catch (err) {
    console.error('[bulkDeleteUsers] thrown', err);
    
    // ⭐ NOUVEAU: Détecter si c'est un timeout
    const isTimeout = 
      err?.code === 'ECONNABORTED' || 
      err?.message?.toLowerCase()?.includes('timeout') ||
      err?.response?.status === 408 ||
      err?.response?.status === 504;
    
    if (isTimeout) {
      console.log('[bulkDeleteUsers] Timeout detected, sync will be triggered');
    }
    
    return {
      success: false,
      isTimeout: isTimeout,  // ⭐ Flag pour indiquer un timeout
      message: err?.message || 'Unknown error',
      error: { message: err?.message || String(err) },
      summary: { requested: userIds?.length ?? 0, deleted: 0, failed: userIds?.length ?? 0 },
      results: {
        success: [],
        failed: (userIds || []).map(id => ({
          id,
          errors: [err?.message || 'Unknown error']
        }))
      }
    };
  } finally {
    // ⭐ Revalidation intelligente standardisée
    await handleBulkRevalidation(
      result,
      [endpoints.users, '/client/client-accounts/'],
      onSyncProgress,
      onSyncComplete
    );
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
