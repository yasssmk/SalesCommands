// frontend/src/api/admin/users.js

import useSWR, { mutate } from 'swr';
import { useMemo } from 'react';

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

const fetcher = async (url) => {
  const result = await api.get(url);
  if (result.success) {
    return result.data;
  }
  throw new Error(result.error || 'Failed to fetch data');
};

// ==============================|| HOOKS ||============================== //

/**
 * ✅ GET USERS LIST
 * Uses Django pagination format with results array
 */
export function useGetUsers() {
  const { data, isLoading, error, isValidating } = useSWR(
    endpoints.users,
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
  const { data, isLoading, error, isValidating } = useSWR(
    userId ? `${endpoints.users}${userId}/` : null,
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
  const { data, isLoading, error } = useSWR(
    endpoints.organizations,
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
 * ✅ GET TEAMS (avec filtres + enabled)
 * @param {Object} filters - ex: { organization: 'uuid' }
 * @param {boolean} enabled - si false, ne fait pas l'appel
 */
export function useGetTeams(filters = {}, enabled = true) {
  const qs = new URLSearchParams(filters || {}).toString();
  const key = enabled ? `${endpoints.teams}${qs ? `?${qs}` : ''}` : null;

  const { data, isLoading, error } = useSWR(
    key,
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
  const { data, isLoading, error } = useSWR(
    endpoints.roles,
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
  // si le clientId n'est pas encore connu, on ne fetch pas
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

  // data peut être:
  // - directement { seats: {...}, users: {...}, ... } (si api.get() dégage déjà .data)
  // - ou { data: { seats: {...}, ... }, client_info: {...} } (réponse back brute)
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
    raw: data // pratique pour debugger ponctuellement
  };
}

// ==============================|| CRUD FUNCTIONS ||============================== //

/**
 * ✅ CREATE USER
 * @param {Object} userData - User data to create
 * @returns {Promise<Object>} {success: boolean, user?: Object, error?: string}
 */
export const insertUser = async (userData) => {
  const result = await api.post(endpoints.users, userData);

  if (result.success) {
    // Update cache optimistically
    mutate(
      endpoints.users,
      (currentData) => {
        if (!currentData) return { results: [result.data], count: 1 };

        return {
          ...currentData,
          results: [...currentData.results, result.data],
          count: (currentData.count || 0) + 1
        };
      },
      false
    );

    // Revalidate to ensure consistency
    mutate(endpoints.users);

    return {
      success: true,
      user: result.data
    };
  } else {
    return {
      success: false,
      error: result.error
    };
  }
};

/**
 * ✅ UPDATE USER (PATCH)
 * @param {string|number} userId - User ID to update
 * @param {Object} userData - Updated user data (partiel)
 * @returns {Promise<Object>} {success: boolean, user?: Object, error?: string}
 */
export const updateUser = async (userId, userData) => {
  const result = await api.patch(`${endpoints.users}${userId}/`, userData);

  if (result.success) {
    // Update cache optimistically
    mutate(
      endpoints.users,
      (currentData) => {
        if (!currentData) return currentData;

        const updatedResults = (currentData.results || []).map((user) =>
          user.id === userId ? result.data : user
        );

        return {
          ...currentData,
          results: updatedResults
        };
      },
      false
    );

    // Also update single user cache if exists
    mutate(`${endpoints.users}${userId}/`, result.data, false);

    // Revalidate to ensure consistency
    mutate(endpoints.users);

    return {
      success: true,
      user: result.data
    };
  } else {
    return {
      success: false,
      error: result.error
    };
  }
};

/**
 * ✅ DELETE USER
 * @param {string|number} userId - User ID to delete
 * @returns {Promise<Object>} {success: boolean, error?: string, status?: number}
 */
export const deleteUser = async (userId) => {
  const result = await api.delete(`${endpoints.users}${userId}/`);

  if (result.success) {
    // Update cache optimistically
    mutate(
      endpoints.users,
      (currentData) => {
        if (!currentData) return currentData;

        const filteredResults = (currentData.results || []).filter((user) => user.id !== userId);

        return {
          ...currentData,
          results: filteredResults,
          count: Math.max(0, (currentData.count || 1) - 1)
        };
      },
      false
    );

    // Remove from single user cache
    mutate(`${endpoints.users}${userId}/`, undefined, false);

    // Revalidate to ensure consistency
    mutate(endpoints.users);

    return { success: true, status: result.status ?? 204 };
  } else {
    return { success: false, error: result.error, status: result.status };
  }
};

// ==============================|| ADDITIONAL OPERATIONS ||============================== //

/**
 * ✅ REFRESH USERS LIST
 */
export const refreshUsers = () => {
  return mutate(endpoints.users);
};

/**
 * ✅ FILTER USERS
 * @param {Object} filters - Filter parameters
 */
export const filterUsers = (filters) => {
  const queryParams = new URLSearchParams(filters).toString();
  const url = `${endpoints.users}?${queryParams}`;
  return mutate(url);
};