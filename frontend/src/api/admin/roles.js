// frontend/src/api/admin/roles.js

import useSWR, { mutate } from 'swr';
import { useMemo } from 'react';
import { useAuth } from 'hooks/useAuth';
import { api } from 'utils/axiosClient';
import { tenantKey, revalidateMultiple } from 'api/_swr';

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  roles: '/client/roles/',
  roleDetail: (id) => `/client/roles/${id}/`,
  permissionsMatrix: '/client/roles/permissions-matrix/'
};

// ==============================|| HOOKS DE LECTURE ||============================== //

/**
 * GET ROLES - Liste paginée avec filtres
 */
export function useGetRoles(page = 1, pageSize = 10, search = '', ordering = '') {
  const { tenantId } = useAuth();

  const params = new URLSearchParams();
  if (page) params.append('page', page);
  if (pageSize) params.append('page_size', pageSize);
  if (search) params.append('search', search);
  if (ordering) params.append('ordering', ordering);

  const url = `${endpoints.roles}?${params.toString()}`;
  const swrKey = tenantKey(url, tenantId);

  const { data, isLoading, error } = useSWR(swrKey);

  const memoizedValue = useMemo(
    () => ({
      // Support both formats: data.data.results and data.results
      roles: data?.data?.results || data?.results || [],
      rolesCount: data?.data?.count || data?.count || 0,
      rolesLoading: isLoading,
      rolesError: error
    }),
    [data, isLoading, error]
  );

  return memoizedValue;
}

/**
 * GET ROLE - Détails d'un rôle spécifique
 */
export function useGetRole(roleId) {
  const { tenantId } = useAuth();

  const swrKey = roleId && tenantId ? tenantKey(endpoints.roleDetail(roleId), tenantId) : null;

  const { data, isLoading, error } = useSWR(swrKey);

  const memoizedValue = useMemo(
    () => ({
      role: data?.data || data,
      roleLoading: isLoading,
      roleError: error
    }),
    [data, isLoading, error]
  );

  return memoizedValue;
}

/**
 * GET USER ROLES - Pour dropdowns dans formulaires
 * MIGRÉ depuis api/admin/users.js
 */
export function useGetUserRoles() {
  const { tenantId } = useAuth();

  const swrKey = tenantKey(endpoints.roles, tenantId);

  const { data, isLoading, error } = useSWR(swrKey);

  const memoizedValue = useMemo(
    () => ({
      // Support both formats: data.data.results and data.results
      roles: data?.data?.results || data?.results || [],
      rolesLoading: isLoading,
      rolesError: error
    }),
    [data, isLoading, error]
  );

  return memoizedValue;
}

/**
 * GET PERMISSIONS MATRIX - Registre complet
 */
export function useGetPermissionsMatrix() {
  const { tenantId } = useAuth();

  const swrKey = tenantKey(endpoints.permissionsMatrix, tenantId);

  const { data, isLoading, error } = useSWR(swrKey);

  const memoizedValue = useMemo(
    () => ({
      matrix: data?.data || {},
      matrixLoading: isLoading,
      matrixError: error
    }),
    [data, isLoading, error]
  );

  return memoizedValue;
}

// ==============================|| FONCTIONS DE MUTATION ||============================== //

/**
 * INSERT ROLE - Créer un nouveau rôle
 */
export async function insertRole(payload) {
  try {
    const result = await api.post(endpoints.roles, payload);

    if (result.success) {
      // Revalider le cache
     revalidateMultiple([
        endpoints.roles  
      ]);
      return { success: true, data: result.data };
    }

    return { success: false, error: result.error };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

/**
 * UPDATE ROLE - Modifier un rôle existant
 */
export async function updateRole(roleId, payload) {
  try {
    const result = await api.patch(endpoints.roleDetail(roleId), payload);

    if (result.success) {
      // Revalidation avec revalidateMultiple
      revalidateMultiple([
        endpoints.roles,                      // Liste roles
        `${endpoints.roles}${roleId}/`        // Role spécifique
      ]);
      return { success: true, data: result.data };
    }

    return { success: false, error: result.error };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

/**
 * DELETE ROLE - Supprimer un rôle
 */
export async function deleteRole(roleId) {
  try {
    const result = await api.delete(endpoints.roleDetail(roleId));

    if (result.success || result.status === 204) {
      //Revalidation avec revalidateMultiple
      revalidateMultiple([
        endpoints.roles  // Liste roles
      ]);
      return { success: true };
    }

    return { success: false, error: result.error };
  } catch (error) {
    return { success: false, error: error.message };
  }
}