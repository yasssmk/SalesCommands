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
  roles: '/client/roles/'
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
 * ✅ GET TEAMS
 */
export function useGetTeams() {
  const { data, isLoading, error } = useSWR(
    endpoints.teams,
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
          count: currentData.count + 1
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
 * ✅ UPDATE USER
 * @param {number} userId - User ID to update
 * @param {Object} userData - Updated user data
 * @returns {Promise<Object>} {success: boolean, user?: Object, error?: string}
 */
export const updateUser = async (userId, userData) => {
  const result = await api.put(`${endpoints.users}${userId}/`, userData);
  
  if (result.success) {
    // Update cache optimistically
    mutate(
      endpoints.users,
      (currentData) => {
        if (!currentData) return currentData;

        const updatedResults = currentData.results.map((user) =>
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
 * @param {number} userId - User ID to delete
 * @returns {Promise<Object>} {success: boolean, error?: string}
 */
export const deleteUser = async (userId) => {
  const result = await api.delete(`${endpoints.users}${userId}/`);

  if (result.success) {
    // cache updates identiques à avant
    mutate(
      endpoints.users,
      (currentData) => {
        if (!currentData) return currentData;
        const filteredResults = currentData.results.filter((user) => user.id !== userId);
        return { ...currentData, results: filteredResults, count: currentData.count - 1 };
      },
      false
    );
    mutate(`${endpoints.users}${userId}/`, undefined, false);
    mutate(endpoints.users);

    return { success: true, status: result.status ?? 204 };
  } else {
    // ⬅️ remonter le status pour la couleur du snackbar
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