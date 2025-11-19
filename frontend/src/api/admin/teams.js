// frontend/src/api/admin/teams.js

import useSWR from 'swr';
import { useMemo } from 'react';
import { useAuth } from 'hooks/useAuth';
import { api } from 'utils/axiosClient';
import { tenantKey, revalidateMultiple } from 'api/_swr';
import { isValidUUID, sanitizeObject } from 'utils/validators';

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  teams: '/client/teams/',
  teamDetail: (id) => `/client/teams/${id}/`,
  teamMembers: (id) => `/client/teams/${id}/members/`,
  teamsSummary: '/client/teams/summary/'
};

// ==============================|| HELPER - BUILD URL WITH PARAMS ||============================== //

/**
 * Construit une URL avec query params
 * @param {string} baseUrl - URL de base
 * @param {Object} params - Paramètres optionnels {search, ordering}
 * @returns {string} URL avec query string
 */
const buildUrlWithParams = (baseUrl, params = {}) => {
  const { search, ordering } = params;
  const queryParams = new URLSearchParams();
  
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
 * GET TEAMS - Liste complète (pas de pagination, max 20 teams)
 * 
 * @param {Object} options - Options de filtrage
 * @param {string} options.search - Terme de recherche
 * @param {string} options.ordering - Tri (ex: 'name', '-created_at')
 * 
 * @returns {Object} {teams, teamsCount, teamsLoading, teamsError, teamsValidating, teamsEmpty}
 */
export function useGetTeams(options = {}) {
  const { tenantId } = useAuth();
  const { search = '', ordering = '' } = options;

  const urlWithParams = useMemo(() => {
    return buildUrlWithParams(endpoints.teams, { search, ordering });
  }, [search, ordering]);

  const swrKey = tenantKey(urlWithParams, tenantId);

  const { data, isLoading, error, isValidating } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      // Support both formats: data.data.results and data.results
      teams: data?.data?.results || data?.results || [],
      teamsCount: data?.data?.count || data?.count || 0,
      teamsLoading: isLoading,
      teamsError: error,
      teamsValidating: isValidating,
      teamsEmpty: !isLoading && (!data?.results?.length)
    }),
    [data, isLoading, error, isValidating]
  );

  return memoizedValue;
}

/**
 * GET TEAM - Détails d'une team spécifique
 * 
 * @param {string} teamId - ID de la team à récupérer
 * @param {Object} options - Options
 * @param {boolean} options.includeMembers - Inclure les membres actifs (default: false)
 * @returns {Object} {team, teamLoading, teamError, teamValidating}
 */
export function useGetTeam(teamId, options = {}) {
  const { tenantId } = useAuth();
  const { includeMembers = false } = options;

  const url = useMemo(() => {
    if (!teamId) return null;
    const baseUrl = endpoints.teamDetail(teamId);
    return includeMembers ? `${baseUrl}?include_members=true` : baseUrl;
  }, [teamId, includeMembers]);

  const swrKey = url && tenantId ? tenantKey(url, tenantId) : null;

  const { data, isLoading, error, isValidating } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      team: data?.data || data,
      teamLoading: isLoading,
      teamError: error,
      teamValidating: isValidating
    }),
    [data, isLoading, error, isValidating]
  );

  return memoizedValue;
}

/**
 * GET TEAM MEMBERS - Liste des membres d'une team
 * 
 * @param {string} teamId - ID de la team
 * @param {Object} filters - Filtres optionnels {active, role_name}
 * @returns {Object} {members, membersCount, membersLoading, membersError}
 */
export function useGetTeamMembers(teamId, filters = {}) {
  const { tenantId } = useAuth();

  const url = useMemo(() => {
    if (!teamId) return null;
    const baseUrl = endpoints.teamMembers(teamId);
    const params = new URLSearchParams();
    
    if (filters.active !== undefined) {
      params.append('active', filters.active);
    }
    if (filters.role_name) {
      params.append('role_name', filters.role_name);
    }
    
    const queryString = params.toString();
    return queryString ? `${baseUrl}?${queryString}` : baseUrl;
  }, [teamId, filters]);

  const swrKey = url && tenantId ? tenantKey(url, tenantId) : null;

  const { data, isLoading, error } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      members: data?.members || [],
      membersCount: data?.total_count || 0,
      membersLoading: isLoading,
      membersError: error
    }),
    [data, isLoading, error]
  );

  return memoizedValue;
}

