// frontend/src/api/admin/roles.js

import useSWR from 'swr';
import { useMemo } from 'react';
import { useAuth } from 'hooks/useAuth';
import { api } from 'utils/axiosClient';
import { tenantKey, revalidateMultiple } from 'api/_swr';
import { sanitizeObject } from 'utils/validators';

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  roles: '/client/roles/',
  roleDetail: (id) => `/client/roles/${id}/`,
  permissionsMatrix: '/client/roles/permissions-matrix/'
};

// ==============================|| HELPER - BUILD URL WITH PARAMS ||============================== //

/**
 * Construit une URL avec query params pour la pagination serveur
 * @param {string} baseUrl - URL de base
 * @param {Object} params - Paramètres optionnels {page, pageSize, search, ordering}
 * @returns {string} URL avec query string
 */
const buildUrlWithParams = (baseUrl, params = {}) => {
  const { page, pageSize, search, ordering } = params;
  const queryParams = new URLSearchParams();
  
  if (page !== undefined && page !== null) {
    queryParams.append('page', page);
  }
  
  if (pageSize !== undefined && pageSize !== null) {
    queryParams.append('page_size', pageSize);
  }
  
  if (search !== undefined && search !== null && search !== '') {
    queryParams.append('search', search);
  }

  if (ordering !== undefined && ordering !== null && ordering !== '') {
    queryParams.append('ordering', ordering);
  }
  
  const queryString = queryParams.toString();
  return queryString ? `${baseUrl}?${queryString}` : baseUrl;
};

// ==============================|| HOOKS DE LECTURE ||============================== //

/**
 * GET ROLES - Liste paginée avec filtres
 */
export function useGetRoles(options = {}) {
  const { tenantId } = useAuth();
  const { page = 1, pageSize = 10, search = '', ordering = '' } = options;

  const urlWithParams = useMemo(() => {
    return buildUrlWithParams(endpoints.roles, { page, pageSize, search, ordering });
  }, [page, pageSize, search, ordering]);

  const swrKey = tenantKey(urlWithParams, tenantId);

  const { data, isLoading, error, isValidating } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      // Support both formats: data.data.results and data.results
      roles: data?.data?.results || data?.results || [],
      rolesCount: data?.data?.count || data?.count || 0,
      rolesLoading: isLoading,
      rolesError: error,
      rolesValidating: isValidating,
      rolesEmpty: !isLoading && (!data?.results?.length)
    }),
    [data, isLoading, error, isValidating]
  );

  return memoizedValue;
}

/**
 * ✅ GET ROLE - Détails d'un rôle spécifique
 * 
 * @param {string} roleId - ID du rôle à récupérer
 * @returns {Object} {role, roleLoading, roleError, roleValidating}
 */
export function useGetRole(roleId) {
  const { tenantId } = useAuth();

  const swrKey = roleId && tenantId ? tenantKey(endpoints.roleDetail(roleId), tenantId) : null;

  const { data, isLoading, error, isValidating } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      role: data,
      roleLoading: isLoading,
      roleError: error,
      roleValidating: isValidating
    }),
    [data, isLoading, error, isValidating]
  );

  return memoizedValue;
}

/**
 * ✅ GET USER ROLES - Pour dropdowns dans formulaires
 * MIGRÉ depuis api/admin/users.js
 * 
 * @returns {Object} {roles, rolesLoading, rolesError, rolesValidating, rolesEmpty}
 */
export function useGetUserRoles() {
  const { tenantId } = useAuth();

  const swrKey = tenantKey(endpoints.roles, tenantId);

  const { data, isLoading, error, isValidating } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      // Support both formats: data.data.results and data.results
      roles: data?.data?.results || data?.results || [],
      rolesLoading: isLoading,
      rolesError: error,
      rolesValidating: isValidating,
      rolesEmpty: !isLoading && (!data?.results?.length)
    }),
    [data, isLoading, error, isValidating]
  );

  return memoizedValue;
}

/**
 * ✅ GET PERMISSIONS MATRIX - Registre complet
 * 
 * @returns {Object} {matrix, matrixLoading, matrixError, matrixValidating}
 */
export function useGetPermissionsMatrix() {
  const { tenantId } = useAuth();

  const swrKey = tenantKey(endpoints.permissionsMatrix, tenantId);

  const { data, isLoading, error, isValidating } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      matrix: data?.data || {},
      matrixLoading: isLoading,
      matrixError: error,
      matrixValidating: isValidating
    }),
    [data, isLoading, error, isValidating]
  );

  return memoizedValue;
}

// ==============================|| FONCTIONS DE MUTATION ||============================== //

/**
 * INSERT ROLE - Créer un nouveau rôle
 */
export async function insertRole(payload) {
  // Sanitize string fields
  // const sanitized = sanitizeObject(payload, ['name']);
  
  const result = await api.post(endpoints.roles, payload);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.roles,
      '/client/users/'
    ]);
    return { success: true, data: result.data };
  } else {
    return { 
      success: false, 
      error: result.error,
      status: result.status || 0,
      response: result.response || null
    };
  }
}

/**
 * UPDATE ROLE - Modifier un rôle existant
 */
export async function updateRole(roleId, payload) {
  // Sanitize string fields
  // const sanitized = sanitizeObject(payload, ['name']);
  
  const result = await api.patch(endpoints.roleDetail(roleId), payload);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.roles,
      endpoints.roleDetail(roleId),
      '/client/users/'
    ]);
    return { success: true, data: result.data };
  } else {
    return { 
      success: false, 
      error: result.error,
      status: result.status || 0,
      response: result.response || null
    };
  }
}

/**
 * DELETE ROLE - Supprimer un rôle
 */
export async function deleteRole(roleId) {
  const result = await api.delete(endpoints.roleDetail(roleId));
  
  if (result.success || result.status === 204) {
    revalidateMultiple([
      endpoints.roles,
      '/client/users/'
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
}