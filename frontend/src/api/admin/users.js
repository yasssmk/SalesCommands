// frontend/src/api/admin/users.js

import useSWR, { mutate } from 'swr';
import { useMemo } from 'react';
import { useAuth } from 'hooks/useAuth';

// utils
import axiosClient, { api } from 'utils/axiosClient';

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
  // ✅ Support des tuples [url, tenantId] et des URLs simples
  const url = Array.isArray(urlOrTuple) ? urlOrTuple[0] : urlOrTuple;

  const result = await api.get(url);
  if (result.success) {
    return result.data;
  }
  throw new Error(result.error || 'Failed to fetch data');
};

// ==============================|| REVALIDATION HELPERS ||============================== //

/**
 * ✅ Revalidation ciblée qui matche tuples ET strings
 */
const revalidateTargeted = (urlPrefix) => {
  mutate(
    (key) => {
      // Matcher les tuples [url, tenantId]
      if (Array.isArray(key) && key[0] && key[0].startsWith(urlPrefix)) {
        return true;
      }
      // Matcher les strings simples
      if (typeof key === 'string' && key.startsWith(urlPrefix)) {
        return true;
      }
      return false;
    },
    undefined,
    { revalidate: true }
  );
};

// ==============================|| HOOKS ||============================== //

/**
 * ✅ GET USERS LIST
 * Uses Django pagination format with results array
 */
export function useGetUsers() {
  const { tenantId } = useAuth();

  const swrKey = tenantId ? [endpoints.users, tenantId] : null;

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
 * ✅ GET SINGLE USER
 */
export function useGetUser(userId) {
  const { tenantId } = useAuth();

  const swrKey = userId && tenantId 
    ? [`${endpoints.users}${userId}/`, tenantId] 
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
 * ✅ GET ORGANIZATIONS
 */
export function useGetOrganizations() {
  const { tenantId } = useAuth(); 
  
  //  Utiliser un tuple
  const swrKey = tenantId ? [endpoints.organizations, tenantId] : null;
  
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
 * ✅ GET TEAMS (with filters + enabled)
 * @param {Object} filters - ex: { organization: 'uuid' }
 * @param {boolean} enabled - if false, skip fetch
 */
export function useGetTeams(filters = {}, enabled = true) {
  const { tenantId } = useAuth(); 
  
  const qs = new URLSearchParams(filters || {}).toString();
  const url = `${endpoints.teams}${qs ? `?${qs}` : ''}`;
  
  // Utiliser un tuple avec tenantId
  const swrKey = enabled && tenantId ? [url, tenantId] : null;

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
 * ✅ GET USER ROLES
 */
export function useGetUserRoles() {
  const { tenantId } = useAuth(); 
  
  // Utiliser un tuple
  const swrKey = tenantId ? [endpoints.roles, tenantId] : null;
  
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
 * ✅ GET CLIENT SEATS STATS
 * seats = client.max_users
 * seats_used = # active users
 * seats_left = seats - seats_used
 */
export function useGetClientSeats(clientId) {
  const key = clientId ? endpoints.clientAccountStats(clientId) : null;

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

// ==============================|| CRUD FUNCTIONS ||============================== //

/**
 * ✅ CREATE USER
 */
export const insertUser = async (userData) => {
  const result = await api.post(endpoints.users, userData);

  if (result.success) {
    // Revalidation ciblée pour users et seats
    revalidateTargeted(endpoints.users);
    revalidateTargeted('/client/client-accounts/');

    return { success: true, user: result.data };
  } else {
    return { success: false, error: result.error };
  }
};

/**
 * ✅ UPDATE USER (PATCH)
 */
export const updateUser = async (userId, userData) => {
  const result = await api.patch(`${endpoints.users}${userId}/`, userData);

  if (result.success) {
    // Revalidation ciblée
    revalidateTargeted(endpoints.users);
    revalidateTargeted(`${endpoints.users}${userId}/`);
    revalidateTargeted('/client/client-accounts/');

    return { success: true, user: result.data };
  } else {
    return { success: false, error: result.error };
  }
};

/**
 * ✅ CHANGE USER PASSWORD
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
    revalidateTargeted(`${endpoints.users}${userId}/`);
    
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
 * ✅ DELETE USER
 */
export const deleteUser = async (userId) => {
  const result = await api.delete(`${endpoints.users}${userId}/`);

  if (result.success) {
   // Revalidation ciblée
    revalidateTargeted(endpoints.users);
    revalidateTargeted('/client/client-accounts/');
    return { success: true, status: result.status ?? 204 };
  } else {
    return { success: false, error: result.error, status: result.status };
  }
};

export const toggleUserStatus = async (userId) => {
  const result = await api.post(`${endpoints.users}${userId}/toggle-status/`);

  if (result.success) {
    // Revalidation ciblée
    revalidateTargeted(endpoints.users);
    revalidateTargeted(`${endpoints.users}${userId}/`);
    revalidateTargeted('/client/client-accounts/');

    return { success: true, user: result.data };
  } else {
    return { success: false, error: result.error };
  }
};

// Export revalidation helpers si besoin ailleurs
export const revalidateUsersLists = () => revalidateTargeted(endpoints.users);
export const refreshClientSeats = () => revalidateTargeted('/client/client-accounts/');

// ==============================|| ADDITIONAL OPERATIONS ||============================== //

/**
 * ✅ REFRESH USERS LIST
 */
export const refreshUsers = () => mutate(endpoints.users);

/**
 * ✅ FILTER USERS
 */
export const filterUsers = (filters) => {
  const queryParams = new URLSearchParams(filters).toString();
  const url = `${endpoints.users}?${queryParams}`;
  return mutate(url);
};