/**
 * GET TEAMS SUMMARY - Statistiques globales des teams
 * 
 * @returns {Object} {summary, summaryLoading, summaryError}
 */
export function useGetTeamsSummary() {
  const { tenantId } = useAuth();

  const swrKey = tenantKey(endpoints.teamsSummary, tenantId);

  const { data, isLoading, error } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      summary: data?.data || {},
      summaryLoading: isLoading,
      summaryError: error
    }),
    [data, isLoading, error]
  );

  return memoizedValue;
}

// ==============================|| FONCTIONS DE MUTATION ||============================== //

/**
 * INSERT TEAM - Créer une nouvelle team
 * 
 * Validation client-side:
 * - name: required
 * - manager: UUID required
 * - parent_team: UUID optional
 * - description: optional (max 500 chars)
 * 
 * @param {Object} payload - Données de la team
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function insertTeam(payload) {
  // ✅ Validate UUID fields before API call
  if (!payload.manager || !isValidUUID(payload.manager)) {
    return {
      success: false,
      error: 'Invalid manager ID format. Please select a valid manager.'
    };
  }

  if (payload.parent_team && payload.parent_team !== '' && !isValidUUID(payload.parent_team)) {
    return {
      success: false,
      error: 'Invalid parent team ID format. Please select a valid parent team.'
    };
  }

  // ✅ Sanitize string fields
  const sanitized = sanitizeObject(payload, ['name', 'description']);

  // ✅ Convert empty parent_team to null
  if (sanitized.parent_team === '' || sanitized.parent_team === undefined) {
    sanitized.parent_team = null;
  }

  const result = await api.post(endpoints.teams, sanitized);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.teams,         // Liste teams
      '/client/users/'         // Users (car users.team peut changer)
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
 * UPDATE TEAM - Modifier une team existante
 * 
 * Validation client-side:
 * - teamId: UUID required
 * - manager: UUID optional
 * - parent_team: UUID optional
 * 
 * @param {string} teamId - ID de la team à modifier
 * @param {Object} payload - Données à modifier
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function updateTeam(teamId, payload) {
  // ✅ Validate teamId is a valid UUID
  if (!teamId || !isValidUUID(teamId)) {
    return {
      success: false,
      error: 'Invalid team ID format. Cannot update team.'
    };
  }
  
  // ✅ Validate UUID fields in payload
  if (payload.manager && payload.manager !== '' && !isValidUUID(payload.manager)) {
    return {
      success: false,
      error: 'Invalid manager ID format. Please select a valid manager.'
    };
  }

  if (payload.parent_team && payload.parent_team !== '' && !isValidUUID(payload.parent_team)) {
    return {
      success: false,
      error: 'Invalid parent team ID format. Please select a valid parent team.'
    };
  }
  
  // ✅ Sanitize string fields
  const sanitized = sanitizeObject(payload, ['name', 'description']);

  // ✅ Convert empty strings to null for nullable fields
  if (sanitized.manager === '') sanitized.manager = null;
  if (sanitized.parent_team === '') sanitized.parent_team = null;
  
  const result = await api.patch(endpoints.teamDetail(teamId), sanitized);

  if (result.success) {
    revalidateMultiple([
      endpoints.teams,                  // Liste teams
      endpoints.teamDetail(teamId),     // Team spécifique
      '/client/users/'                  // Users (car users.team peut changer)
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
 * DELETE TEAM - Supprimer une team
 * 
 * Business rules (enforced by backend):
 * - Cannot delete team with active members
 * - Children teams are orphaned (parent_team → NULL)
 * 
 * @param {string} teamId - ID de la team à supprimer
 * @returns {Promise<Object>} {success: boolean, status?: number, error?: string}
 */
export async function deleteTeam(teamId) {
  // ✅ Validate teamId is a valid UUID
  if (!teamId || !isValidUUID(teamId)) {
    return {
      success: false,
      error: 'Invalid team ID format. Cannot delete team.',
      status: 400
    };
  }
  
  const result = await api.delete(endpoints.teamDetail(teamId));

  if (result.success || result.status === 204) {
    revalidateMultiple([
      endpoints.teams,         // Liste teams
      '/client/users/'         // Users (car users.team peut être affecté)
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